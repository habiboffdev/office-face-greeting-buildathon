# Rocus

AI face recognition welcome display for office reception — promotional videos play fullscreen while the laptop webcam recognizes enrolled people and shows a glassmorphism welcome overlay (video never pauses).

## Stack

- **Frontend:** React, Vite, Tailwind CSS, Framer Motion, React Router, Recharts
- **Backend:** Python FastAPI, OpenCV YuNet + SFace (ONNX), SQLite, WebSocket

## Project layout

```
FaceID/
├── assets/people/     # Source photos (seeded on startup)
├── assets/videos/     # Source MP4 promos
├── backend/
└── frontend/
```

## Setup

### 1. Backend

```powershell
cd c:\Users\HP\Desktop\FaceID\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

API: http://127.0.0.1:8000  
On first run, photos from `assets/people/` and videos from `assets/videos/` are copied and enrolled automatically.

### 2. Frontend

```powershell
cd c:\Users\HP\Desktop\FaceID\frontend
npm install
npm run dev
```

Open:

- **Display (TV mode):** http://localhost:5173/display — press F11 for fullscreen
- **Admin:** http://localhost:5173/admin

## Demo flow

1. Start backend (camera + recognition worker).
2. Start frontend, open `/display`.
3. Stand in front of the laptop camera as an enrolled person (Abdulloh, Dilxumor, Murodillo).
4. Welcome overlay appears for ~5 seconds; videos keep playing.
5. Use **Admin → Test** to trigger a greeting without the camera.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_INDEX` | `0` | Webcam device index |
| `RECOGNITION_INTERVAL_FRAMES` | `10` | Run recognition every N frames |
| `COOLDOWN_SECONDS` | `60` | Min seconds between greetings per person |
| `SIMILARITY_THRESHOLD` | `0.45` | Face match threshold |
| `TELEGRAM_BOT_TOKEN` | _(bo‘sh)_ | [@BotFather](https://t.me/BotFather) dan bot token |
| `TELEGRAM_CHAT_ID` | _(bo‘sh)_ | Kanal/guruh ID (masalan `-100...`); bot admin yoki a’zo |
| `GREETING_ABSENCE_WEEK_DAYS` | `7` | Aqlli salom: shuncha kundan keyin «hafta» xabari |
| `GREETING_ABSENCE_MONTH_DAYS` | `30` | Aqlli salom: shuncha kundan keyin «oy» xabari |

`backend/.env` faylida ham yozishingiz mumkin (`TELEGRAM_BOT_TOKEN=...`, `TELEGRAM_CHAT_ID=...`) — bu fayl `.gitignore` da.

## API routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + camera status |
| GET | `/api/people` | List enrolled people |
| POST | `/api/people` | Add person (multipart) |
| DELETE | `/api/people/{id}` | Remove person |
| GET | `/api/people/visits` | Visit log |
| POST | `/api/people/{id}/test-greeting` | Test WebSocket overlay |
| GET | `/api/videos` | Playlist |
| GET | `/api/videos/stream/{filename}` | Stream MP4 |
| GET | `/api/analytics/summary` | Dashboard stats |
| WS | `/ws/display` | Welcome events |

## Architecture

```
Webcam → RecognitionWorker (thread) → OpenCV SFace → SQLite visit
                              ↓
                    WebSocket broadcast
                              ↓
              /display → WelcomeOverlay (video unchanged)
```
