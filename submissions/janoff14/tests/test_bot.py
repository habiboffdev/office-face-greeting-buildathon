"""Offline tests for Telegram bot allowlist behavior."""

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


class _FakeFile:
    def __init__(self, payload: bytes = b"photo") -> None:
        self.payload = payload
        self.downloaded_to: Path | None = None

    async def download_to_drive(self, path: Path) -> None:
        self.downloaded_to = Path(path)
        self.downloaded_to.write_bytes(self.payload)


class _FakePhoto:
    def __init__(self, file_id: str = "file-1", width: int = 640, height: int = 480) -> None:
        self.file_id = file_id
        self.width = width
        self.height = height


class _FakeBot:
    def __init__(self, file_obj: _FakeFile | None = None) -> None:
        self.file_obj = file_obj or _FakeFile()
        self.requested_file_ids: list[str] = []
        self.sent_photos: list[dict] = []
        self.sent_messages: list[dict] = []

    async def get_file(self, file_id: str):
        self.requested_file_ids.append(file_id)
        return self.file_obj

    async def send_photo(self, **kwargs) -> None:
        self.sent_photos.append(kwargs)

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)


class _FakeMessage:
    def __init__(self, text: str = "", photo: list[_FakePhoto] | None = None) -> None:
        self.text = text
        self.photo = photo or []
        self.replies: list[str] = []
        self.photos: list[str] = []
        self.videos: list[str] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:
        self.replies.append(text)

    async def reply_photo(self, photo, caption: str | None = None) -> None:
        self.photos.append(caption or "")

    async def reply_video(self, video, caption: str | None = None) -> None:
        self.videos.append(caption or "")


class _FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class _FakeVideo:
    def __init__(
        self,
        file_id: str = "vid-1",
        file_size: int = 1024,
        file_name: str | None = "promo.mp4",
        mime_type: str | None = "video/mp4",
    ) -> None:
        self.file_id = file_id
        self.file_size = file_size
        self.file_name = file_name
        self.mime_type = mime_type


class _FakeUpdate:
    def __init__(
        self,
        chat_id: int,
        text: str = "",
        photo: list[_FakePhoto] | None = None,
        video: _FakeVideo | None = None,
    ) -> None:
        self.effective_chat = _FakeChat(chat_id)
        self.effective_message = _FakeMessage(text, photo=photo)
        self.effective_message.video = video


class _FakeQuery:
    def __init__(self, data: str, fail_text_edit: bool = False) -> None:
        self.data = data
        self.fail_text_edit = fail_text_edit
        self.answers: list[str] = []
        self.edits: list[str] = []
        self.caption_edits: list[str] = []

    async def answer(self, text: str | None = None) -> None:
        self.answers.append(text or "")

    async def edit_message_text(self, text: str, reply_markup=None) -> None:
        if self.fail_text_edit:
            raise RuntimeError("message is not text")
        self.edits.append(text)

    async def edit_message_caption(self, caption: str, reply_markup=None) -> None:
        self.caption_edits.append(caption)


class _FakeCallbackUpdate:
    def __init__(self, chat_id: int, data: str, fail_text_edit: bool = False) -> None:
        self.effective_chat = _FakeChat(chat_id)
        self.effective_message = _FakeMessage()
        self.callback_query = _FakeQuery(data, fail_text_edit=fail_text_edit)


