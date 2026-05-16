"""Tests for the Telegram inline-keyboard menus (Story 5.5)."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot


def _write_people_json(path: Path, names: list[str]) -> None:
    payload = {"people": [{"name": n, "encoding": [0.0] * 128} for n in names]}
    path.write_text(json.dumps(payload), encoding="utf-8")


class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[tuple[str, object]] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:
        self.replies.append((text, reply_markup))


class _FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class _FakeQuery:
    def __init__(self, chat_id: int, data: str) -> None:
        self.data = data
        self.answers: list[str] = []
        self.edits: list[tuple[str, object]] = []
        self.message = _FakeMessage()
        self.from_user = mock.Mock(id=chat_id)

    async def answer(self, text: str | None = None) -> None:
        self.answers.append(text or "")

    async def edit_message_text(self, text: str, reply_markup=None) -> None:
        self.edits.append((text, reply_markup))


class _FakeUpdate:
    def __init__(self, chat_id: int, callback_data: str | None = None) -> None:
        self.effective_chat = _FakeChat(chat_id)
        self.effective_message = _FakeMessage()
        self.callback_query = _FakeQuery(chat_id, callback_data) if callback_data else None


class MenuMarkupTests(unittest.TestCase):
    def test_main_menu_has_three_buttons(self) -> None:
        markup = bot._main_menu_markup()
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertEqual(set(flat), {"menu:people", "menu:videos", "menu:status"})

    def test_people_menu_has_back(self) -> None:
        markup = bot._people_menu_markup()
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertIn("menu:main", flat)
        self.assertIn("action:add_person", flat)
        self.assertIn("action:list_people", flat)
        self.assertIn("action:delete_person_pick", flat)

    def test_videos_menu_has_back(self) -> None:
        markup = bot._videos_menu_markup()
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertIn("menu:main", flat)
        self.assertIn("action:add_video", flat)

    def test_delete_people_markup_includes_back(self) -> None:
        markup = bot._delete_people_markup(["Alice", "Bob"])
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertIn("delete_person:Alice", flat)
        self.assertIn("delete_person:Bob", flat)
        self.assertIn("menu:people", flat)

    def test_user_menu_starts_registration(self) -> None:
        markup = bot._user_menu_markup()
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertEqual(flat, ["user:join"])


class CallbackDispatchTests(unittest.TestCase):
    def _context(self, chat_id: int, **bot_data):
        ctx = mock.Mock()
        ctx.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "pending_add_video": {},
            "people_db_path": Path("people.json"),
            "faces_folder": Path("faces"),
            "video_folder": Path("videos"),
            "started_at": 0,
            "greetings_count": 0,
            **bot_data,
        }
        ctx.bot = mock.AsyncMock()
        return ctx

    def test_unauthorized_callback_does_not_dispatch(self) -> None:
        update = _FakeUpdate(999, callback_data="menu:people")
        context = self._context(123)
        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
            asyncio.run(bot.handle_menu_callback(update, context))
        self.assertEqual(update.callback_query.edits, [])
        self.assertIn("Unauthorized", update.callback_query.answers[0])

    def test_user_join_callback_starts_self_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            update = _FakeUpdate(999, callback_data="user:join")
            context = self._context(
                123,
                pending_self_submit={},
                people_db_path=Path(tmp) / "people.json",
            )
            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_menu_callback(update, context))

            self.assertEqual(context.bot_data["pending_self_submit"][999], {"step": "name"})
            text, markup = update.callback_query.edits[0]
            self.assertIn("Send your name", text)
            flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
            self.assertEqual(flat, ["user:cancel"])

    def test_user_cancel_callback_clears_self_registration(self) -> None:
        update = _FakeUpdate(999, callback_data="user:cancel")
        context = self._context(123, pending_self_submit={999: {"step": "photo", "name": "Aziza"}})

        asyncio.run(bot.handle_menu_callback(update, context))

        self.assertEqual(context.bot_data["pending_self_submit"], {})
        text, markup = update.callback_query.edits[0]
        self.assertIn("cancelled", text)
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertEqual(flat, ["user:join"])

    def test_menu_people_edits_to_people_menu(self) -> None:
        update = _FakeUpdate(123, callback_data="menu:people")
        context = self._context(123)
        asyncio.run(bot.handle_menu_callback(update, context))
        self.assertEqual(len(update.callback_query.edits), 1)
        text, markup = update.callback_query.edits[0]
        self.assertEqual(text, "People menu")
        flat = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertIn("action:add_person", flat)

    def test_action_add_person_sets_pending_state(self) -> None:
        update = _FakeUpdate(123, callback_data="action:add_person")
        context = self._context(123)
        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
            asyncio.run(bot.handle_menu_callback(update, context))
        self.assertEqual(context.bot_data["pending_add_person"][123], {"step": "name"})
        self.assertEqual(update.callback_query.edits[0][0], "Send me a name, then a photo")

    def test_action_list_people_with_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            faces = Path(tmp) / "faces"
            faces.mkdir()
            _write_people_json(people_db, ["Alice", "Bob"])
            (faces / "alice.jpg").write_bytes(b"jpg")
            (faces / "bob.jpg").write_bytes(b"jpg")
            update = _FakeUpdate(123, callback_data="action:list_people")
            context = self._context(123, people_db_path=people_db, faces_folder=faces)
            asyncio.run(bot.handle_menu_callback(update, context))
            self.assertEqual(update.callback_query.edits[0][0], "Sending registered people...")
            context.bot.send_message.assert_awaited_once_with(chat_id=123, text="Registered people: 2.")
            captions = [call.kwargs["caption"] for call in context.bot.send_photo.await_args_list]
            self.assertEqual(captions, ["Alice", "Bob"])

    def test_delete_person_pick_calls_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            _write_people_json(people_db, ["Alice"])
            update = _FakeUpdate(123, callback_data="delete_person:Alice")
            context = self._context(123, people_db_path=people_db, faces_folder=Path(tmp) / "faces")

            with mock.patch.object(bot, "remove_person", return_value=True) as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_menu_callback(update, context))

            writer.assert_called_once()
            self.assertEqual(update.callback_query.edits[0][0], "Alice removed")

    def test_action_list_videos_with_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "promo.mp4").write_bytes(b"x")
            update = _FakeUpdate(123, callback_data="action:list_videos")
            context = self._context(123, video_folder=video_folder)
            asyncio.run(bot.handle_menu_callback(update, context))
            self.assertEqual(update.callback_query.edits[0][0], "Sending playlist videos...")
            context.bot.send_message.assert_awaited_once_with(chat_id=123, text="Playlist videos: 1.")
            context.bot.send_video.assert_awaited_once()
            self.assertEqual(context.bot.send_video.await_args.kwargs["caption"], "promo.mp4")

    def test_delete_video_callback_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "promo.mp4").write_bytes(b"x")
            update = _FakeUpdate(123, callback_data="delete_video:promo.mp4")
            context = self._context(123, video_folder=video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_menu_callback(update, context))

            self.assertFalse((video_folder / "promo.mp4").exists())
            self.assertIn("promo.mp4 removed", update.callback_query.edits[0][0])

    def test_menu_status_shows_uptime_and_counter(self) -> None:
        update = _FakeUpdate(123, callback_data="menu:status")
        context = self._context(123, started_at=0, greetings_count=5)
        asyncio.run(bot.handle_menu_callback(update, context))
        text = update.callback_query.edits[0][0]
        self.assertIn("Greetings since boot: 5", text)


if __name__ == "__main__":
    unittest.main()
