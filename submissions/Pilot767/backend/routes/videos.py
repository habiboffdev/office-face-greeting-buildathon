import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import VIDEOS_DIR
from database import _utc_now, get_connection
from models import VideoResponse

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("", response_model=list[VideoResponse])
def list_videos():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, title FROM videos ORDER BY id"
        ).fetchall()
    return [
        VideoResponse(
            id=r["id"],
            filename=r["filename"],
            title=r["title"],
            url=f"/api/videos/stream/{quote(r['filename'])}",
        )
        for r in rows
    ]


@router.get("/stream/{filename:path}")
def stream_video(filename: str):
    path = VIDEOS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Video not found")
    return FileResponse(path, media_type="video/mp4")


@router.post("", response_model=VideoResponse)
async def upload_video(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".mp4"):
        raise HTTPException(400, "Only MP4 allowed")

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    dest = VIDEOS_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO videos (filename, title, created_at) VALUES (?, ?, ?)",
            (file.filename, Path(file.filename).stem, _utc_now()),
        )
        row = conn.execute(
            "SELECT id, filename, title FROM videos WHERE filename = ?", (file.filename,)
        ).fetchone()

    return VideoResponse(
        id=row["id"],
        filename=row["filename"],
        title=row["title"],
        url=f"/api/videos/stream/{quote(row['filename'])}",
    )


@router.delete("/{video_id}")
def delete_video(video_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT filename FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Video not found")
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))

    path = VIDEOS_DIR / row["filename"]
    path.unlink(missing_ok=True)
    return {"ok": True}