class BotAllowlistTests(unittest.TestCase):
    def test_parse_admin_chat_ids_accepts_ints_and_numeric_strings(self) -> None:
        self.assertEqual(bot.parse_admin_chat_ids([123, "456", " 789 "]), {123, 456, 789})

    def test_admin_start_replies_welcome(self) -> None:
        update = _FakeUpdate(123, "/start")
        context = mock.Mock()
        context.bot_data = {"admin_chat_ids": {123}}

        asyncio.run(bot.start_command(update, context))

        self.assertEqual(update.effective_message.replies, ["Welcome admin"])

    def test_unauthorized_start_replies_and_logs(self) -> None:
        update = _FakeUpdate(999, "/start")
        context = mock.Mock()
        context.bot_data = {"admin_chat_ids": {123}}
        log = io.StringIO()

        with mock.patch.object(bot, "BOT_LOG_STREAM", log):
            asyncio.run(bot.admin_only(bot.start_command)(update, context))

        self.assertEqual(update.effective_message.replies, ["Unauthorized"])
        logged = log.getvalue()
        self.assertIn("UNAUTHORIZED chat_id=999 command=/start", logged)

    def test_unauthorized_unknown_command_does_not_leak_behavior(self) -> None:
        update = _FakeUpdate(999, "/delete_person Alice")
        context = mock.Mock()
        context.bot_data = {"admin_chat_ids": {123}}
        log = io.StringIO()

        with mock.patch.object(bot, "BOT_LOG_STREAM", log):
            asyncio.run(bot.unknown_command(update, context))

        self.assertEqual(update.effective_message.replies, ["Unauthorized"])
        self.assertIn("UNAUTHORIZED chat_id=999 command=/delete_person", log.getvalue())

    def test_sanitize_secret_redacts_token(self) -> None:
        token = "12345:SECRET_TOKEN"
        text = f"connection failed for https://api.telegram.org/bot{token}/getMe"

        sanitized = bot.sanitize_secret(text, token)

        self.assertNotIn(token, sanitized)
        self.assertIn("<telegram_token>", sanitized)

    def test_build_application_allows_empty_allowlist_so_chat_ids_can_be_logged(self) -> None:
        fake_builder = mock.Mock()
        fake_application = mock.Mock()
        fake_application.bot_data = {}
        fake_application.add_handler = mock.Mock()
        fake_builder.token.return_value = fake_builder
        fake_builder.post_init.return_value = fake_builder
        fake_builder.build.return_value = fake_application

        with mock.patch("telegram.ext.Application.builder", return_value=fake_builder):
            application = bot.build_application({"telegram_token": "12345:SECRET", "admin_chat_ids": []})

        self.assertIs(application, fake_application)
        self.assertEqual(application.bot_data["admin_chat_ids"], set())

    def test_build_application_registers_add_person_handlers(self) -> None:
        fake_builder = mock.Mock()
        fake_application = mock.Mock()
        fake_application.bot_data = {}
        fake_application.add_handler = mock.Mock()
        fake_builder.token.return_value = fake_builder
        fake_builder.post_init.return_value = fake_builder
        fake_builder.build.return_value = fake_application

        with mock.patch("telegram.ext.Application.builder", return_value=fake_builder):
            bot.build_application({"telegram_token": "12345:SECRET", "admin_chat_ids": [123]})

        self.assertGreaterEqual(fake_application.add_handler.call_count, 5)
        self.assertEqual(fake_application.bot_data["pending_add_person"], {})
        self.assertEqual(fake_application.bot_data["people_db_path"], Path("people.json"))
        self.assertEqual(fake_application.bot_data["faces_folder"], Path("faces"))


