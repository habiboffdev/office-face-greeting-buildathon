import logging
import shutil
from pathlib import Path

from config import ASSETS_DIR, EMBEDDINGS_DIR, PEOPLE_DIR, VIDEOS_DIR
from database import _utc_now, get_connection, init_db
from greeting_settings import get_greeting_settings
from face_engine import FaceEngine

logger = logging.getLogger(__name__)


def _name_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").title()


def ensure_dirs() -> None:
    for d in (PEOPLE_DIR, EMBEDDINGS_DIR, VIDEOS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def sync_videos() -> None:
    src = ASSETS_DIR / "videos"
    if not src.exists():
        return
    for mp4 in src.glob("*.mp4"):
        dest = VIDEOS_DIR / mp4.name
        if not dest.exists() or dest.stat().st_size != mp4.stat().st_size:
            shutil.copy2(mp4, dest)
        with get_connection() as conn:
            exists = conn.execute(
                "SELECT id FROM videos WHERE filename = ?", (mp4.name,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO videos (filename, title, created_at) VALUES (?, ?, ?)",
                    (mp4.name, mp4.stem, _utc_now()),
                )


def seed_people(face_engine: FaceEngine) -> None:
    src = ASSETS_DIR / "people"
    if not src.exists():
        return

    for img in sorted(src.glob("*")):
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        full_name = _name_from_filename(img.name)
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, image_path FROM people WHERE full_name = ?", (full_name,)
            ).fetchone()

            dest = PEOPLE_DIR / img.name
            if not dest.exists() or dest.stat().st_size != img.stat().st_size:
                shutil.copy2(img, dest)

            if existing:
                person_id = existing["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO people (full_name, image_path, total_visits, is_vip, birthday, created_at)
                    VALUES (?, ?, 0, 0, NULL, ?)
                    """,
                    (full_name, str(dest.relative_to(PEOPLE_DIR.parent)), _utc_now()),
                )
                person_id = cur.lastrowid
                logger.info("Seeded person: %s (id=%s)", full_name, person_id)

        emb_path = EMBEDDINGS_DIR / f"{person_id}.npy"
        if emb_path.exists():
            face_engine.load_embedding(person_id, emb_path)
            continue

        embedding = face_engine.extract_from_image_path(dest)
        if embedding is None:
            logger.warning("No face found in %s", img.name)
            continue

        saved = face_engine.save_embedding(person_id, embedding)
        with get_connection() as conn:
            conn.execute(
                "UPDATE people SET embedding_path = ? WHERE id = ?",
                (str(saved.relative_to(EMBEDDINGS_DIR.parent)), person_id),
            )
        logger.info("Embedding saved for %s", full_name)


def load_embeddings_cache(face_engine: FaceEngine) -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, embedding_path FROM people WHERE embedding_path IS NOT NULL"
        ).fetchall()
    entries = []
    for row in rows:
        if row["embedding_path"]:
            entries.append((row["id"], EMBEDDINGS_DIR.parent / row["embedding_path"]))
    face_engine.reload_all(entries)


def run_seed(face_engine: FaceEngine) -> None:
    init_db()
    get_greeting_settings()
    ensure_dirs()
    sync_videos()
    seed_people(face_engine)
    load_embeddings_cache(face_engine)
