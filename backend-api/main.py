import os
import uuid
import json
import socket
import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Silence the cosmetic OpenMP duplicate-lib warning on macOS.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

logger = logging.getLogger("python_utils")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

TASKS_DIR = Path("tasks")
TASKS_DIR.mkdir(exist_ok=True)

WHISPER_CACHE_DIR = Path.home() / ".cache" / "whisper"
SOCKET_TIMEOUT_SECONDS = 30
LOAD_MODEL_TIMEOUT_SECONDS = 180


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def _save_task(task_id: str, task: dict):
    _task_path(task_id).write_text(json.dumps(task))


def _load_task(task_id: str) -> dict | None:
    path = _task_path(task_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def _load_all_tasks() -> dict[str, dict]:
    loaded = {}
    for path in TASKS_DIR.glob("*.json"):
        try:
            task = json.loads(path.read_text())
            loaded[task["id"]] = task
        except Exception:
            pass
    return loaded


def _update_task(task_id: str, **kwargs):
    task = tasks[task_id]
    task.update(kwargs)
    _save_task(task_id, task)
    return task


def _is_model_cached(model_name: str) -> bool:
    path = WHISPER_CACHE_DIR / f"{model_name}.pt"
    return path.is_file() and path.stat().st_size > 0


def _fail_orphaned_tasks():
    """Background asyncio tasks die on reload/restart; mark leftovers as error."""
    recovered = 0
    for task_id, task in list(tasks.items()):
        if task.get("status") == "processing":
            task["status"] = "error"
            task["error"] = (
                "La transcripción se interrumpió porque el servidor se reinició. "
                "Vuelve a subir el archivo."
            )
            task["message"] = task["error"]
            _save_task(task_id, task)
            recovered += 1
    if recovered:
        logger.warning("Marked %s orphaned transcription task(s) as error", recovered)


def _log_model_cache_status(model_name: str = "base"):
    if _is_model_cached(model_name):
        path = WHISPER_CACHE_DIR / f"{model_name}.pt"
        size_mb = path.stat().st_size / (1024 * 1024)
        logger.info("Whisper model '%s' cached at %s (%.1f MB)", model_name, path, size_mb)
        return
    logger.warning(
        "Whisper model '%s' is NOT cached. First transcription will download it. "
        "Pre-download with: python preload_model.py --model %s",
        model_name,
        model_name,
    )


def _load_whisper_model(model_name: str):
    """Load a Whisper model with a socket timeout so urllib cannot hang forever.

    openai-whisper downloads via urllib.request.urlopen() with no timeout. If the
    network stalls, load_model() never returns and the task stays at progress 0.
    """
    import whisper

    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(SOCKET_TIMEOUT_SECONDS)
    try:
        logger.info(
            "whisper.load_model(%s) starting (cached=%s)",
            model_name,
            _is_model_cached(model_name),
        )
        model = whisper.load_model(model_name)
        logger.info("whisper.load_model(%s) finished", model_name)
        return model
    finally:
        socket.setdefaulttimeout(previous_timeout)


tasks = _load_all_tasks()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _fail_orphaned_tasks()
    _log_model_cache_status("base")
    yield


app = FastAPI(title="Python Utils API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "whisper_model_cached": _is_model_cached("base"),
    }


@app.get("/api/apps")
def list_apps():
    return {
        "apps": [
            {
                "id": "mov-transcriber",
                "name": "Transcriptor de Video",
                "description": "Transcribe archivos .mov a texto plano",
                "icon": "video_file",
            }
        ]
    }


@app.post("/api/transcribe")
async def start_transcription(
    file: UploadFile = File(...),
    model: str = Form("base"),
    language: str = Form("es"),
):
    task_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{task_id}{file_ext}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    cached = _is_model_cached(model)
    message = (
        f"Cargando modelo '{model}' ({language})..."
        if cached
        else f"Descargando modelo '{model}' (primera vez)..."
    )
    task = {
        "id": task_id,
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "result": None,
        "error": None,
        "message": message,
        "model": model,
        "language": language,
        "model_cached": cached,
    }
    tasks[task_id] = task
    _save_task(task_id, task)

    logger.info(
        "Started transcription %s file=%s model=%s language=%s cached=%s",
        task_id,
        file.filename,
        model,
        language,
        cached,
    )
    asyncio.create_task(process_transcription(task_id, str(file_path), model, language))

    return {"task_id": task_id, "status": "processing", "model": model, "language": language}


async def process_transcription(task_id: str, file_path: str, model_name: str, language: str):
    try:
        cached = _is_model_cached(model_name)
        if cached:
            _update_task(task_id, progress=10, message=f"Cargando modelo '{model_name}'...")
        else:
            logger.warning(
                "Model '%s' not in cache; downloading before transcription %s",
                model_name,
                task_id,
            )
            _update_task(
                task_id,
                progress=5,
                message=(
                    f"Descargando modelo '{model_name}' (primera vez). "
                    "Si tarda demasiado, cancela y ejecuta: python preload_model.py"
                ),
            )

        try:
            model = await asyncio.wait_for(
                asyncio.to_thread(_load_whisper_model, model_name),
                timeout=LOAD_MODEL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"La carga del modelo '{model_name}' superó {LOAD_MODEL_TIMEOUT_SECONDS}s. "
                f"Pre-descarga el modelo con: python preload_model.py --model {model_name}"
            )

        _update_task(
            task_id,
            progress=30,
            message=f"Transcribiendo audio (idioma={language})...",
        )

        options = {}
        if language and language != "auto":
            options["language"] = language

        logger.info("Transcribing %s with model=%s language=%s", file_path, model_name, language)
        result = await asyncio.to_thread(model.transcribe, file_path, **options)

        _update_task(
            task_id,
            progress=100,
            status="completed",
            result=result["text"],
            message="Transcripción completada",
        )
        logger.info("Transcription %s completed", task_id)

        os.remove(file_path)

    except Exception as e:
        logger.exception("Transcription %s failed: %s", task_id, e)
        _update_task(
            task_id,
            status="error",
            error=str(e),
            message=str(e),
        )


@app.get("/api/transcribe/{task_id}/status")
def get_status(task_id: str):
    if task_id not in tasks:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return tasks[task_id]


@app.get("/api/transcribe/{task_id}/result")
def get_result(task_id: str):
    if task_id not in tasks:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    task = tasks[task_id]
    if task["status"] != "completed":
        return {"status": task["status"], "text": None, "error": task.get("error")}
    return {"status": "completed", "text": task["result"]}


@app.websocket("/ws/transcribe/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            if task_id in tasks:
                await websocket.send_json(tasks[task_id])
                if tasks[task_id]["status"] in ("completed", "error"):
                    break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
