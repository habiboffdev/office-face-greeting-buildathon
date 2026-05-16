"""Telegram bot buyruqlari: /top_hafta, /top_oy (getUpdates long polling)."""

from __future__ import annotations

import html
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from config import (
    ORG_NAME,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_COMMAND_CHAT_IDS,
    TELEGRAM_TOP_MONTH_DAYS,
)
from database import get_connection
from telegram_notify import call_bot_api, send_telegram_to_chat, telegram_set_default_commands

logger = logging.getLogger(__name__)

TOP_N = 10
DAYS_WEEK = 7


def command_chat_allowlist() -> frozenset[int]:
    ids: list[int] = []
    raw = TELEGRAM_COMMAND_CHAT_IDS.strip()
    if raw:
        for part in raw.split(","):
            p = part.strip()
            if p.lstrip("-").isdigit():
                ids.append(int(p))
    else:
        cid = TELEGRAM_CHAT_ID.strip()
        if cid.lstrip("-").isdigit():
            ids.append(int(cid))
    return frozenset(ids)


def top_visitors(days: int, limit: int) -> list[tuple[str, int]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.full_name AS fn, COUNT(*) AS cnt
            FROM visits v
            JOIN people p ON p.id = v.person_id
            WHERE v.visited_at >= ?
            GROUP BY v.person_id, p.full_name
            ORDER BY cnt DESC, fn COLLATE NOCASE ASC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [(str(r["fn"]), int(r["cnt"])) for r in rows]


def today_visit_stats() -> tuple[int, int, str]:
    """(noyob odamlar, jami kirish yozuvlari, sana leybeli UTC)."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = today_start.isoformat()
    date_label = today_start.strftime("%Y-%m-%d (UTC)")
    with get_connection() as conn:
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT person_id) FROM visits WHERE visited_at >= ?",
            (today_iso,),
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at >= ?",
            (today_iso,),
        ).fetchone()[0]
    return int(distinct), int(total), date_label


def format_today_message() -> str:
    people, visits, label = today_visit_stats()
    lines = [
        f"🏢 <b>{html.escape(ORG_NAME)}</b>",
        "📅 <b>Bugungi tashriflar</b>",
        f"<i>{html.escape(label)}</i>",
        "",
        f"👥 Noyob odamlar: <b>{people}</b>",
        f"🚪 Jami kirishlar (tan olishlar): <b>{visits}</b>",
    ]
    return "\n".join(lines)


def format_top_message(heading: str, days: int, rows: list[tuple[str, int]]) -> str:
    lines = [
        f"🏢 <b>{html.escape(ORG_NAME)}</b>",
        f"📊 <b>{html.escape(heading)}</b>",
        f"<i>Oxirgi {days} kun — kirishlar soni bo‘yicha (TOP {TOP_N})</i>",
        "",
    ]
    if not rows:
        lines.append("<i>Shu davrda tashrif yozuvlari yo‘q.</i>")
        return "\n".join(lines)
    for i, (name, cnt) in enumerate(rows, start=1):
        lines.append(f"{i}. {html.escape(name)} — <b>{cnt}</b> marta")
    return "\n".join(lines)


def _help_html() -> str:
    md = TELEGRAM_TOP_MONTH_DAYS
    return (
        f"🏢 <b>{html.escape(ORG_NAME)}</b> — buyruqlar\n\n"
        "/hafta — oxirgi <b>7</b> kunda eng ko‘p kirganlar (TOP "
        f"{TOP_N})\n"
        "/bugun yoki /today — bugungi noyob odamlar va jami kirishlar (UTC kun)\n"
        f"/oy — oxirgi <b>{md}</b> kunda eng ko‘p kirganlar (TOP {TOP_N})\n\n"
        "<i>Shuningdek ishlaydi: /top_hafta, /top_oy, /today</i>\n\n"
        "/help — qisqa yordam"
    )


def parse_command(text: str) -> str:
    if not text or not text.strip().startswith("/"):
        return ""
    first = text.strip().split(maxsplit=1)[0]
    return first.split("@", 1)[0].lower()


def handle_command(cmd: str) -> str | None:
    if cmd in ("/start", "/help"):
        return _help_html()
    if cmd in ("/bugun", "/today"):
        return format_today_message()
    if cmd in ("/top_hafta", "/hafta"):
        rows = top_visitors(DAYS_WEEK, TOP_N)
        return format_top_message("Haftalik TOP", DAYS_WEEK, rows)
    if cmd in ("/top_oy", "/oy"):
        md = TELEGRAM_TOP_MONTH_DAYS
        rows = top_visitors(md, TOP_N)
        return format_top_message("Oy TOP", md, rows)
    return None


def _poll_loop(stop: threading.Event, allow: frozenset[int]) -> None:
    del_body = call_bot_api("deleteWebhook", {"drop_pending_updates": False})
    if not del_body.get("ok"):
        logger.warning("Telegram deleteWebhook: %s", del_body)
    else:
        logger.info("Telegram webhook o‘chirildi (buyruqlar: long polling)")

    next_offset: int | None = None

    while not stop.is_set():
        try:
            payload: dict = {
                "timeout": 30,
                "allowed_updates": ["message"],
            }
            if next_offset is not None:
                payload["offset"] = next_offset

            data = call_bot_api("getUpdates", payload, timeout=45)
            if not data.get("ok"):
                logger.warning(
                    "getUpdates xato: %s",
                    data.get("description", data)[:500],
                )
                time.sleep(2)
                continue

            for u in data.get("result", []):
                next_offset = int(u["update_id"]) + 1
                msg = u.get("message")
                if not msg:
                    continue
                text = msg.get("text")
                if not text or not isinstance(text, str):
                    continue
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                if chat_id not in allow:
                    logger.debug("Buyruq rad etildi (chat_id=%s)", chat_id)
                    continue

                cmd = parse_command(text)
                if not cmd:
                    continue

                body = handle_command(cmd)
                if body is None:
                    if text.strip().startswith("/"):
                        send_telegram_to_chat(
                            chat_id,
                            "Noma'lum buyruq. /help — yordam",
                            parse_html=False,
                        )
                    continue

                send_telegram_to_chat(chat_id, body, parse_html=True)
        except Exception:
            logger.exception("Telegram buyruqlar sikli xatosi")
            time.sleep(3)


class TelegramCommandWorker:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._allow: frozenset[int] = frozenset()

    def start(self) -> None:
        if not TELEGRAM_BOT_TOKEN:
            logger.info("Telegram buyruqlar: token yo‘q")
            return
        allow = command_chat_allowlist()
        if not allow:
            logger.info(
                "Telegram buyruqlar: ruxsatli chat yo‘q — .env da TELEGRAM_COMMAND_CHAT_IDS "
                "(vergul bilan) yoki raqamli TELEGRAM_CHAT_ID kiriting"
            )
            return
        self._allow = allow
        self._stop.clear()
        sync = telegram_set_default_commands()
        if sync.get("ok"):
            logger.info("Telegram bot menyusi (setMyCommands) yangilandi")
        else:
            logger.warning(
                "Telegram setMyCommands bajarilmadi: %s",
                sync.get("description", sync)[:200],
            )
        self._thread = threading.Thread(
            target=_poll_loop,
            args=(self._stop, allow),
            name="telegram-commands",
            daemon=True,
        )
        self._thread.start()
        logger.info("Telegram buyruqlar tinglovi yoqildi (%s ta chat)", len(allow))

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4)
