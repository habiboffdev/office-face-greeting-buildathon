from fastapi import APIRouter, Request

from config import TELEGRAM_BOT_TOKEN
from telegram_command_worker import command_chat_allowlist
from telegram_notify import send_telegram_text, telegram_get_me, telegram_status



router = APIRouter(prefix="/api/health", tags=["health"])





@router.get("")

def health(request: Request):

    worker = getattr(request.app.state, "recognition_worker", None)

    _cmd_allow = command_chat_allowlist()

    return {

        "status": "ok",

        "camera_active": worker.camera_active if worker else False,

        "camera_error": worker.last_error if worker else None,

        "telegram": telegram_status(),

        "telegram_commands": {

            "enabled": bool(TELEGRAM_BOT_TOKEN and len(_cmd_allow) > 0),

            "allowlist_size": len(_cmd_allow),

        },

    }





@router.get("/telegram-debug")

def telegram_debug():

    """

    Token tekshiruvi (getMe). Brauzer: http://127.0.0.1:8000/api/health/telegram-debug

    """

    me = telegram_get_me()

    return {

        "getMe": me,

        "chat_id_configured": bool(telegram_status().get("enabled")),

        "hint": "404 bo'lsa: backendni yangilab qayta ishga tushiring (uvicorn). To'g'ridan port 8000 oching.",

    }





def _telegram_test_response():

    result = send_telegram_text(

        "✅ <b>Rocus</b> — test xabar. Shaxsiy kanal: bot — Administrator, «Post messages» yoqilgan bo‘lishi kerak.",

        parse_html=True,

    )

    if result.get("ok"):

        return {"ok": True, "message": "Yuborildi", **result}

    return {"ok": False, **result}





@router.post("/telegram-test")

def telegram_test_post():

    """Kanalga test xabari (POST)."""

    return _telegram_test_response()





@router.get("/telegram-test")

def telegram_test_get():

    """Brauzerda tekshirish uchun GET (xuddi shu test)."""

    return _telegram_test_response()


