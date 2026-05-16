"""Asoschilar (max 31): maxsus ekran salomi + hero rasm."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import FOUNDERS_DIR, FOUNDERS_MAX, UPLOADS_DIR
from database import _utc_now, get_connection

router = APIRouter(prefix="/api/founders", tags=["founders"])

_FOUNDER_SELECT = """
            SELECT f.id, f.person_id, p.full_name, f.hero_image_path,
                   f.welcome_title, f.welcome_subtitle,
                   f.welcome_title_repeat, f.welcome_subtitle_repeat,
                   f.sort_order, f.created_at
            FROM founders f
            JOIN people p ON p.id = f.person_id
"""


class FounderResponse(BaseModel):
    id: int
    person_id: int
    full_name: str
    hero_image_path: str
    hero_image_url: str
    welcome_title: str
    welcome_subtitle: str
    welcome_title_repeat: str | None = None
    welcome_subtitle_repeat: str | None = None
    sort_order: int
    created_at: str


@router.get("", response_model=list[FounderResponse])
def list_founders():
    with get_connection() as conn:
        rows = conn.execute(
            f"{_FOUNDER_SELECT} ORDER BY f.sort_order ASC, f.id ASC"
        ).fetchall()
    return [_row_to_response(dict(r)) for r in rows]


def _row_to_response(r: dict) -> FounderResponse:
    rel = r["hero_image_path"]
    return FounderResponse(
        id=r["id"],
        person_id=r["person_id"],
        full_name=r["full_name"],
        hero_image_path=rel,
        hero_image_url=f"/api/media/{rel}",
        welcome_title=r["welcome_title"],
        welcome_subtitle=r["welcome_subtitle"],
        welcome_title_repeat=r.get("welcome_title_repeat"),
        welcome_subtitle_repeat=r.get("welcome_subtitle_repeat"),
        sort_order=r["sort_order"] or 0,
        created_at=r["created_at"],
    )


class FounderUpdate(BaseModel):
    welcome_title: str | None = Field(default=None)
    welcome_subtitle: str | None = Field(default=None)
    welcome_title_repeat: str | None = Field(default=None)
    welcome_subtitle_repeat: str | None = Field(default=None)
    sort_order: int | None = Field(default=None)


_PATCH_COLS = frozenset(
    {
        "welcome_title",
        "welcome_subtitle",
        "welcome_title_repeat",
        "welcome_subtitle_repeat",
        "sort_order",
    }
)


@router.patch("/{founder_id}", response_model=FounderResponse)
def patch_founder(founder_id: int, body: FounderUpdate):
    raw = body.model_dump(exclude_unset=True)
    updates: dict[str, object] = {k: v for k, v in raw.items() if k in _PATCH_COLS}
    if not updates:
        raise HTTPException(400, "Yangilanadigan maydon yo‘q.")

    if "welcome_title" in updates:
        t = str(updates["welcome_title"]).strip()
        if not t:
            raise HTTPException(400, "Sarlavha bo‘sh bo‘lmasin.")
        updates["welcome_title"] = t
    if "welcome_subtitle" in updates:
        s = str(updates["welcome_subtitle"]).strip()
        if not s:
            raise HTTPException(400, "Ostmatn bo‘sh bo‘lmasin.")
        updates["welcome_subtitle"] = s
    for k in ("welcome_title_repeat", "welcome_subtitle_repeat"):
        if k in updates and updates[k] is not None:
            v = str(updates[k]).strip()
            updates[k] = v if v else None

    placeholders = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [founder_id]

    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE founders SET {placeholders} WHERE id = ?",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Topilmadi")
        row = conn.execute(
            f"{_FOUNDER_SELECT} WHERE f.id = ?",
            (founder_id,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Topilmadi")
    return _row_to_response(dict(row))


@router.post("", response_model=FounderResponse)
async def add_founder(
    person_id: int = Form(...),
    welcome_title: str = Form(...),
    welcome_subtitle: str = Form(...),
    welcome_title_repeat: str | None = Form(None),
    welcome_subtitle_repeat: str | None = Form(None),
    sort_order: int = Form(0),
    hero_image: UploadFile = File(...),
):
    title = (welcome_title or "").strip()
    subtitle = (welcome_subtitle or "").strip()
    if not title or not subtitle:
        raise HTTPException(400, "Sarlavha va ostmatn bo‘sh bo‘lmasin.")
    tr = (welcome_title_repeat or "").strip() or None
    sr = (welcome_subtitle_repeat or "").strip() or None
    suffix = Path(hero_image.filename or "photo.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "Rasm: JPG, PNG yoki WEBP.")

    FOUNDERS_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM founders").fetchone()[0]
        if n >= FOUNDERS_MAX:
            raise HTTPException(400, f"Asoschilar soni {FOUNDERS_MAX} dan oshmasin.")
        exists = conn.execute(
            "SELECT id FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if not exists:
            raise HTTPException(404, "Bunday odam bazada yo‘q (avval Yuzlar orqali qo‘shing).")
        dup = conn.execute(
            "SELECT id FROM founders WHERE person_id = ?", (person_id,)
        ).fetchone()
        if dup:
            raise HTTPException(400, "Bu odam allaqachon asoschilar ro‘yxatida.")

        uid = uuid.uuid4().hex[:10]
        fname = f"hero_{person_id}_{uid}{suffix}"
        rel_path = f"founders/{fname}"
        dest = UPLOADS_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        content = await hero_image.read()
        dest.write_bytes(content)

        cur = conn.execute(
            """
            INSERT INTO founders (
                person_id, hero_image_path,
                welcome_title, welcome_subtitle,
                welcome_title_repeat, welcome_subtitle_repeat,
                sort_order, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (person_id, rel_path, title, subtitle, tr, sr, sort_order, _utc_now()),
        )
        fid = cur.lastrowid
        row = conn.execute(
            f"{_FOUNDER_SELECT} WHERE f.id = ?",
            (fid,),
        ).fetchone()

    return _row_to_response(dict(row))


@router.delete("/{founder_id}")
def delete_founder(founder_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT hero_image_path FROM founders WHERE id = ?", (founder_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Topilmadi")
        rel = row["hero_image_path"]
        conn.execute("DELETE FROM founders WHERE id = ?", (founder_id,))
    path = UPLOADS_DIR / rel
    path.unlink(missing_ok=True)
    return {"ok": True}
