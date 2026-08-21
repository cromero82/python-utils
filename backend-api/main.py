import os
import uuid
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Python Utils API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

TASKS_DIR = Path("tasks")
TASKS_DIR.mkdir(exist_ok=True)


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
    tasks = {}
    for path in TASKS_DIR.glob("*.json"):
        try:
            task = json.loads(path.read_text())
            tasks[task["id"]] = task
        except Exception:
            pass
    return tasks


tasks = _load_all_tasks()


@app.get("/api/health")
def health():
    return {"status": "ok"}


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
async def start_transcription(file: UploadFile = File(...), model: str = "base", language: str = "es"):
    task_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{task_id}{file_ext}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    task = {
        "id": task_id,
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "result": None,
        "error": None,
    }
    tasks[task_id] = task
    _save_task(task_id, task)

    asyncio.create_task(process_transcription(task_id, str(file_path), model, language))

    return {"task_id": task_id, "status": "processing"}


async def process_transcription(task_id: str, file_path: str, model_name: str, language: str):
    try:
        import whisper

        tasks[task_id]["progress"] = 10
        _save_task(task_id, tasks[task_id])

        model = await asyncio.to_thread(whisper.load_model, model_name)
        tasks[task_id]["progress"] = 30
        _save_task(task_id, tasks[task_id])

        options = {}
        if language and language != "auto":
            options["language"] = language

        result = await asyncio.to_thread(model.transcribe, file_path, **options)
        tasks[task_id]["progress"] = 90
        _save_task(task_id, tasks[task_id])

        tasks[task_id]["result"] = result["text"]
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        _save_task(task_id, tasks[task_id])

        os.remove(file_path)

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)
        _save_task(task_id, tasks[task_id])


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
        return {"status": task["status"], "text": None}
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
