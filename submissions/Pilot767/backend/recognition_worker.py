import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

import cv2

from config import CAMERA_INDEX, COOLDOWN_SECONDS, RECOGNITION_INTERVAL_FRAMES
from database import get_connection
from founder_messages import founder_greeting_lines, visits_today_utc
from greeting import build_greeting
from telegram_notify import notify_visit

if TYPE_CHECKING:
    from face_engine import FaceEngine
    from websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

MAX_READ_FAILURES = 30
CAMERA_RETRY_DELAY = 2.0


class RecognitionWorker:
    def __init__(
        self,
        face_engine: "FaceEngine",
        ws_manager: "WebSocketManager",
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._face_engine = face_engine
        self._ws_manager = ws_manager
        self._loop = loop
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._cooldown: dict[int, float] = {}
        self.camera_active = False
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="recognition")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def clear_cooldown(self, person_id: int) -> None:
        """Admin o'chirishdan keyin tez qayta sinash uchun."""
        self._cooldown.pop(person_id, None)

    def _open_camera(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            self.camera_active = False
            self.last_error = f"Kamera ochilmadi (indeks {CAMERA_INDEX})"
            logger.error(self.last_error)
            cap.release()
            return None
        self.camera_active = True
        self.last_error = None
        logger.info("Camera opened (index %s)", CAMERA_INDEX)
        return cap

    def _run(self) -> None:
        cap: cv2.VideoCapture | None = None
        frame_idx = 0
        read_failures = 0

        try:
            while not self._stop.is_set():
                if cap is None or not cap.isOpened():
                    cap = self._open_camera()
                    if cap is None:
                        time.sleep(CAMERA_RETRY_DELAY)
                        continue
                    frame_idx = 0
                    read_failures = 0

                ok, frame = cap.read()
                if not ok:
                    read_failures += 1
                    if read_failures >= MAX_READ_FAILURES:
                        logger.warning(
                            "Kamera uzildi (sleep/uyg'onish?). Qayta ulanmoqda..."
                        )
                        cap.release()
                        cap = None
                        self.camera_active = False
                        self.last_error = "Kamera qayta ulanmoqda..."
                        read_failures = 0
                        time.sleep(CAMERA_RETRY_DELAY)
                    else:
                        time.sleep(0.05)
                    continue

                read_failures = 0
                if not self.camera_active:
                    self.camera_active = True
                    self.last_error = None

                frame_idx += 1
                if frame_idx % RECOGNITION_INTERVAL_FRAMES != 0:
                    continue

                try:
                    features = self._face_engine.extract_features_for_all_faces(frame)
                except Exception as exc:
                    logger.warning("Recognition frame error: %s", exc)
                    continue

                if not features:
                    continue

                matched: list[tuple[int, float]] = []
                seen_ids: set[int] = set()
                for embedding in features:
                    person_id, score = self._face_engine.match(embedding)
                    if person_id is None:
                        continue
                    if person_id in seen_ids:
                        continue
                    seen_ids.add(person_id)
                    matched.append((person_id, score))

                for person_id, score in matched:
                    now = time.time()
                    last = self._cooldown.get(person_id, 0)
                    if now - last < COOLDOWN_SECONDS:
                        continue

                    person = self._record_visit(person_id)
                    if not person:
                        continue

                    self._cooldown[person_id] = now
                    vtd = visits_today_utc(person_id)
                    greeting = build_greeting(
                        person["full_name"],
                        person["total_visits"],
                        person["last_seen_at_before"],
                        bool(person["is_vip"]),
                        person.get("birthday"),
                        visits_today=vtd,
                    )
                    fn = person["full_name"]
                    payload = {
                        "person_id": person_id,
                        "full_name": fn,
                        "greeting": greeting["title"],
                        "subtitle": greeting["subtitle"],
                        "is_vip": bool(person["is_vip"]),
                        "is_birthday": bool(greeting.get("is_birthday")),
                        "score": round(score, 3),
                    }
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
                        vtd = visits_today_utc(person_id)
                        g_line, s_line = founder_greeting_lines(
                            dict(f), fn, visits_today=vtd
                        )
                        payload["greeting"] = g_line
                        payload["subtitle"] = s_line
                        payload["is_founder"] = True
                        payload["founder_image_url"] = f"/api/media/{f['hero_image_path']}"
                        payload["is_birthday"] = False
                        payload["founder_visits_today"] = vtd
                    elif person["is_vip"]:
                        payload["visits_today"] = vtd
                    asyncio.run_coroutine_threadsafe(
                        self._ws_manager.broadcast_welcome(payload),
                        self._loop,
                    )
                    notify_visit(
                        full_name=person["full_name"],
                        total_visits=person["total_visits"],
                        greeting_title=payload["greeting"],
                        greeting_subtitle=payload["subtitle"],
                        is_vip=bool(person["is_vip"]),
                        is_birthday=bool(payload.get("is_birthday")),
                        match_score=score,
                    )
                    logger.info(
                        "Recognized %s (%.3f): %s — %s",
                        person["full_name"],
                        score,
                        payload["greeting"],
                        payload["subtitle"],
                    )
        finally:
            if cap is not None:
                cap.release()
            self.camera_active = False
            logger.info("Camera released")

    def _record_visit(self, person_id: int) -> dict | None:
        from database import _utc_now

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, full_name, total_visits, last_seen_at, is_vip, birthday FROM people WHERE id = ?",
                (person_id,),
            ).fetchone()
            if not row:
                return None

            now = _utc_now()
            last_seen_before = row["last_seen_at"]
            new_total = (row["total_visits"] or 0) + 1

            conn.execute(
                "UPDATE people SET total_visits = ?, last_seen_at = ? WHERE id = ?",
                (new_total, now, person_id),
            )
            conn.execute(
                "INSERT INTO visits (person_id, visited_at) VALUES (?, ?)",
                (person_id, now),
            )

            return {
                "full_name": row["full_name"],
                "total_visits": new_total,
                "last_seen_at_before": last_seen_before,
                "is_vip": row["is_vip"],
                "birthday": row["birthday"],
            }