class AddPersonFlowTests(unittest.TestCase):
    def _context(self, chat_id: int = 123, file_obj: _FakeFile | None = None):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "people_db_path": Path("people.json"),
            "faces_folder": Path("faces"),
        }
        context.bot = _FakeBot(file_obj=file_obj)
        return context

    def test_add_person_command_prompts_for_name_and_sets_pending_state(self) -> None:
        update = _FakeUpdate(123, "/add_person")
        context = self._context()

        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
            asyncio.run(bot.admin_only(bot.add_person_command)(update, context))

        self.assertEqual(update.effective_message.replies, ["Send me a name, then a photo"])
        self.assertEqual(context.bot_data["pending_add_person"][123], {"step": "name"})
        self.assertIn("ADD_PERSON_START chat_id=123", log.getvalue())

    def test_name_reply_stores_pending_name(self) -> None:
        update = _FakeUpdate(123, "Judge Karimov")
        context = self._context()
        context.bot_data["pending_add_person"][123] = {"step": "name"}

        with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
            asyncio.run(bot.handle_text_message(update, context))

        self.assertEqual(update.effective_message.replies, ["Send me a photo"])
        self.assertEqual(context.bot_data["pending_add_person"][123], {"step": "photo", "name": "Judge Karimov"})
        self.assertIn("ADD_PERSON_NAME chat_id=123", log.getvalue())

    def test_photo_reply_downloads_and_calls_shared_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_obj = _FakeFile()
            update = _FakeUpdate(123, photo=[_FakePhoto("small", width=100), _FakePhoto("large", width=800)])
            context = self._context(file_obj=file_obj)
            context.bot_data["pending_add_person"][123] = {"step": "photo", "name": "Judge Karimov"}
            context.bot_data["people_db_path"] = root / "people.json"
            context.bot_data["faces_folder"] = root / "faces"

            with mock.patch.object(bot, "add_person") as add_person, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.handle_photo_message(update, context))

        self.assertEqual(update.effective_message.replies, ["Photo received. Processing...", "Judge Karimov added"])
        self.assertEqual(context.bot.requested_file_ids, ["large"])
        add_person.assert_called_once()
        args = add_person.call_args.args
        self.assertEqual(args[0], "Judge Karimov")
        self.assertEqual(args[2], root / "people.json")
        self.assertEqual(args[3], root / "faces")
        self.assertNotIn(123, context.bot_data["pending_add_person"])
        self.assertIn("ADD_PERSON_ADDED chat_id=123", log.getvalue())

    def test_no_face_reply_clears_pending_state(self) -> None:
        update = _FakeUpdate(123, photo=[_FakePhoto("face")])
        context = self._context()
        context.bot_data["pending_add_person"][123] = {"step": "photo", "name": "Ghost"}

        with mock.patch.object(bot, "add_person", side_effect=bot.NoFaceInImageError("none")):
            asyncio.run(bot.handle_photo_message(update, context))

        self.assertEqual(
            update.effective_message.replies,
            [
                "Photo received. Processing...",
                "No face detected in that photo. Please try a clearer front-facing photo.",
            ],
        )
        self.assertNotIn(123, context.bot_data["pending_add_person"])

    def test_writer_error_replies_instead_of_going_silent(self) -> None:
        update = _FakeUpdate(123, photo=[_FakePhoto("bad")])
        context = self._context()
        context.bot_data["pending_add_person"][123] = {"step": "photo", "name": "Bad Image"}

        with mock.patch.object(bot, "add_person", side_effect=ValueError("could not decode image")):
            asyncio.run(bot.handle_photo_message(update, context))

        self.assertEqual(
            update.effective_message.replies,
            ["Photo received. Processing...", "Could not add that photo. Please try a clearer front-facing photo."],
        )
        self.assertNotIn(123, context.bot_data["pending_add_person"])

    def test_text_when_waiting_for_photo_reprompts(self) -> None:
        update = _FakeUpdate(123, "not a photo")
        context = self._context()
        context.bot_data["pending_add_person"][123] = {"step": "photo", "name": "Alice"}

        asyncio.run(bot.handle_text_message(update, context))

        self.assertEqual(update.effective_message.replies, ["Send me a photo"])

    def test_unauthorized_add_person_is_blocked_before_state_change(self) -> None:
        update = _FakeUpdate(999, "/add_person")
        context = self._context(chat_id=123)

        asyncio.run(bot.admin_only(bot.add_person_command)(update, context))

        self.assertEqual(update.effective_message.replies, ["Unauthorized"])
        self.assertEqual(context.bot_data["pending_add_person"], {})


