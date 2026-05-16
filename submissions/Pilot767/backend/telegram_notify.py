"""Telegram orqali tashrif haqida xabar (ixtiyoriy, TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)."""

from __future__ import annotations

import html
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from config import ORG_NAME, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOP_MONTH_DAYS

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4000


def _configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def telegram_status() -> dict[str, bool | str]:
    """Health uchun: token/chat bor-yo‘qligi (maxfiy qiymatlarni chiqarmaymiz)."""
    return {
        "enabled": _configured(),
    }


def _api_post(
    method: str,
    payload: dict[str, Any],
    *,
    timeout: float = 20,
) -> tuple[int, dict[str, Any]]:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        body: dict[str, Any] = json.loads(raw) if raw else {}
        return resp.status, body


def _normalize_chat_id(chat_raw: str) -> str | int:
    s = chat_raw.strip()
    if s.lstrip("-").isdigit():
        return int(s)
    return s




def call_bot_api(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 20,
) -> dict[str, Any]:
    """Telegram Bot API chaqiruvi (getUpdates, deleteWebhook, ...)."""
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN yo‘q"}
    try:
        _, body = _api_post(method, payload or {}, timeout=timeout)
        return body
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        try:
            return json.loads(err) if err else {"ok": False, "description": err}
        except json.JSONDecodeError:
            return {"ok": False, "description": err}
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


def telegram_set_default_commands() -> dict[str, Any]:
    """
    Bot menyusidagi / buyruqlar (guruh va shaxsiy chat).
    Backend ishga tushganda TelegramCommandWorker chaqiradi.
    """
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN yo‘q"}
    d = TELEGRAM_TOP_MONTH_DAYS
    return call_bot_api(
        "setMyCommands",
        {
            "commands": [
                {"command": "start", "description": "Rocus — kirish"},
                {"command": "help", "description": "Buyruqlar ro‘yxati"},
                {"command": "hafta", "description": "7 kunda eng ko‘p kirgan TOP 10"},
                {"command": "bugun", "description": "Bugungi tashriflar (odam va kirishlar)"},
                {"command": "oy", "description": f"So‘nggi {d} kunda TOP 10"},
            ]
        },
    )


def send_telegram_to_chat(
    chat_id: str | int,
    text: str,
    *,
    parse_html: bool = True,
) -> dict[str, Any]:
    """
    Istalgan chatga xabar (buyruq javoblari). Token bo‘lishi kerak.
    """
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN yo‘q"}

    trimmed = text if len(text) <= MAX_MESSAGE_LEN else text[: MAX_MESSAGE_LEN - 1] + "…"

    def try_send(pm: str | None) -> tuple[int, dict[str, Any]] | None:
        pl: dict[str, Any] = {
            "chat_id": chat_id,
            "text": trimmed,
            "disable_web_page_preview": True,
        }
        if pm:
            pl["parse_mode"] = pm
        try:
            return _api_post("sendMessage", pl)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                j = json.loads(err_body) if err_body else {}
            except json.JSONDecodeError:
                j = {"description": err_body[:800]}
            return e.code, {"ok": False, **j}
        except Exception as exc:
            return 0, {"ok": False, "description": str(exc)}

    first = try_send("HTML" if parse_html else None)
    if first is None:
        return {"ok": False, "error": "Noma’lum xatolik"}

    status, body = first
    if body.get("ok"):
        return {"ok": True, "telegram": body}

    desc = str(body.get("description", body))
    if parse_html and status == 400 and (
        "parse" in desc.lower() or "entities" in desc.lower()
    ):
        second = try_send(None)
        if second and second[1].get("ok"):
            return {"ok": True, "telegram": second[1], "note": "HTML bekor, plain text"}

    hint = _hint_for_error(desc)
    return {
        "ok": False,
        "error": desc,
        "hint": hint,
        "telegram": body,
        "http_status": status,
    }


def send_telegram_text(text: str, *, parse_html: bool = True) -> dict[str, Any]:
    """
    sendMessage chaqiruvi (TELEGRAM_CHAT_ID). Natija: ok, telegram, error.
    """
    if not _configured():
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN yoki TELEGRAM_CHAT_ID bo‘sh — backend/.env tekshiring.",
        }

    payload_chat = _normalize_chat_id(TELEGRAM_CHAT_ID)
    result = send_telegram_to_chat(payload_chat, text, parse_html=parse_html)
    if result.get("ok"):
        logger.info("Telegram xabar yuborildi (chat_id=%s)", payload_chat)
    else:
        logger.warning(
            "Telegram yuborilmadi: %s",
            str(result.get("error", result))[:300],
        )
    return result


def _hint_for_error(description: str) -> str:
    d = description.lower()
    if "chat not found" in d or "chat_id is empty" in d:
        return "TELEGRAM_CHAT_ID noto‘g‘ri. Kanal uchun -100... ID yoki @kanalusername ishlating."
    if "not enough rights" in d or "have no rights" in d or "can't write" in d:
        return (
            "Shaxsiy kanalda ham bot Administrator bo‘lishi va «Post messages» "
            "(xabarlarni joylash / publish) ruxsati yoqilgan bo‘lishi kerak."
        )
    if "bot was not in the" in d or "not a member" in d:
        return "Bot kanal/guruhga qo‘shilmagan. Avval botni kanalga admin qiling."
    if "wrong HTTP URL" in d or "invalid" in d and "token" in d:
        return "TELEGRAM_BOT_TOKEN noto‘g‘ri yoki bekor qilingan (BotFather da tekshiring)."
    return "Telegram qo‘llanmasi: kanalda bot admin, Post messages ruxsati; chat_id to‘g‘ri ekanini tekshiring."


def notify_visit(
    *,
    full_name: str,
    total_visits: int,
    greeting_title: str,
    greeting_subtitle: str,
    is_vip: bool,
    is_birthday: bool,
    match_score: float,
) -> None:
    if not _configured():
        return

    safe_name = html.escape(full_name)
    safe_title = html.escape(greeting_title)
    safe_sub = html.escape(greeting_subtitle)

    lines = [
        f"🏢 <b>{html.escape(ORG_NAME)}</b> — <b>tashrif</b>",
        f"👤 {safe_name}",
        f"📊 Jami tashriflar: <b>{total_visits}</b>",
        f"💬 {safe_title}",
        f"<i>{safe_sub}</i>",
        f"🎯 Moslik: <code>{match_score:.3f}</code>",
    ]
    if is_vip:
        lines.append("⭐ VIP")
    if is_birthday:
        lines.append("🎂 Tug‘ilgan kun tabrigi")

    send_telegram_text("\n".join(lines), parse_html=True)


def telegram_get_me() -> dict[str, Any]:
    """Token to‘g‘rimi — getMe."""
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "Token yo‘q"}
    try:
        status, body = _api_post("getMe", {})
        return {
            "ok": bool(body.get("ok")),
            "http_status": status,
            "telegram": body,
        }
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "http_status": e.code, "error": err}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
