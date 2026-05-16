import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from config import EMBEDDINGS_DIR, PEOPLE_DIR, UPLOADS_DIR
from database import _utc_now, get_connection
from models import BirthdayUpdate, PersonResponse, VisitResponse, VipUpdate

router = APIRouter(prefix="/api/people", tags=["people"])
_executor = ThreadPoolExecutor(max_workers=2)


@router.get("", response_model=list[PersonResponse])
def list_people():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, full_name, image_path, total_visits, last_seen_at, is_vip, birthday, created_at FROM people ORDER BY full_name"
        ).fetchall()
    return [
        PersonResponse(
            id=r["id"],
            full_name=r["full_name"],
            image_path=r["image_path"],
            total_visits=r["total_visits"] or 0,
            last_seen_at=r["last_seen_at"],
            is_vip=bool(r["is_vip"]),
            birthday=r["birthday"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("", response_model=PersonResponse)
async def create_person(
    request: Request,
    full_name: str = Form(...),
    is_vip: bool = Form(False),
    birthday: str | None = Form(None),
    image: UploadFile = File(...),
):
    engine = request.app.state.face_engine
    suffix = Path(image.filename or "photo.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(
            400,
            "Faqat JPG, PNG yoki WEBP. iPhone HEIC ishlamaydi — JPG ga o‘giring.",
        )

    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    content = await image.read()

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO people (full_name, image_path, total_visits, is_vip, birthday, created_at)
            VALUES (?, '', 0, ?, ?, ?)
            """,
            (full_name, int(is_vip), birthday, _utc_now()),
        )
        person_id = cur.lastrowid

    filename = f"{person_id}{suffix}"
    dest = PEOPLE_DIR / filename
    dest.write_bytes(content)

    loop = asyncio.get_running_loop()
    embedding = await loop.run_in_executor(
        _executor, engine.extract_from_image_path, dest
    )
    if embedding is None:
        with get_connection() as conn:
            conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
        dest.unlink(missing_ok=True)
        raise HTTPException(
            400,
            "Rasmda yuz topilmadi. Yuz old tomonda, yorug‘ va aniq bo‘lgan rasm yuboring.",
        )

    emb_path = engine.save_embedding(person_id, embedding)
    rel_img = str(dest.relative_to(PEOPLE_DIR.parent))
    rel_emb = str(emb_path.relative_to(EMBEDDINGS_DIR.parent))

    with get_connection() as conn:
        conn.execute(
            "UPDATE people SET image_path = ?, embedding_path = ? WHERE id = ?",
            (rel_img, rel_emb, person_id),
        )
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()

    return PersonResponse(
        id=row["id"],
        full_name=row["full_name"],
        image_path=row["image_path"],
        total_visits=0,
        last_seen_at=row["last_seen_at"],
        is_vip=bool(row["is_vip"]),
        birthday=row["birthday"],
        created_at=row["created_at"],
    )


@router.delete("/{person_id}")
def delete_person(person_id: int, request: Request):
    engine = request.app.state.face_engine
    worker = getattr(request.app.state, "recognition_worker", None)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Person not found")
        frow = conn.execute(
            "SELECT hero_image_path FROM founders WHERE person_id = ?", (person_id,)
        ).fetchone()
        founder_rel = frow["hero_image_path"] if frow else None
        conn.execute("DELETE FROM visits WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM people WHERE id = ?", (person_id,))

    if row["image_path"]:
        img = PEOPLE_DIR.parent / row["image_path"]
        if img.exists():
            img.unlink(missing_ok=True)

    # DB dagi yo'l va standart {id}.npy — ikkalasini ham olib tashlash
    if row["embedding_path"]:
        emb_db = EMBEDDINGS_DIR.parent / row["embedding_path"]
        emb_db.unlink(missing_ok=True)
    EMBEDDINGS_DIR.joinpath(f"{person_id}.npy").unlink(missing_ok=True)

    if founder_rel:
        (UPLOADS_DIR / founder_rel).unlink(missing_ok=True)

    engine.unload_person(person_id)
    if worker is not None:
        worker.clear_cooldown(person_id)
    return {"ok": True}


@router.get("/visits", response_model=list[VisitResponse])
def list_visits(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT v.id, v.person_id, p.full_name, v.visited_at
            FROM visits v
            JOIN people p ON p.id = v.person_id
            ORDER BY v.visited_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        VisitResponse(
            id=r["id"],
            person_id=r["person_id"],
            full_name=r["full_name"],
            visited_at=r["visited_at"],
        )
        for r in rows
    ]


@router.patch("/{person_id}/birthday", response_model=PersonResponse)
def update_birthday(person_id: int, body: BirthdayUpdate):
    b = (body.birthday or "").strip()
    stored = b[:10] if len(b) >= 10 else (b or None)
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Person not found")
        conn.execute("UPDATE people SET birthday = ? WHERE id = ?", (stored, person_id))
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    return PersonResponse(
        id=row["id"],
        full_name=row["full_name"],
        image_path=row["image_path"],
        total_visits=row["total_visits"] or 0,
        last_seen_at=row["last_seen_at"],
        is_vip=bool(row["is_vip"]),
        birthday=row["birthday"],
        created_at=row["created_at"],
    )


@router.patch("/{person_id}/vip", response_model=PersonResponse)
def update_vip(person_id: int, body: VipUpdate):
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Person not found")
        conn.execute(
            "UPDATE people SET is_vip = ? WHERE id = ?",
            (int(body.is_vip), person_id),
        )
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    return PersonResponse(
        id=row["id"],
        full_name=row["full_name"],
        image_path=row["image_path"],
        total_visits=row["total_visits"] or 0,
        last_seen_at=row["last_seen_at"],
        is_vip=bool(row["is_vip"]),
        birthday=row["birthday"],
        created_at=row["created_at"],
    )


@router.post("/{person_id}/test-greeting")
async def test_greeting(
    person_id: int,
    request: Request,
    simulate_birthday: bool = False,
    preview_birthday: bool = False,
    sample_name: str | None = None,
    founder_preview_repeat: bool = False,
    vip_preview_repeat: bool = False,
):
    from datetime import datetime, timedelta, timezone

    from founder_messages import founder_greeting_lines, visits_today_utc
    from greeting import build_greeting
    from greeting_settings import apply_birthday_templates

    ws_manager = request.app.state.ws_manager

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Person not found")

    if preview_birthday:
        display_name = (sample_name or "").strip() or row["full_name"]
        greeting = {**apply_birthday_templates(display_name), "is_birthday": True}
        actual_visits_today = 0
    else:
        last_seen = row["last_seen_at"]
        if simulate_birthday and row["birthday"]:
            last_seen = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        actual_visits_today = visits_today_utc(person_id)
        vtd_greet = (
            max(actual_visits_today, 2) if vip_preview_repeat else actual_visits_today
        )
        greeting = build_greeting(
            row["full_name"],
            row["total_visits"] or 0,
            last_seen,
            bool(row["is_vip"]),
            row["birthday"],
            visits_today=vtd_greet,
        )

    fn = row["full_name"]
    payload: dict = {
        "person_id": person_id,
        "full_name": fn,
        "greeting": greeting["title"],
        "subtitle": greeting["subtitle"],
        "is_vip": bool(row["is_vip"]),
        "is_birthday": bool(greeting.get("is_birthday")),
    }

    if not preview_birthday:
        with get_connection() as conn:
            f = conn.execute(
                """
                SELECT hero_image_path, welcome_title, welcome_subtitle,
                       welcome_title_repeat, welcome_subtitle_repeat
                FROM founders WHERE person_id = ?
                """,
                (person_id,),
            ).fetchone()
        if f:
            actual_today = visits_today_utc(person_id)
            vtd = max(actual_today, 2) if founder_preview_repeat else actual_today
            g_line, s_line = founder_greeting_lines(
                dict(f), fn, visits_today=vtd
            )
            payload["greeting"] = g_line
            payload["subtitle"] = s_line
            payload["is_founder"] = True
            payload["founder_image_url"] = f"/api/media/{f['hero_image_path']}"
            payload["is_birthday"] = False
            payload["founder_visits_today"] = actual_today
        elif row["is_vip"]:
            payload["visits_today"] = actual_visits_today
    await ws_manager.broadcast_welcome(payload)
    return payload
