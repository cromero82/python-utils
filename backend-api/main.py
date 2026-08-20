import os
import uuid
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import whisper

app = FastAPI(title="Python Utils API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

tasks = {}

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


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

    tasks[task_id] = {
        "id": task_id,
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "result": None,
        "error": None,
    }

    asyncio.create_task(process_transcription(task_id, str(file_path), model, language))

    return {"task_id": task_id, "status": "processing"}


async def process_transcription(task_id: str, file_path: str, model_name: str, language: str):
    try:
        tasks[task_id]["progress"] = 10
        model = whisper.load_model(model_name)
        tasks[task_id]["progress"] = 30

        options = {}
        if language and language != "auto":
            options["language"] = language

        result = model.transcribe(file_path, **options)
        tasks[task_id]["progress"] = 90

        tasks[task_id]["result"] = result["text"]
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100

        os.remove(file_path)

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)


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
