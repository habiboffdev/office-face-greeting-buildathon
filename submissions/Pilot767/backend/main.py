import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, UPLOADS_DIR
from face_engine import FaceEngine
from recognition_worker import RecognitionWorker
from routes import analytics, founders, health, people, settings, videos
from seed import run_seed
from telegram_command_worker import TelegramCommandWorker
from websocket_manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

face_engine = FaceEngine()
ws_manager = WebSocketManager()
recognition_worker: RecognitionWorker | None = None
telegram_command_worker: TelegramCommandWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global recognition_worker, telegram_command_worker
    loop = asyncio.get_running_loop()
    app.state.face_engine = face_engine
    app.state.ws_manager = ws_manager
    logger.info("Initializing database and seeding assets...")
    run_seed(face_engine)
    recognition_worker = RecognitionWorker(face_engine, ws_manager, loop)
    app.state.recognition_worker = recognition_worker
    recognition_worker.start()
    telegram_command_worker = TelegramCommandWorker()
    app.state.telegram_command_worker = telegram_command_worker
    telegram_command_worker.start()
    yield
    if telegram_command_worker:
        telegram_command_worker.stop()
    if recognition_worker:
        recognition_worker.stop()
    logger.info("Shutdown complete")


app = FastAPI(title="Rocus", lifespan=lifespan)
app.state.face_engine = face_engine
app.state.ws_manager = ws_manager

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "founders").mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=str(UPLOADS_DIR)), name="media")

app.include_router(people.router)
app.include_router(videos.router)
app.include_router(analytics.router)
app.include_router(health.router)
app.include_router(settings.router)
app.include_router(founders.router)


@app.websocket("/ws/display")
async def display_websocket(websocket: WebSocket):
    # Brauzer Origin: http://localhost:5173 — har doim qabul qilamiz
    await ws_manager.connect_display(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_display(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