class SelfRegistrationFlowTests(unittest.TestCase):
    def _context(self, root: Path, file_obj: _FakeFile | None = None):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {123},
            "pending_self_submit": {},
            "pending_approvals": {},
            "pending_add_person": {},
            "people_db_path": root / "people.json",
            "faces_folder": root / "faces",
            "pending_submissions_folder": root / "pending",
        }
        context.bot = _FakeBot(file_obj=file_obj)
        return context

    def test_join_prompts_normal_user_for_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            update = _FakeUpdate(999, "/join")
            context = self._context(Path(tmp))

            asyncio.run(bot.self_register_command(update, context))

            self.assertEqual(context.bot_data["pending_self_submit"][999], {"step": "name"})
            self.assertEqual(update.effective_message.replies, ["Send your name, then a clear front-facing photo."])

    def test_join_blocked_after_user_is_already_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Aziza"])
            data = json.loads(people_db.read_text(encoding="utf-8"))
            data["people"][0]["telegram_chat_id"] = "999"
            people_db.write_text(json.dumps(data), encoding="utf-8")
            update = _FakeUpdate(999, "/join")
            context = self._context(root)

            asyncio.run(bot.self_register_command(update, context))

            self.assertEqual(context.bot_data["pending_self_submit"], {})
            self.assertIn("already registered as Aziza", update.effective_message.replies[0])

    def test_normal_user_name_then_photo_notifies_admin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = self._context(root)
            context.bot_data["pending_self_submit"][999] = {"step": "name"}

            asyncio.run(bot.handle_text_message(_FakeUpdate(999, "Aziza"), context))
            photo_update = _FakeUpdate(999, photo=[_FakePhoto("selfie", width=800, height=800)])
            asyncio.run(bot.handle_photo_message(photo_update, context))

            self.assertEqual(photo_update.effective_message.replies, ["Photo received. Waiting for admin approval."])
            self.assertEqual(context.bot.requested_file_ids, ["selfie"])
            self.assertEqual(len(context.bot_data["pending_approvals"]), 1)
            self.assertEqual(len(context.bot.sent_photos), 1)
            self.assertEqual(context.bot.sent_photos[0]["chat_id"], 123)
            self.assertIn("Aziza", context.bot.sent_photos[0]["caption"])

    def test_admin_approval_adds_person_and_notifies_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = root / "pending.jpg"
            photo.write_bytes(b"jpg")
            context = self._context(root)
            context.bot_data["pending_approvals"]["abc123"] = {
                "chat_id": 999,
                "name": "Aziza",
                "photo_path": str(photo),
            }
            update = _FakeCallbackUpdate(123, "self_approve:abc123")

            with mock.patch.object(bot, "add_person") as writer:
                asyncio.run(bot.handle_menu_callback(update, context))

            writer.assert_called_once_with(
                "Aziza",
                photo,
                root / "people.json",
                root / "faces",
                telegram_chat_id=999,
            )
            self.assertEqual(update.callback_query.edits, ["✅ Aziza approved and added."])
            self.assertEqual(context.bot.sent_messages[0]["chat_id"], 999)
            self.assertIn("approved", context.bot.sent_messages[0]["text"])
            self.assertFalse(photo.exists())

    def test_admin_approval_edits_caption_when_request_is_photo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = root / "pending.jpg"
            photo.write_bytes(b"jpg")
            context = self._context(root)
            context.bot_data["pending_approvals"]["abc123"] = {
                "chat_id": 999,
                "name": "Aziza",
                "photo_path": str(photo),
            }
            update = _FakeCallbackUpdate(123, "self_approve:abc123", fail_text_edit=True)

            with mock.patch.object(bot, "add_person"), \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_menu_callback(update, context))

            self.assertEqual(update.callback_query.edits, [])
            self.assertEqual(update.callback_query.caption_edits, ["✅ Aziza approved and added."])

    def test_admin_rejection_notifies_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = root / "pending.jpg"
            photo.write_bytes(b"jpg")
            context = self._context(root)
            context.bot_data["pending_approvals"]["abc123"] = {
                "chat_id": 999,
                "name": "Aziza",
                "photo_path": str(photo),
            }
            update = _FakeCallbackUpdate(123, "self_reject:abc123")

            asyncio.run(bot.handle_menu_callback(update, context))

            self.assertEqual(update.callback_query.edits, ["❌ Aziza rejected."])
            self.assertIn("not approved", context.bot.sent_messages[0]["text"])
            self.assertFalse(photo.exists())


    def test_duplicate_admin_approval_tap_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = self._context(Path(tmp))
            update = _FakeCallbackUpdate(123, "self_approve:missing")

            asyncio.run(bot.handle_menu_callback(update, context))

            self.assertEqual(update.callback_query.edits, ["Registration request is no longer available."])
            self.assertEqual(context.bot.sent_messages, [])

    def test_cancelled_self_registration_text_goes_back_to_join_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = self._context(Path(tmp))
            context.bot_data["pending_self_submit"][999] = {"step": "photo", "name": "Aziza"}
            cancel_update = _FakeCallbackUpdate(999, "user:cancel")

            asyncio.run(bot.handle_menu_callback(cancel_update, context))
            text_update = _FakeUpdate(999, "Aziza")
            asyncio.run(bot.handle_text_message(text_update, context))

            self.assertEqual(context.bot_data["pending_self_submit"], {})
            self.assertEqual(text_update.effective_message.replies, ["Use /join to request registration."])


