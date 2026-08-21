# Contexto del Proyecto: python-utils

Repositorio monorepo con utilidades de Python. Actualmente contiene un **sistema de transcripción de video** con backend FastAPI + frontend Angular.

---

## Estructura

```
python-utils/
├── backend-api/           # FastAPI server (puerto 5050)
│   ├── main.py
│   └── requirements.txt
├── frontend-directorio/   # Angular 19 app (puerto 4300)
│   ├── src/app/
│   │   ├── services/api.service.ts
│   │   ├── pages/dashboard/
│   │   └── pages/transcriber/
│   └── angular.json
└── mov-transcriber/       # Script CLI standalone (legacy)
    ├── transcribe.py
    ├── config.yaml
    └── requirements.txt
```

## Arquitectura

```
Angular (4300)  ──HTTP──>  FastAPI (5050)  ──thread──>  Whisper
                              │
                         tasks/*.json  (persistencia)
                         uploads/      (archivos .mov)
```

### Flujo de transcripción

1. Usuario sube archivo `.mov` desde Angular
2. `POST /api/transcribe` guarda el archivo en `uploads/` y crea un task en `tasks/*.json`
3. `asyncio.create_task()` lanza `process_transcription()` en background
4. `whisper.load_model()` + `model.transcribe()` corren en `asyncio.to_thread()` (thread pool)
5. Angular hace polling cada 500ms a `GET /api/transcribe/{task_id}/status`
6. Cuando status=completed, el texto se muestra con botón de copiar

---

## Cómo ejecutar

### Backend

```bash
cd backend-api
pip install -r requirements.txt
uvicorn main:app --reload --port 5050
```

### Frontend

```bash
cd frontend-directorio
npm install
ng serve --port 4300
```

---

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/apps` | Lista de apps disponibles |
| POST | `/api/transcribe` | Sube archivo y crea task. Params: `file` (form), `model`, `language` |
| GET | `/api/transcribe/{task_id}/status` | Estado del task (progress 0-100) |
| GET | `/api/transcribe/{task_id}/result` | Resultado de la transcripción |
| WS | `/ws/transcribe/{task_id}` | WebSocket con updates en tiempo real |

### Task status posibles

- `processing` — en progreso
- `completed` — terminado, resultado en `result`
- `error` — falló, detalle en `error`

---

## Git Branches

- `master` — rama principal
- `develop` — rama de desarrollo (aquí se trabaja)

---

## Problemas conocidos y fixes aplicados

### 1. Puerto 5050 (no 5000)

macOS ControlCenter ocupa el puerto 5000. El backend usa **5050**.

**Fix:** `uvicorn main:app --port 5050`

### 2. Whisper crashea al iniciar FastAPI

`import whisper` al tope de `main.py` descarga modelo y crashea durante el startup del servidor.

**Fix (commit `6d3434b`):** Lazy import dentro de `process_transcription()`:
```python
async def process_transcription(...):
    import whisper  # solo se importa cuando se necesita
```

### 3. Event loop bloqueado por whisper

`whisper.load_model()` y `model.transcribe()` son llamadas **bloqueantes** (CPU-bound). Si corren en el event loop de FastAPI, el servidor no responde a requests de polling.

**Fix (commit `72a21db`):** Envolver con `asyncio.to_thread()`:
```python
model = await asyncio.to_thread(whisper.load_model, model_name)
result = await asyncio.to_thread(model.transcribe, file_path, **options)
```

### 4. Tasks se pierden con uvicorn --reload

`uvicorn --reload` reinicia el proceso cuando detecta cambios en archivos. El diccionario `tasks = {}` (en memoria) se borra. Los task_ids anteriores devuelven **404** en el polling.

**Fix (commit `2a31ce8`):** Persistir cada task a disco en `tasks/*.json`. Al iniciar, `_load_all_tasks()` carga todos los JSONs del directorio.

### 5. Modelo Whisper no descargado (pendiente / parcialmente resuelto)

**Síntoma:** La primera vez que se usa el sistema, `whisper.load_model("base")` intenta descargar ~139MB. La descarga puede **colgarse silenciosamente** — el task queda en `status: processing, progress: 0` indefinidamente. No hay proceso de whisper corriendo (`ps aux | grep whisper` vacío), pero el task nunca avanza ni falla.

**Lo que se intentó:**
- `asyncio.to_thread()` para no bloquear el event loop → resuelve el bloqueo del servidor, pero no la descarga colgada
- Persistir tasks a disco → sobrevive restarts, pero no resuelve el stuck en download
- Ejecutar `whisper.load_model("base")` manualmente desde terminal → funciona, descarga en ~5s y queda cacheado en `~/.cache/whisper/`

**Lo que falta / soluciones posibles:**
- **Pre-descargar el modelo** en el Dockerfile o script de setup: `python -c "import whisper; whisper.load_model('base')"`
- **Agregar timeout** a la llamada de descarga con `asyncio.wait_for()`
- **Agregar logging** al proceso de descarga para ver si falla o se cuelga
- **Mostrar error real** al frontend cuando la descarga falla (actualmente el exception handler en `process_transcription` captura errores, pero si la descarga se cuelga sin exception, nunca llega ahí)
- **Validar que el modelo esté cacheado** antes de aceptar el task, y devolver error claro si no lo está

### 6. OMP Error #15 (cosmético)

```
OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib already initialized.
```

Warning de OpenMP por múltiples copias de la librería. **No afecta funcionalidad.** Se puede silenciar con `KMP_DUPLICATE_LIB_OK=TRUE`.

---

## Estado actual (último commit: `2a31ce8`)

- Backend corriendo en `http://localhost:5050`
- Frontend corriendo en `http://localhost:4300`
- Modelo whisper `base` cacheado en `~/.cache/whisper/`
- Tasks persistidos a disco en `tasks/*.json`
- **Pendiente:** El task de transcripción más reciente (`1b0a3e5c`) quedó stuck en `progress: 0` porque la descarga del modelo se colgó antes de que estuviera cacheado. Ahora que el modelo ya está descargado, un nuevo upload debería funcionar.

---

## Dependencias

### Backend (Python)
- fastapi
- uvicorn
- python-multipart
- openai-whisper
- websockets

### Frontend (Node/Angular)
- Angular 19
- TypeScript
- HttpClient (para API calls)
- FormsModule (para ngModel)
