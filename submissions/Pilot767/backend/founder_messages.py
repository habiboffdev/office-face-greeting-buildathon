"""Asoschi salomi: UTC bo‘yicha kun ichida birinchi vs keyingi kirishlar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from database import get_connection
from greeting import expand_placeholders


def visits_today_utc(person_id: int) -> int:
    """Bugungi (UTC) tashriflar soni — hozirgi tadbir yozuvi allaqachon bazada bo‘lishi kerak."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM visits
            WHERE person_id = ? AND visited_at >= ?
            """,
            (person_id, today_start),
        ).fetchone()
    return int(row["c"])


def founder_greeting_lines(
    row: Mapping[str, Any],
    full_name: str,
    *,
    visits_today: int,
) -> tuple[str, str]:
    """
    visits_today: shu kundagi jami yozuvlar (1 = birinchi kirish, 2+ = qayta).
    """
    is_repeat = visits_today > 1
    if is_repeat:
        rt = row.get("welcome_title_repeat")
        rs = row.get("welcome_subtitle_repeat")
        raw_t = (rt if rt is not None else "") or ""
        raw_s = (rs if rs is not None else "") or ""
        t = raw_t.strip() or str(row["welcome_title"])
        s = raw_s.strip() or str(row["welcome_subtitle"])
    else:
        t, s = str(row["welcome_title"]), str(row["welcome_subtitle"])
    return expand_placeholders(t, full_name), expand_placeholders(s, full_name)