def _write_people_json(path: Path, names: list[str]) -> None:
    payload = {"people": [{"name": n, "encoding": [0.0] * 128} for n in names]}
    path.write_text(json.dumps(payload), encoding="utf-8")


class ListPeopleFlowTests(unittest.TestCase):
    def _context(self, chat_id: int, people_db_path: Path):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "people_db_path": people_db_path,
            "faces_folder": people_db_path.parent / "faces",
        }
        return context

    def test_list_people_empty_replies_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            update = _FakeUpdate(123, "/list_people")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.list_people_command)(update, context))

            self.assertEqual(
                update.effective_message.replies,
                ["No people registered yet. Use /add_person to add someone."],
            )
            self.assertIn("LIST_PEOPLE chat_id=123 count=0", log.getvalue())

    def test_list_people_sends_registered_photos_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            faces = root / "faces"
            faces.mkdir()
            _write_people_json(people_db, ["Alice", "Bob", "Carol"])
            for filename in ("alice.jpg", "bob.jpg", "carol.jpg"):
                (faces / filename).write_bytes(b"jpg")
            update = _FakeUpdate(123, "/list_people")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.list_people_command)(update, context))

            self.assertEqual(update.effective_message.replies, ["Registered people: 3."])
            self.assertEqual(update.effective_message.photos, ["Alice", "Bob", "Carol"])
            self.assertIn("LIST_PEOPLE chat_id=123 count=3", log.getvalue())

    def test_unauthorized_list_people_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Alice"])
            update = _FakeUpdate(999, "/list_people")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.list_people_command)(update, context))

            self.assertEqual(update.effective_message.replies, ["Unauthorized"])


class DeletePersonFlowTests(unittest.TestCase):
    def _context(self, chat_id: int, people_db_path: Path):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "people_db_path": people_db_path,
            "faces_folder": people_db_path.parent / "faces",
        }
        return context

    def test_delete_person_known_name_calls_writer_and_replies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Alice", "Bob"])
            update = _FakeUpdate(123, "/delete_person Alice")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person", return_value=True) as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_called_once_with("Alice", people_db, root / "faces")
            self.assertEqual(update.effective_message.replies, ["Alice removed"])
            self.assertIn("DELETE_PERSON_REMOVED chat_id=123", log.getvalue())

    def test_delete_person_multi_word_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Judge Karimov"])
            update = _FakeUpdate(123, "/delete_person Judge Karimov")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person", return_value=True) as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_called_once_with("Judge Karimov", people_db, root / "faces")
            self.assertEqual(update.effective_message.replies, ["Judge Karimov removed"])

    def test_delete_person_missing_arg_replies_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            update = _FakeUpdate(123, "/delete_person")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person") as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_not_called()
            self.assertEqual(update.effective_message.replies, ["Usage: /delete_person <name>"])

    def test_delete_person_unknown_name_replies_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Alice"])
            update = _FakeUpdate(123, "/delete_person Bob")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person") as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_not_called()
            self.assertEqual(
                update.effective_message.replies,
                ["Person not found. Use /list_people to see who is registered."],
            )
            self.assertIn("DELETE_PERSON_NOT_FOUND chat_id=123", log.getvalue())

    def test_delete_person_case_sensitive_does_not_match_lowercase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Alice"])
            update = _FakeUpdate(123, "/delete_person alice")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person") as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_not_called()
            self.assertEqual(
                update.effective_message.replies,
                ["Person not found. Use /list_people to see who is registered."],
            )

    def test_unauthorized_delete_person_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            _write_people_json(people_db, ["Alice"])
            update = _FakeUpdate(999, "/delete_person Alice")
            context = self._context(123, people_db)

            with mock.patch.object(bot, "remove_person") as rm, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_person_command)(update, context))

            rm.assert_not_called()
            self.assertEqual(update.effective_message.replies, ["Unauthorized"])


