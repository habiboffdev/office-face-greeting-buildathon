"""Telegram admin bot entry point."""

from __future__ import annotations

import functools
import secrets
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import yaml

from player.playlist import scan_playlist
from player.video_writer import (
    SUPPORTED_VIDEO_EXTENSIONS,
    UnsupportedVideoFormatError,
    add_video,
    remove_video,
)
from recognition.notifications import (
    RECOGNITIONS_FILENAME,
    initial_offset,
    read_new_events,
)
from recognition.registry import load_registry
from recognition.writer import NoFaceInImageError, _safe_name, add_person, remove_person

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config.yaml.example"
PLACEHOLDER_TOKEN = "PASTE_BOT_TOKEN_HERE"
BOT_LOG_STREAM = sys.stdout
PENDING_ADD_PERSON_KEY = "pending_add_person"
PENDING_ADD_VIDEO_KEY = "pending_add_video"
PENDING_SELF_SUBMIT_KEY = "pending_self_submit"
PENDING_APPROVALS_KEY = "pending_approvals"
TELEGRAM_VIDEO_MAX_BYTES = 20 * 1024 * 1024
VIDEO_MIME_TO_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}
RECOGNITION_POLL_INTERVAL_S = 2.0
LIST_MEDIA_LIMIT = 20


class BotConfigError(ValueError):
    """Raised when local bot configuration is incomplete."""


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def sanitize_secret(text: str, token: str | None) -> str:
    if not token:
        return text
    return text.replace(token, "<telegram_token>")


def parse_admin_chat_ids(raw_ids) -> set[int]:
    ids: set[int] = set()
    for raw in raw_ids or []:
        try:
            ids.add(int(str(raw).strip()))
        except ValueError as exc:
            raise BotConfigError("admin_chat_ids must contain only numeric Telegram chat IDs") from exc
    return ids


def _chat_id(update: Any) -> int | None:
    chat = getattr(update, "effective_chat", None)
    return getattr(chat, "id", None)


def _message(update: Any):
    return getattr(update, "effective_message", None)


def _command(update: Any) -> str:
    message = _message(update)
    text = getattr(message, "text", "") or ""
    first = text.strip().split(maxsplit=1)[0] if text.strip() else "<unknown>"
    return first.split("@", 1)[0]


def log_unauthorized(chat_id: int | None, command: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] UNAUTHORIZED chat_id={chat_id} command={command}", file=BOT_LOG_STREAM, flush=True)


def log_bot_event(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", file=BOT_LOG_STREAM, flush=True)


def _is_authorized(update: Any, context: Any) -> bool:
    chat_id = _chat_id(update)
    admin_ids = context.bot_data.get("admin_chat_ids", set())
    return chat_id in admin_ids


async def unauthorized_response(update: Any, context: Any) -> None:
    command = _command(update)
    chat_id = _chat_id(update)
    log_unauthorized(chat_id, command)
    message = _message(update)
    if message is not None:
        await message.reply_text("Unauthorized")


def admin_only(handler: Callable[[Any, Any], Awaitable[None]]):
    @functools.wraps(handler)
    async def wrapper(update: Any, context: Any) -> None:
        if not _is_authorized(update, context):
            await unauthorized_response(update, context)
            return
        await handler(update, context)

    return wrapper


def _main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 People", callback_data="menu:people"),
            InlineKeyboardButton("🎬 Videos", callback_data="menu:videos"),
        ],
        [InlineKeyboardButton("📊 Status", callback_data="menu:status")],
    ])


def _people_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add person", callback_data="action:add_person")],
        [InlineKeyboardButton("📋 List people", callback_data="action:list_people")],
        [InlineKeyboardButton("🗑 Delete person", callback_data="action:delete_person_pick")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])


def _videos_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add video", callback_data="action:add_video")],
        [InlineKeyboardButton("📋 List videos", callback_data="action:list_videos")],
        [InlineKeyboardButton("🗑 Delete video", callback_data="action:delete_video_pick")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:main")],
    ])


def _user_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Start registration", callback_data="user:join")],
    ])


def _user_cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cancel request", callback_data="user:cancel")],
    ])


def _delete_people_markup(names: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"🗑 {name}", callback_data=f"delete_person:{name}")] for name in names[:20]]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:people")])
    return InlineKeyboardMarkup(rows)


