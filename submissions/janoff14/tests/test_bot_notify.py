"""Tests for the bot's recognition-notification path (Story 5.6)."""

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


class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:
        self.replies.append(text)


class _FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class _FakeUpdate:
    def __init__(self, chat_id: int) -> None:
        self.effective_chat = _FakeChat(chat_id)
        self.effective_message = _FakeMessage()


class FormatTests(unittest.TestCase):
    def test_format_recognition_text(self) -> None:
        # Use UTC noon timestamp; HH:MM is locale-dependent so just check the prefix
        text = bot._format_recognition_text({"name": "Alice", "timestamp": 1700000000.0})
        self.assertTrue(text.startswith("🎯 Alice recognized at "))
        self.assertRegex(text, r"\d{2}:\d{2}$")

    def test_format_recognition_missing_timestamp(self) -> None:
        text = bot._format_recognition_text({"name": "Alice"})
        self.assertEqual(text, "🎯 Alice recognized at ??:??")


class QuietToggleTests(unittest.TestCase):
    def _context(self):
        ctx = mock.Mock()
        ctx.bot_data = {"admin_chat_ids": {123}, "notify_enabled": True}
        return ctx

    def test_quiet_sets_flag_false(self) -> None:
        update = _FakeUpdate(123)
        context = self._context()
        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
            asyncio.run(bot.quiet_command(update, context))
        self.assertFalse(context.bot_data["notify_enabled"])
        self.assertEqual(update.effective_message.replies, ["Notifications muted."])

    def test_unquiet_sets_flag_true(self) -> None:
        update = _FakeUpdate(123)
        context = self._context()
        context.bot_data["notify_enabled"] = False
        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
            asyncio.run(bot.unquiet_command(update, context))
        self.assertTrue(context.bot_data["notify_enabled"])
        self.assertEqual(update.effective_message.replies, ["Notifications resumed."])


class PollRecognitionsTests(unittest.TestCase):
    def _context(self, path: Path, chat_ids: set[int], **bot_data):
        ctx = mock.Mock()
        ctx.bot_data = {
            "admin_chat_ids": chat_ids,
            "notify_enabled": True,
            "recognitions_log_path": path,
            "recognitions_offset": 0,
            "greetings_count": 0,
            **bot_data,
        }
        ctx.bot = mock.AsyncMock()
        return ctx

    def test_dispatches_to_each_admin_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recognitions.jsonl"
            path.write_text(json.dumps({"name": "Alice", "timestamp": 1700000000.0}) + "\n", encoding="utf-8")
            context = self._context(path, {111, 222})

            asyncio.run(bot.poll_recognitions(context))

            self.assertEqual(context.bot.send_message.await_count, 2)
            chat_ids_sent = {call.kwargs["chat_id"] for call in context.bot.send_message.await_args_list}
            self.assertEqual(chat_ids_sent, {111, 222})
            self.assertEqual(context.bot_data["greetings_count"], 1)

    def test_quiet_blocks_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recognitions.jsonl"
            path.write_text(json.dumps({"name": "Alice", "timestamp": 1.0}) + "\n", encoding="utf-8")
            context = self._context(path, {111}, notify_enabled=False)

            asyncio.run(bot.poll_recognitions(context))

            self.assertEqual(context.bot.send_message.await_count, 0)

    def test_offset_advances_so_repeated_polls_dont_resend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recognitions.jsonl"
            path.write_text(json.dumps({"name": "Alice", "timestamp": 1.0}) + "\n", encoding="utf-8")
            context = self._context(path, {111})

            asyncio.run(bot.poll_recognitions(context))
            self.assertEqual(context.bot.send_message.await_count, 1)

            # Second tick with no new lines → no new sends.
            asyncio.run(bot.poll_recognitions(context))
            self.assertEqual(context.bot.send_message.await_count, 1)

    def test_no_admins_no_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recognitions.jsonl"
            path.write_text(json.dumps({"name": "Alice", "timestamp": 1.0}) + "\n", encoding="utf-8")
            context = self._context(path, set())

            asyncio.run(bot.poll_recognitions(context))

            self.assertEqual(context.bot.send_message.await_count, 0)


if __name__ == "__main__":
    unittest.main()