class AddVideoFlowTests(unittest.TestCase):
    def _context(self, chat_id: int, video_folder: Path, file_obj: _FakeFile | None = None):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "pending_add_video": {},
            "people_db_path": video_folder.parent / "people.json",
            "faces_folder": video_folder.parent / "faces",
            "video_folder": video_folder,
        }
        context.bot = _FakeBot(file_obj=file_obj)
        return context

    def test_add_video_command_prompts_and_sets_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            update = _FakeUpdate(123, "/add_video")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.add_video_command)(update, context))

            self.assertEqual(update.effective_message.replies, ["Send me the video file"])
            self.assertTrue(context.bot_data["pending_add_video"][123])
            self.assertIn("ADD_VIDEO_START chat_id=123", log.getvalue())

    def test_video_under_limit_writes_through_writer_and_replies_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_folder = root / "videos"
            video_folder.mkdir()
            (video_folder / "existing.mp4").write_bytes(b"old")

            file_obj = _FakeFile(b"new-video-bytes")
            video = _FakeVideo(file_id="abc", file_size=1024, file_name="promo.mp4")
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder, file_obj=file_obj)
            context.bot_data["pending_add_video"][123] = True

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.handle_video_message(update, context))

            final_path = video_folder / "promo.mp4"
            self.assertTrue(final_path.exists())
            self.assertEqual(final_path.read_bytes(), b"new-video-bytes")
            self.assertEqual(
                update.effective_message.replies,
                ["Video received. Processing...", "promo.mp4 added. Playlist now has 2 videos"],
            )
            self.assertNotIn(123, context.bot_data["pending_add_video"])
            self.assertIn("ADD_VIDEO_ADDED chat_id=123", log.getvalue())

    def test_video_over_limit_rejected_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video = _FakeVideo(file_id="big", file_size=21 * 1024 * 1024, file_name="big.mp4")
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder)
            context.bot_data["pending_add_video"][123] = True

            with mock.patch.object(bot, "add_video") as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            writer.assert_not_called()
            self.assertEqual(context.bot.requested_file_ids, [])
            self.assertEqual(
                update.effective_message.replies,
                ["This video is over 20 MB. Please upload it via add_video.py on the laptop."],
            )
            self.assertNotIn(123, context.bot_data["pending_add_video"])

    def test_unsupported_extension_rejected_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video = _FakeVideo(file_id="bad", file_size=1024, file_name="weird.avi")
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder)
            context.bot_data["pending_add_video"][123] = True

            with mock.patch.object(bot, "add_video") as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            writer.assert_not_called()
            self.assertEqual(context.bot.requested_file_ids, [])
            self.assertEqual(
                update.effective_message.replies,
                ["That file format is not supported. Please use .mp4, .mov, or .webm."],
            )
            self.assertNotIn(123, context.bot_data["pending_add_video"])

    def test_missing_filename_falls_back_to_mime_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_folder = root / "videos"
            video_folder.mkdir()

            file_obj = _FakeFile(b"mp4-bytes")
            video = _FakeVideo(
                file_id="noname-mp4",
                file_size=1024,
                file_name=None,
                mime_type="video/mp4",
            )
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder, file_obj=file_obj)
            context.bot_data["pending_add_video"][123] = True

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            final_path = video_folder / "noname-mp4.mp4"
            self.assertTrue(final_path.exists())
            self.assertEqual(
                update.effective_message.replies,
                ["Video received. Processing...", "noname-mp4.mp4 added. Playlist now has 1 videos"],
            )

    def test_missing_filename_and_unknown_mime_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video = _FakeVideo(
                file_id="mystery",
                file_size=1024,
                file_name=None,
                mime_type="video/x-mystery",
            )
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder)
            context.bot_data["pending_add_video"][123] = True

            with mock.patch.object(bot, "add_video") as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            writer.assert_not_called()
            self.assertEqual(
                update.effective_message.replies,
                ["That file format is not supported. Please use .mp4, .mov, or .webm."],
            )

    def test_video_without_pending_state_replies_use_add_video_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video = _FakeVideo()
            update = _FakeUpdate(123, video=video)
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "add_video") as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            writer.assert_not_called()
            self.assertEqual(update.effective_message.replies, ["Use /add_video first"])

    def test_unauthorized_video_message_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video = _FakeVideo()
            update = _FakeUpdate(999, video=video)
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "add_video") as writer, \
                 mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.handle_video_message(update, context))

            writer.assert_not_called()
            self.assertEqual(update.effective_message.replies, ["Unauthorized"])


