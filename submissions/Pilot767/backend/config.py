from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# .env dagi qiymatlar tizim muhitidan ustun (masalan eski TELEGRAM_CHAT_ID kanalda qolmasin)
load_dotenv(BASE_DIR / ".env", override=True)

import os

PROJECT_ROOT = BASE_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
PEOPLE_DIR = BASE_DIR / "people"
EMBEDDINGS_DIR = BASE_DIR / "embeddings"
MODELS_DIR = BASE_DIR / "models"
VIDEOS_DIR = BASE_DIR / "videos"
UPLOADS_DIR = BASE_DIR / "uploads"
FOUNDERS_DIR = UPLOADS_DIR / "founders"
FOUNDERS_MAX = int(os.getenv("FOUNDERS_MAX", "31"))
DB_PATH = BASE_DIR / "smart_office.db"

ORG_NAME = os.getenv("ORG_NAME", "Rocus")
ORG_TAGLINE = os.getenv("ORG_TAGLINE", "Rocusga xush kelibsiz!")

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
RECOGNITION_INTERVAL_FRAMES = int(os.getenv("RECOGNITION_INTERVAL_FRAMES", "10"))
# Kadrda nechta yuzgacha alohida tan olinadi (navbatga bitta-bitta welcome ketadi)
MAX_FACES_PER_FRAME = int(os.getenv("MAX_FACES_PER_FRAME", "8"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "60"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.40"))
OVERLAY_DURATION_MS = int(os.getenv("OVERLAY_DURATION_MS", "5500"))

# Aqlli salom: oxirgi tashrifdan necha kundan keyin «hafta / oy» xabari
GREETING_ABSENCE_WEEK_DAYS = int(os.getenv("GREETING_ABSENCE_WEEK_DAYS", "7"))
GREETING_ABSENCE_MONTH_DAYS = int(os.getenv("GREETING_ABSENCE_MONTH_DAYS", "30"))

# Telegram: @BotFather dan token; kanal/guruh uchun chat_id (masalan -1001234567890)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
# Buyruqlar (/top_hafta, /top_oy) faqat shu chat id lardan: vergul bilan. Bo‘sh bo‘lsa raqamli TELEGRAM_CHAT_ID ishlatiladi.
TELEGRAM_COMMAND_CHAT_IDS = os.getenv("TELEGRAM_COMMAND_CHAT_IDS", "").strip()
# /top_oy uchun “so‘nggi N kun” (standart — 30)
TELEGRAM_TOP_MONTH_DAYS = int(os.getenv("TELEGRAM_TOP_MONTH_DAYS", "30"))

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