def _delete_videos_markup(filenames: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for fn in filenames[:20]:
        # Telegram callback_data has a 64-byte cap; truncate long names.
        cb_data = f"delete_video:{fn}"
        if len(cb_data.encode("utf-8")) > 64:
            continue  # fall through; admin can use /delete_video <name> typed
        rows.append([InlineKeyboardButton(f"🗑 {fn}", callback_data=cb_data)])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:videos")])
    return InlineKeyboardMarkup(rows)


def _face_photo_path(name: str, faces_folder: Path) -> Path | None:
    try:
        return Path(faces_folder) / f"{_safe_name(name)}.jpg"
    except ValueError:
        return None


async def _send_people_media_to_message(message: Any, registry: Any, faces_folder: Path) -> None:
    names = list(registry.names)
    limit = min(len(names), LIST_MEDIA_LIMIT)
    suffix = "" if len(names) <= LIST_MEDIA_LIMIT else f" Showing first {LIST_MEDIA_LIMIT}."
    await message.reply_text(f"Registered people: {len(names)}.{suffix}")
    for name in names[:limit]:
        photo_path = _face_photo_path(name, faces_folder)
        if photo_path is None or not photo_path.is_file():
            await message.reply_text(f"{name} (photo missing)")
            continue
        try:
            with photo_path.open("rb") as handle:
                await message.reply_photo(photo=handle, caption=name)
        except Exception as exc:
            log_bot_event(f"LIST_PEOPLE_PHOTO_ERROR name={name!r} error={type(exc).__name__}: {exc}")
            await message.reply_text(f"{name} (could not send photo)")


async def _send_people_media_to_chat(bot_client: Any, chat_id: int, registry: Any, faces_folder: Path) -> None:
    names = list(registry.names)
    limit = min(len(names), LIST_MEDIA_LIMIT)
    suffix = "" if len(names) <= LIST_MEDIA_LIMIT else f" Showing first {LIST_MEDIA_LIMIT}."
    await bot_client.send_message(chat_id=chat_id, text=f"Registered people: {len(names)}.{suffix}")
    for name in names[:limit]:
        photo_path = _face_photo_path(name, faces_folder)
        if photo_path is None or not photo_path.is_file():
            await bot_client.send_message(chat_id=chat_id, text=f"{name} (photo missing)")
            continue
        try:
            with photo_path.open("rb") as handle:
                await bot_client.send_photo(chat_id=chat_id, photo=handle, caption=name)
        except Exception as exc:
            log_bot_event(f"LIST_PEOPLE_PHOTO_ERROR name={name!r} error={type(exc).__name__}: {exc}")
            await bot_client.send_message(chat_id=chat_id, text=f"{name} (could not send photo)")


async def _send_videos_media_to_message(message: Any, entries: list[Path]) -> None:
    limit = min(len(entries), LIST_MEDIA_LIMIT)
    suffix = "" if len(entries) <= LIST_MEDIA_LIMIT else f" Showing first {LIST_MEDIA_LIMIT}."
    await message.reply_text(f"Playlist videos: {len(entries)}.{suffix}")
    for path in entries[:limit]:
        try:
            with path.open("rb") as handle:
                await message.reply_video(video=handle, caption=path.name)
        except Exception as exc:
            log_bot_event(f"LIST_VIDEO_SEND_ERROR name={path.name!r} error={type(exc).__name__}: {exc}")
            await message.reply_text(f"{path.name} (could not send video)")


async def _send_videos_media_to_chat(bot_client: Any, chat_id: int, entries: list[Path]) -> None:
    limit = min(len(entries), LIST_MEDIA_LIMIT)
    suffix = "" if len(entries) <= LIST_MEDIA_LIMIT else f" Showing first {LIST_MEDIA_LIMIT}."
    await bot_client.send_message(chat_id=chat_id, text=f"Playlist videos: {len(entries)}.{suffix}")
    for path in entries[:limit]:
        try:
            with path.open("rb") as handle:
                await bot_client.send_video(chat_id=chat_id, video=handle, caption=path.name)
        except Exception as exc:
            log_bot_event(f"LIST_VIDEO_SEND_ERROR name={path.name!r} error={type(exc).__name__}: {exc}")
            await bot_client.send_message(chat_id=chat_id, text=f"{path.name} (could not send video)")


async def start_command(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    if _is_authorized(update, context):
        await message.reply_text("Welcome admin", reply_markup=_main_menu_markup())
    else:
        await message.reply_text(
            "Welcome. Tap the button to send your name and photo for admin approval.",
            reply_markup=_user_menu_markup(),
        )


def _pending_add_person(context: Any) -> dict:
    return context.bot_data.setdefault(PENDING_ADD_PERSON_KEY, {})


def _pending_self_submit(context: Any) -> dict:
    return context.bot_data.setdefault(PENDING_SELF_SUBMIT_KEY, {})


def _pending_approvals(context: Any) -> dict:
    return context.bot_data.setdefault(PENDING_APPROVALS_KEY, {})


def _approval_markup(submission_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"self_approve:{submission_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"self_reject:{submission_id}"),
        ]
    ])


def _registered_name_for_chat_id(context: Any, chat_id: int | None) -> str | None:
    if chat_id is None:
        return None
    people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
    try:
        registry = load_registry(people_db_path)
    except Exception as exc:
        log_bot_event(f"SELF_REGISTER_REGISTRY_CHECK_ERROR chat_id={chat_id} error={type(exc).__name__}: {exc}")
        return None
    needle = str(chat_id)
    for idx, name in enumerate(registry.names):
        if idx < len(registry.telegram_chat_ids) and registry.telegram_chat_ids[idx] == needle:
            return name
    return None