class ListVideosFlowTests(unittest.TestCase):
    def _context(self, chat_id: int, video_folder: Path):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "pending_add_video": {},
            "video_folder": video_folder,
        }
        return context

    def test_empty_replies_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            update = _FakeUpdate(123, "/list_videos")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.list_videos_command)(update, context))

            self.assertEqual(
                update.effective_message.replies,
                ["No videos in playlist yet. Use /add_video to add one."],
            )
            self.assertIn("LIST_VIDEOS chat_id=123 count=0", log.getvalue())

    def test_non_empty_sends_videos_with_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "alpha.mp4").write_bytes(b"x")
            (video_folder / "beta.webm").write_bytes(b"y")
            update = _FakeUpdate(123, "/list_videos")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.list_videos_command)(update, context))

            self.assertEqual(update.effective_message.replies, ["Playlist videos: 2."])
            self.assertEqual(update.effective_message.videos, ["alpha.mp4", "beta.webm"])

    def test_unauthorized_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            update = _FakeUpdate(999, "/list_videos")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.list_videos_command)(update, context))

            self.assertEqual(update.effective_message.replies, ["Unauthorized"])


class DeleteVideoFlowTests(unittest.TestCase):
    def _context(self, chat_id: int, video_folder: Path):
        context = mock.Mock()
        context.bot_data = {
            "admin_chat_ids": {chat_id},
            "pending_add_person": {},
            "pending_add_video": {},
            "video_folder": video_folder,
        }
        return context

    def test_known_file_removed_replies_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "a.mp4").write_bytes(b"x")
            (video_folder / "b.mp4").write_bytes(b"y")
            update = _FakeUpdate(123, "/delete_video a.mp4")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.delete_video_command)(update, context))

            self.assertFalse((video_folder / "a.mp4").exists())
            self.assertTrue((video_folder / "b.mp4").exists())
            self.assertEqual(
                update.effective_message.replies,
                ["a.mp4 removed. Playlist now has 1 videos"],
            )
            self.assertIn("DELETE_VIDEO_REMOVED chat_id=123", log.getvalue())

    def test_multi_word_filename_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "my promo.mp4").write_bytes(b"x")
            update = _FakeUpdate(123, "/delete_video my promo.mp4")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_video_command)(update, context))

            self.assertFalse((video_folder / "my promo.mp4").exists())
            self.assertEqual(
                update.effective_message.replies,
                ["my promo.mp4 removed. Playlist now has 0 videos"],
            )

    def test_unknown_replies_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "a.mp4").write_bytes(b"x")
            update = _FakeUpdate(123, "/delete_video ghost.mp4")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()) as log:
                asyncio.run(bot.admin_only(bot.delete_video_command)(update, context))

            self.assertTrue((video_folder / "a.mp4").exists())
            self.assertEqual(
                update.effective_message.replies,
                ["Video not found. Use /list_videos to see what is in the playlist."],
            )
            self.assertIn("DELETE_VIDEO_NOT_FOUND chat_id=123", log.getvalue())

    def test_missing_arg_replies_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            update = _FakeUpdate(123, "/delete_video")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_video_command)(update, context))

            self.assertEqual(
                update.effective_message.replies,
                ["Usage: /delete_video <filename>"],
            )

    def test_unauthorized_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            (video_folder / "a.mp4").write_bytes(b"x")
            update = _FakeUpdate(999, "/delete_video a.mp4")
            context = self._context(123, video_folder)

            with mock.patch.object(bot, "BOT_LOG_STREAM", io.StringIO()):
                asyncio.run(bot.admin_only(bot.delete_video_command)(update, context))

            self.assertTrue((video_folder / "a.mp4").exists())
            self.assertEqual(update.effective_message.replies, ["Unauthorized"])


if __name__ == "__main__":
    unittest.main()