async def _replace_callback_message(query: Any, text: str, reply_markup=None) -> None:
    """Replace the callback message whether it is text or a photo caption."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    except Exception as exc:
        log_bot_event(f"CALLBACK_EDIT_TEXT_FALLBACK error={type(exc).__name__}: {exc}")
    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup)
        return
    except Exception as exc:
        log_bot_event(f"CALLBACK_EDIT_CAPTION_FALLBACK error={type(exc).__name__}: {exc}")
    message = getattr(query, "message", None)
    if message is not None:
        try:
            await message.reply_text(text, reply_markup=reply_markup)
        except Exception as exc:
            log_bot_event(f"CALLBACK_REPLY_FALLBACK_ERROR error={type(exc).__name__}: {exc}")


async def self_register_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    registered_name = _registered_name_for_chat_id(context, chat_id)
    message = _message(update)
    if registered_name:
        if message is not None:
            await message.reply_text(
                f"You are already registered as {registered_name}. Ask an admin to delete you before registering again."
            )
        return
    if chat_id is not None:
        _pending_self_submit(context)[chat_id] = {"step": "name"}
        log_bot_event(f"SELF_REGISTER_START chat_id={chat_id}")
    if message is not None:
        await message.reply_text(
            "Send your name, then a clear front-facing photo.",
            reply_markup=_user_cancel_markup(),
        )


async def add_person_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    if chat_id is not None:
        _pending_add_person(context)[chat_id] = {"step": "name"}
        log_bot_event(f"ADD_PERSON_START chat_id={chat_id}")
    message = _message(update)
    if message is not None:
        await message.reply_text("Send me a name, then a photo")


async def handle_text_message(update: Any, context: Any) -> None:
    if not _is_authorized(update, context):
        chat_id = _chat_id(update)
        state = _pending_self_submit(context).get(chat_id)
        message = _message(update)
        registered_name = _registered_name_for_chat_id(context, chat_id)
        if registered_name:
            _pending_self_submit(context).pop(chat_id, None)
            if message is not None:
                await message.reply_text(
                    f"You are already registered as {registered_name}. Ask an admin to delete you before registering again."
                )
            return
        if not state:
            if message is not None:
                await message.reply_text("Use /join to request registration.")
            return
        if state.get("step") == "photo":
            if message is not None:
                await message.reply_text(
                    "Send a clear front-facing photo.",
                    reply_markup=_user_cancel_markup(),
                )
            return
        name = (getattr(message, "text", "") or "").strip()
        if not name:
            if message is not None:
                await message.reply_text("Send your name.")
            return
        _pending_self_submit(context)[chat_id] = {"step": "photo", "name": name}
        log_bot_event(f"SELF_REGISTER_NAME chat_id={chat_id} name={name!r}")
        if message is not None:
            await message.reply_text(
                "Send a clear front-facing photo.",
                reply_markup=_user_cancel_markup(),
            )
        return
    chat_id = _chat_id(update)
    pending = _pending_add_person(context)
    state = pending.get(chat_id)
    message = _message(update)
    if not state or state.get("step") != "name":
        if state and state.get("step") == "photo" and message is not None:
            await message.reply_text("Send me a photo")
        return
    name = (getattr(message, "text", "") or "").strip()
    if not name:
        if message is not None:
            await message.reply_text("Send me a name")
        return
    pending[chat_id] = {"step": "photo", "name": name}
    log_bot_event(f"ADD_PERSON_NAME chat_id={chat_id} name={name!r}")
    if message is not None:
        await message.reply_text("Send me a photo")


def _largest_photo(message: Any):
    photos = list(getattr(message, "photo", []) or [])
    if not photos:
        return None
    return max(photos, key=lambda item: getattr(item, "width", 0) * getattr(item, "height", 0))


async def handle_photo_message(update: Any, context: Any) -> None:
    if not _is_authorized(update, context):
        await _handle_self_submit_photo(update, context)
        return
    chat_id = _chat_id(update)
    pending = _pending_add_person(context)
    state = pending.get(chat_id)
    if not state or state.get("step") != "photo":
        if message := _message(update):
            await message.reply_text("Use /add_person first")
        return

    name = state["name"]
    message = _message(update)
    photo = _largest_photo(message)
    if photo is None:
        return

    people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
    faces_folder = Path(context.bot_data.get("faces_folder", "faces"))

    with tempfile.TemporaryDirectory(prefix="add-person-") as tmp:
        photo_path = Path(tmp) / f"{getattr(photo, 'file_id', 'photo')}.jpg"
        if message is not None:
            await message.reply_text("Photo received. Processing...")
        try:
            log_bot_event(f"ADD_PERSON_PHOTO chat_id={chat_id} name={name!r} file_id={photo.file_id}")
            telegram_file = await context.bot.get_file(photo.file_id)
            await telegram_file.download_to_drive(photo_path)
            add_person(name, photo_path, people_db_path, faces_folder)
        except NoFaceInImageError:
            pending.pop(chat_id, None)
            log_bot_event(f"ADD_PERSON_NO_FACE chat_id={chat_id} name={name!r}")
            if message is not None:
                await message.reply_text("No face detected in that photo. Please try a clearer front-facing photo.")
            return
        except ValueError as exc:
            pending.pop(chat_id, None)
            log_bot_event(f"ADD_PERSON_IMAGE_ERROR chat_id={chat_id} name={name!r} error={exc}")
            if message is not None:
                await message.reply_text("Could not add that photo. Please try a clearer front-facing photo.")
            return
        except Exception as exc:
            pending.pop(chat_id, None)
            log_bot_event(f"ADD_PERSON_ERROR chat_id={chat_id} name={name!r} error={type(exc).__name__}: {exc}")
            if message is not None:
                await message.reply_text("Something went wrong while adding that person. Please try again.")
            return

    pending.pop(chat_id, None)
    log_bot_event(f"ADD_PERSON_ADDED chat_id={chat_id} name={name!r}")
    if message is not None:
        await message.reply_text(f"{name} added")


async def _handle_self_submit_photo(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    registered_name = _registered_name_for_chat_id(context, chat_id)
    pending = _pending_self_submit(context)
    state = pending.get(chat_id)
    message = _message(update)
    if registered_name:
        pending.pop(chat_id, None)
        if message is not None:
            await message.reply_text(
                f"You are already registered as {registered_name}. Ask an admin to delete you before registering again."
            )
        return
    if not state or state.get("step") != "photo":
        if message is not None:
            await message.reply_text("Use /join first.")
        return

    photo = _largest_photo(message)
    if photo is None:
        return

    pending_folder = Path(context.bot_data.get("pending_submissions_folder", "pending_submissions"))
    pending_folder.mkdir(parents=True, exist_ok=True)
    submission_id = secrets.token_hex(4)
    photo_path = pending_folder / f"{submission_id}.jpg"
    name = state["name"]

    if message is not None:
        await message.reply_text("Photo received. Waiting for admin approval.")
    try:
        telegram_file = await context.bot.get_file(photo.file_id)
        await telegram_file.download_to_drive(photo_path)
    except Exception as exc:
        pending.pop(chat_id, None)
        log_bot_event(f"SELF_REGISTER_DOWNLOAD_ERROR chat_id={chat_id} error={type(exc).__name__}: {exc}")
        if message is not None:
            await message.reply_text("Could not receive that photo. Please try again.")
        return

    _pending_approvals(context)[submission_id] = {
        "chat_id": chat_id,
        "name": name,
        "photo_path": str(photo_path),
    }
    pending.pop(chat_id, None)
    admin_ids: set[int] = context.bot_data.get("admin_chat_ids", set())
    caption = f"Registration request\nName: {name}\nChat ID: {chat_id}"
    for admin_id in admin_ids:
        try:
            with photo_path.open("rb") as handle:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=handle,
                    caption=caption,
                    reply_markup=_approval_markup(submission_id),
                )
        except Exception as exc:
            log_bot_event(f"SELF_REGISTER_NOTIFY_ERROR admin_chat_id={admin_id} error={type(exc).__name__}: {exc}")
    log_bot_event(f"SELF_REGISTER_SUBMITTED chat_id={chat_id} id={submission_id} name={name!r}")


async def list_people_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
    registry = load_registry(people_db_path)
    log_bot_event(f"LIST_PEOPLE chat_id={chat_id} count={len(registry.names)}")
    message = _message(update)
    if message is None:
        return
    if not registry.names:
        await message.reply_text("No people registered yet. Use /add_person to add someone.")
        return
    faces_folder = Path(context.bot_data.get("faces_folder", "faces"))
    await _send_people_media_to_message(message, registry, faces_folder)


async def delete_person_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    message = _message(update)
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split(maxsplit=1)
    name = parts[1].strip() if len(parts) > 1 else ""

    if not name:
        log_bot_event(f"DELETE_PERSON_USAGE chat_id={chat_id}")
        if message is not None:
            await message.reply_text("Usage: /delete_person <name>")
        return

    people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
    faces_folder = Path(context.bot_data.get("faces_folder", "faces"))
    log_bot_event(f"DELETE_PERSON_START chat_id={chat_id} name={name!r}")

    registry = load_registry(people_db_path)
    if name not in registry.names:
        log_bot_event(f"DELETE_PERSON_NOT_FOUND chat_id={chat_id} name={name!r}")
        if message is not None:
            await message.reply_text("Person not found. Use /list_people to see who is registered.")
        return

    removed = remove_person(name, people_db_path, faces_folder)
    if removed:
        log_bot_event(f"DELETE_PERSON_REMOVED chat_id={chat_id} name={name!r}")
        if message is not None:
            await message.reply_text(f"{name} removed")
    else:
        log_bot_event(f"DELETE_PERSON_NOT_FOUND chat_id={chat_id} name={name!r}")
        if message is not None:
            await message.reply_text("Person not found. Use /list_people to see who is registered.")


def _pending_add_video(context: Any) -> dict:
    return context.bot_data.setdefault(PENDING_ADD_VIDEO_KEY, {})


async def add_video_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    if chat_id is not None:
        _pending_add_video(context)[chat_id] = True
        log_bot_event(f"ADD_VIDEO_START chat_id={chat_id}")
    message = _message(update)
    if message is not None:
        await message.reply_text("Send me the video file")


async def handle_video_message(update: Any, context: Any) -> None:
    if not _is_authorized(update, context):
        await unauthorized_response(update, context)
        return
    chat_id = _chat_id(update)
    pending = _pending_add_video(context)
    message = _message(update)
    if not pending.get(chat_id):
        if message is not None:
            await message.reply_text("Use /add_video first")
        return

    video = getattr(message, "video", None)
    if video is None:
        return

    file_size = int(getattr(video, "file_size", 0) or 0)
    if file_size > TELEGRAM_VIDEO_MAX_BYTES:
        pending.pop(chat_id, None)
        log_bot_event(f"ADD_VIDEO_TOO_LARGE chat_id={chat_id} size={file_size}")
        if message is not None:
            await message.reply_text(
                "This video is over 20 MB. Please upload it via add_video.py on the laptop."
            )
        return

    file_name = getattr(video, "file_name", None) or ""
    mime_type = (getattr(video, "mime_type", None) or "").lower()
    filename = Path(file_name).name.strip() if file_name else ""
    if not filename:
        fallback_suffix = VIDEO_MIME_TO_EXT.get(mime_type, "")
        if fallback_suffix:
            filename = f"{video.file_id}{fallback_suffix}"
    suffix = Path(filename).suffix.lower() if filename else ""
    if not filename or suffix not in SUPPORTED_VIDEO_EXTENSIONS:
        pending.pop(chat_id, None)
        log_bot_event(
            f"ADD_VIDEO_BAD_FORMAT chat_id={chat_id} name={file_name!r} mime={mime_type!r}"
        )
        if message is not None:
            await message.reply_text(
                "That file format is not supported. Please use .mp4, .mov, or .webm."
            )
        return

    video_folder = Path(context.bot_data.get("video_folder", "videos"))

    if message is not None:
        await message.reply_text("Video received. Processing...")

    with tempfile.TemporaryDirectory(prefix="add-video-") as tmp:
        tmp_path = Path(tmp) / filename
        try:
            log_bot_event(
                f"ADD_VIDEO_DOWNLOAD chat_id={chat_id} name={filename!r} "
                f"file_id={video.file_id} size={file_size}"
            )
            telegram_file = await context.bot.get_file(video.file_id)
            await telegram_file.download_to_drive(tmp_path)
            add_video(tmp_path, video_folder)
        except UnsupportedVideoFormatError:
            pending.pop(chat_id, None)
            log_bot_event(f"ADD_VIDEO_BAD_FORMAT chat_id={chat_id} name={filename!r}")
            if message is not None:
                await message.reply_text(
                    "That file format is not supported. Please use .mp4, .mov, or .webm."
                )
            return
        except Exception as exc:
            pending.pop(chat_id, None)
            log_bot_event(
                f"ADD_VIDEO_ERROR chat_id={chat_id} name={filename!r} "
                f"error={type(exc).__name__}: {exc}"
            )
            if message is not None:
                await message.reply_text(
                    "Something went wrong while adding that video. Please try again."
                )
            return

    pending.pop(chat_id, None)
    count = len(scan_playlist(video_folder))
    log_bot_event(f"ADD_VIDEO_ADDED chat_id={chat_id} name={filename!r} count={count}")
    if message is not None:
        await message.reply_text(f"{filename} added. Playlist now has {count} videos")


async def list_videos_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    video_folder = Path(context.bot_data.get("video_folder", "videos"))
    entries = scan_playlist(video_folder)
    log_bot_event(f"LIST_VIDEOS chat_id={chat_id} count={len(entries)}")
    message = _message(update)
    if message is None:
        return
    if not entries:
        await message.reply_text("No videos in playlist yet. Use /add_video to add one.")
        return
    await _send_videos_media_to_message(message, entries)


async def delete_video_command(update: Any, context: Any) -> None:
    chat_id = _chat_id(update)
    message = _message(update)
    text = (getattr(message, "text", "") or "").strip()
    parts = text.split(maxsplit=1)
    filename = parts[1].strip() if len(parts) > 1 else ""

    if not filename:
        log_bot_event(f"DELETE_VIDEO_USAGE chat_id={chat_id}")
        if message is not None:
            await message.reply_text("Usage: /delete_video <filename>")
        return

    video_folder = Path(context.bot_data.get("video_folder", "videos"))
    log_bot_event(f"DELETE_VIDEO_START chat_id={chat_id} name={filename!r}")

    removed = remove_video(filename, video_folder)
    if not removed:
        log_bot_event(f"DELETE_VIDEO_NOT_FOUND chat_id={chat_id} name={filename!r}")
        if message is not None:
            await message.reply_text(
                "Video not found. Use /list_videos to see what is in the playlist."
            )
        return

    count = len(scan_playlist(video_folder))
    log_bot_event(f"DELETE_VIDEO_REMOVED chat_id={chat_id} name={filename!r} count={count}")
    if message is not None:
        await message.reply_text(f"{filename} removed. Playlist now has {count} videos")


async def handle_menu_callback(update: Any, context: Any) -> None:
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    chat_id = _chat_id(update)
    data = (getattr(query, "data", "") or "").strip()

    if data == "user:join":
        try:
            await query.answer()
        except Exception:
            pass
        registered_name = _registered_name_for_chat_id(context, chat_id)
        if registered_name:
            await query.edit_message_text(
                f"You are already registered as {registered_name}. Ask an admin to delete you before registering again.",
                reply_markup=_user_menu_markup(),
            )
            return
        if chat_id is not None:
            _pending_self_submit(context)[chat_id] = {"step": "name"}
            log_bot_event(f"SELF_REGISTER_START chat_id={chat_id}")
        await query.edit_message_text(
            "Send your name, then a clear front-facing photo.",
            reply_markup=_user_cancel_markup(),
        )
        return

    if data == "user:cancel":
        try:
            await query.answer()
        except Exception:
            pass
        if chat_id is not None:
            _pending_self_submit(context).pop(chat_id, None)
        await query.edit_message_text(
            "Registration cancelled. Tap Start registration when you are ready.",
            reply_markup=_user_menu_markup(),
        )
        return

    admin_ids = context.bot_data.get("admin_chat_ids", set())
    if chat_id not in admin_ids:
        log_unauthorized(chat_id, getattr(query, "data", "<callback>"))
        try:
            await query.answer("Unauthorized")
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass

    if data.startswith("self_approve:") or data.startswith("self_reject:"):
        action, submission_id = data.split(":", 1)
        approvals = _pending_approvals(context)
        submission = approvals.pop(submission_id, None)
        if not submission:
            await _replace_callback_message(query, "Registration request is no longer available.")
            return

        user_chat_id = int(submission["chat_id"])
        name = str(submission["name"])
        photo_path = Path(submission["photo_path"])
        if action == "self_reject":
            photo_path.unlink(missing_ok=True)
            log_bot_event(f"SELF_REGISTER_REJECTED admin_chat_id={chat_id} request_chat_id={user_chat_id} name={name!r}")
            await _replace_callback_message(query, f"❌ {name} rejected.")
            try:
                await context.bot.send_message(chat_id=user_chat_id, text="Your registration request was not approved.")
            except Exception as exc:
                log_bot_event(f"SELF_REGISTER_USER_NOTIFY_ERROR chat_id={user_chat_id} error={type(exc).__name__}: {exc}")
            return

        people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
        faces_folder = Path(context.bot_data.get("faces_folder", "faces"))
        try:
            add_person(
                name,
                photo_path,
                people_db_path,
                faces_folder,
                telegram_chat_id=user_chat_id,
            )
        except NoFaceInImageError:
            log_bot_event(f"SELF_REGISTER_NO_FACE admin_chat_id={chat_id} request_chat_id={user_chat_id} name={name!r}")
            await _replace_callback_message(query, "No face detected in that request photo.")
            try:
                await context.bot.send_message(chat_id=user_chat_id, text="No face was detected in your photo. Use /join to try again.")
            except Exception:
                pass
            return
        except Exception as exc:
            log_bot_event(f"SELF_REGISTER_APPROVE_ERROR admin_chat_id={chat_id} request_chat_id={user_chat_id} error={type(exc).__name__}: {exc}")
            await _replace_callback_message(query, "Could not approve that registration request.")
            return
        finally:
            photo_path.unlink(missing_ok=True)

        log_bot_event(f"SELF_REGISTER_APPROVED admin_chat_id={chat_id} request_chat_id={user_chat_id} name={name!r}")
        await _replace_callback_message(query, f"✅ {name} approved and added.")
        try:
            await context.bot.send_message(chat_id=user_chat_id, text="Your registration was approved.")
        except Exception as exc:
            log_bot_event(f"SELF_REGISTER_USER_NOTIFY_ERROR chat_id={user_chat_id} error={type(exc).__name__}: {exc}")
        return

    if data == "menu:main":
        await query.edit_message_text("Main menu", reply_markup=_main_menu_markup())
        return
    if data == "menu:people":
        await query.edit_message_text("People menu", reply_markup=_people_menu_markup())
        return
    if data == "menu:videos":
        await query.edit_message_text("Videos menu", reply_markup=_videos_menu_markup())
        return
    if data == "menu:status":
        started_at = context.bot_data.get("started_at", time.time())
        uptime_s = int(time.time() - started_at)
        greetings = int(context.bot_data.get("greetings_count", 0))
        text = (
            f"Uptime: {uptime_s // 3600}h {(uptime_s % 3600) // 60}m\n"
            f"Greetings since boot: {greetings}"
        )
        await query.edit_message_text(text, reply_markup=_main_menu_markup())
        return

    if data == "action:add_person":
        _pending_add_person(context)[chat_id] = {"step": "name"}
        log_bot_event(f"ADD_PERSON_START chat_id={chat_id}")
        await query.edit_message_text("Send me a name, then a photo")
        return
    if data == "action:list_people":
        people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
        faces_folder = Path(context.bot_data.get("faces_folder", "faces"))
        registry = load_registry(people_db_path)
        if not registry.names:
            text = "No people registered yet. Use /add_person to add someone."
            await query.edit_message_text(text, reply_markup=_people_menu_markup())
        else:
            await query.edit_message_text("Sending registered people...", reply_markup=_people_menu_markup())
            if chat_id is not None:
                await _send_people_media_to_chat(context.bot, chat_id, registry, faces_folder)
        return
    if data == "action:delete_person_pick":
        people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
        registry = load_registry(people_db_path)
        if not registry.names:
            await query.edit_message_text(
                "No people registered yet.", reply_markup=_people_menu_markup()
            )
            return
        await query.edit_message_text(
            "Pick a person to remove:",
            reply_markup=_delete_people_markup(list(registry.names)),
        )
        return
    if data == "action:add_video":
        _pending_add_video(context)[chat_id] = True
        log_bot_event(f"ADD_VIDEO_START chat_id={chat_id}")
        await query.edit_message_text("Send me the video file")
        return
    if data == "action:list_videos":
        video_folder = Path(context.bot_data.get("video_folder", "videos"))
        entries = scan_playlist(video_folder)
        if not entries:
            text = "No videos in playlist yet. Use /add_video to add one."
            await query.edit_message_text(text, reply_markup=_videos_menu_markup())
        else:
            await query.edit_message_text("Sending playlist videos...", reply_markup=_videos_menu_markup())
            if chat_id is not None:
                await _send_videos_media_to_chat(context.bot, chat_id, entries)
        return
    if data == "action:delete_video_pick":
        video_folder = Path(context.bot_data.get("video_folder", "videos"))
        entries = scan_playlist(video_folder)
        if not entries:
            await query.edit_message_text(
                "No videos in playlist yet.", reply_markup=_videos_menu_markup()
            )
            return
        await query.edit_message_text(
            "Pick a video to remove:",
            reply_markup=_delete_videos_markup([p.name for p in entries]),
        )
        return

    if data.startswith("delete_person:"):
        name = data[len("delete_person:"):]
        people_db_path = Path(context.bot_data.get("people_db_path", "people.json"))
        faces_folder = Path(context.bot_data.get("faces_folder", "faces"))
        registry = load_registry(people_db_path)
        if name not in registry.names:
            log_bot_event(f"DELETE_PERSON_NOT_FOUND chat_id={chat_id} name={name!r}")
            await query.edit_message_text(
                "Person not found. Use /list_people to see who is registered.",
                reply_markup=_people_menu_markup(),
            )
            return
        removed = remove_person(name, people_db_path, faces_folder)
        if removed:
            log_bot_event(f"DELETE_PERSON_REMOVED chat_id={chat_id} name={name!r}")
            await query.edit_message_text(
                f"{name} removed", reply_markup=_people_menu_markup()
            )
        else:
            await query.edit_message_text(
                "Person not found. Use /list_people to see who is registered.",
                reply_markup=_people_menu_markup(),
            )
        return

    if data.startswith("delete_video:"):
        filename = data[len("delete_video:"):]
        video_folder = Path(context.bot_data.get("video_folder", "videos"))
        removed = remove_video(filename, video_folder)
        if removed:
            count = len(scan_playlist(video_folder))
            log_bot_event(f"DELETE_VIDEO_REMOVED chat_id={chat_id} name={filename!r} count={count}")
            await query.edit_message_text(
                f"{filename} removed. Playlist now has {count} videos",
                reply_markup=_videos_menu_markup(),
            )
        else:
            await query.edit_message_text(
                "Video not found. Use /list_videos to see what is in the playlist.",
                reply_markup=_videos_menu_markup(),
            )
        return


async def quiet_command(update: Any, context: Any) -> None:
    context.bot_data["notify_enabled"] = False
    log_bot_event("NOTIFY_DISABLED")
    message = _message(update)
    if message is not None:
        await message.reply_text("Notifications muted.")


async def unquiet_command(update: Any, context: Any) -> None:
    context.bot_data["notify_enabled"] = True
    log_bot_event("NOTIFY_ENABLED")
    message = _message(update)
    if message is not None:
        await message.reply_text("Notifications resumed.")


def _format_recognition_text(event: dict) -> str:
    name = str(event.get("name", "?"))
    ts = float(event.get("timestamp", 0) or 0)
    hhmm = time.strftime("%H:%M", time.localtime(ts)) if ts else "??:??"
    return f"🎯 {name} recognized at {hhmm}"


async def poll_recognitions(context: Any) -> None:
    """JobQueue callback — read new recognition events, push to admin chats."""
    bot_data = context.bot_data
    if not bot_data.get("notify_enabled", True):
        return
    path = Path(bot_data.get("recognitions_log_path", "logs/recognitions.jsonl"))
    last_offset = int(bot_data.get("recognitions_offset", 0))
    events, new_offset = read_new_events(path, last_offset)
    bot_data["recognitions_offset"] = new_offset
    if not events:
        return
    admin_ids: set[int] = bot_data.get("admin_chat_ids", set())
    if not admin_ids:
        return
    for event in events:
        text = _format_recognition_text(event)
        for chat_id in admin_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception as exc:
                log_bot_event(f"NOTIFY_SEND_ERROR chat_id={chat_id} error={type(exc).__name__}: {exc}")
        bot_data["greetings_count"] = int(bot_data.get("greetings_count", 0)) + 1


async def unknown_command(update: Any, context: Any) -> None:
    if not _is_authorized(update, context):
        await unauthorized_response(update, context)
        return
    message = _message(update)
    if message is not None:
        await message.reply_text("Command not available yet")


async def _ready_log(application: Any) -> None:
    user = await application.bot.get_me()
    username = getattr(user, "username", None) or "<unknown>"
    print(f"BOT_READY username=@{username}", flush=True)


def build_application(config: dict):
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    token = str(config.get("telegram_token", "")).strip()
    if not token or token == PLACEHOLDER_TOKEN:
        raise BotConfigError("telegram_token is missing in config.yaml")
    admin_chat_ids = parse_admin_chat_ids(config.get("admin_chat_ids", []))

    application = Application.builder().token(token).post_init(_ready_log).build()
    application.bot_data["admin_chat_ids"] = admin_chat_ids
    application.bot_data[PENDING_ADD_PERSON_KEY] = {}
    application.bot_data[PENDING_ADD_VIDEO_KEY] = {}
    application.bot_data[PENDING_SELF_SUBMIT_KEY] = {}
    application.bot_data[PENDING_APPROVALS_KEY] = {}
    application.bot_data["people_db_path"] = Path(config.get("people_db_path", "people.json"))
    application.bot_data["faces_folder"] = Path(config.get("faces_folder", "faces"))
    application.bot_data["pending_submissions_folder"] = Path(
        config.get("pending_submissions_folder", "pending_submissions")
    )
    application.bot_data["video_folder"] = Path(config.get("video_folder", "videos"))
    application.bot_data["started_at"] = time.time()
    application.bot_data["greetings_count"] = 0
    application.bot_data["notify_enabled"] = True
    log_dir = Path(config.get("log_directory", "logs"))
    recognitions_log = log_dir / RECOGNITIONS_FILENAME
    application.bot_data["recognitions_log_path"] = recognitions_log
    application.bot_data["recognitions_offset"] = initial_offset(recognitions_log)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("join", self_register_command))
    application.add_handler(CommandHandler("register", self_register_command))
    application.add_handler(CommandHandler("add_person", admin_only(add_person_command)))
    application.add_handler(CommandHandler("list_people", admin_only(list_people_command)))
    application.add_handler(CommandHandler("delete_person", admin_only(delete_person_command)))
    application.add_handler(CommandHandler("add_video", admin_only(add_video_command)))
    application.add_handler(CommandHandler("list_videos", admin_only(list_videos_command)))
    application.add_handler(CommandHandler("delete_video", admin_only(delete_video_command)))
    application.add_handler(CommandHandler("quiet", admin_only(quiet_command)))
    application.add_handler(CommandHandler("unquiet", admin_only(unquiet_command)))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(handle_menu_callback))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    job_queue = getattr(application, "job_queue", None)
    if job_queue is not None:
        job_queue.run_repeating(
            poll_recognitions,
            interval=RECOGNITION_POLL_INTERVAL_S,
            first=RECOGNITION_POLL_INTERVAL_S,
            name="poll-recognitions",
        )
    else:
        log_bot_event(
            'NOTIFY_JOBQUEUE_MISSING install python-telegram-bot[job-queue] to enable recognition notifications'
        )

    return application


def run_bot(config: dict) -> int:
    application = build_application(config)
    if not application.bot_data.get("admin_chat_ids"):
        print("BOT_WARNING admin_chat_ids empty; all commands will be unauthorized", flush=True)
    print("BOT_STARTING", flush=True)
    application.run_polling()
    return 0


def main() -> int:
    config = load_config()
    token = str(config.get("telegram_token", "")).strip()
    try:
        return run_bot(config)
    except Exception as exc:
        safe = sanitize_secret(str(exc), token)
        print(f"BOT_ERROR {type(exc).__name__}: {safe}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
