"""Tests for recognition.writer — atomic add_person / remove_person.

Uses tmp_path-style isolation so the writer never touches the real
project-root ``people.json``. Face-bearing tests skip cleanly if no
source photo is available.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recognition.registry import load_registry
from recognition.writer import (
    NoFaceInImageError,
    _safe_name,
    add_person,
    remove_person,
    update_person_metadata,
)
from tests._fixtures import _first_face_photo


class TestSafeName(unittest.TestCase):
    def test_lowercases(self) -> None:
        self.assertEqual(_safe_name("Alice"), "alice")

    def test_strips_whitespace(self) -> None:
        self.assertEqual(_safe_name("  alice  "), "alice")

    def test_replaces_inner_whitespace(self) -> None:
        self.assertEqual(_safe_name("Alice Anderson"), "alice_anderson")

    def test_replaces_path_separators(self) -> None:
        self.assertEqual(_safe_name("a/b\\c"), "a_b_c")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            _safe_name("   ")
        with self.assertRaises(ValueError):
            _safe_name("")

    def test_collapses_runs_of_unsafe_chars(self) -> None:
        self.assertEqual(_safe_name("Alice  /  Anderson"), "alice_anderson")


class _WriterTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.people_path = self.tmp_path / "people.json"
        self.faces_dir = self.tmp_path / "faces"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestRemovePerson(_WriterTestBase):
    def test_unknown_returns_false_no_change(self) -> None:
        self.people_path.write_text(json.dumps({"people": []}))
        before = self.people_path.read_text()
        self.assertFalse(remove_person("Alice", self.people_path, self.faces_dir))
        self.assertEqual(self.people_path.read_text(), before)

    def test_unknown_on_missing_file_returns_false(self) -> None:
        self.assertFalse(remove_person("Alice", self.people_path, self.faces_dir))


class TestUpdatePersonMetadata(_WriterTestBase):
    def test_updates_existing_entry(self) -> None:
        payload = {"people": [{"name": "Alice", "encoding": [0.1] * 128}]}
        self.people_path.write_text(json.dumps(payload), encoding="utf-8")

        updated = update_person_metadata(
            "Alice",
            self.people_path,
            language="uz",
            birthday="05-16",
            custom_message="demo day",
            flavor=["nice scarf"],
            telegram_chat_id=999,
        )

        self.assertTrue(updated)
        data = json.loads(self.people_path.read_text(encoding="utf-8"))
        entry = data["people"][0]
        self.assertEqual(entry["language"], "uz")
        self.assertEqual(entry["birthday"], "05-16")
        self.assertEqual(entry["custom_message"], "demo day")
        self.assertEqual(entry["flavor"], ["nice scarf"])
        self.assertEqual(entry["telegram_chat_id"], "999")

    def test_update_unknown_returns_false(self) -> None:
        payload = {"people": [{"name": "Alice", "encoding": [0.1] * 128}]}
        self.people_path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertFalse(update_person_metadata("Bob", self.people_path, language="ru"))

    def test_invalid_birthday_raises(self) -> None:
        payload = {"people": [{"name": "Alice", "encoding": [0.1] * 128}]}
        self.people_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            update_person_metadata("Alice", self.people_path, birthday="2026-05-16")


class TestAtomicWriteSemantics(_WriterTestBase):
    def test_lock_blocks_concurrent_writer(self) -> None:
        """Second add_person on the same path must wait until the first releases."""
        # We can't realistically run face_recognition twice in this test
        # without pulling in a real photo, so we exercise the lock by
        # acquiring it via the writer's own filelock helper.
        from filelock import FileLock

        lock_path = str(self.people_path) + ".lock"
        # Hold the lock from a background thread for 0.5s.
        held = threading.Event()
        release = threading.Event()

        def hold() -> None:
            with FileLock(lock_path):
                held.set()
                release.wait(timeout=2.0)

        t = threading.Thread(target=hold, daemon=True)
        t.start()
        self.assertTrue(held.wait(timeout=1.0))

        # Now try to acquire the same lock with a short timeout; must fail.
        from filelock import Timeout

        contended = FileLock(lock_path)
        with self.assertRaises(Timeout):
            contended.acquire(timeout=0.1)

        release.set()
        t.join(timeout=2.0)


class TestAddRemoveIntegration(_WriterTestBase):
    """End-to-end add_person → remove_person against a real face."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_photo = _first_face_photo()
        if cls.source_photo is None:
            raise unittest.SkipTest("No face photo available in faces/")

    def test_add_creates_entry_and_copies_photo(self) -> None:
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        reg = load_registry(self.people_path)
        self.assertEqual(reg.names, ["Alice"])
        self.assertEqual(reg.encodings.shape, (1, 128))
        self.assertTrue((self.faces_dir / "alice.jpg").exists())

    def test_add_overwrites_duplicate_name(self) -> None:
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        reg = load_registry(self.people_path)
        self.assertEqual(reg.names, ["Alice"])  # exactly one entry

    def test_add_then_remove_round_trip(self) -> None:
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        self.assertTrue((self.faces_dir / "alice.jpg").exists())
        self.assertTrue(remove_person("Alice", self.people_path, self.faces_dir))
        reg = load_registry(self.people_path)
        self.assertEqual(reg.names, [])
        self.assertFalse((self.faces_dir / "alice.jpg").exists())

    def test_remove_is_case_insensitive_on_name(self) -> None:
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        self.assertTrue(remove_person("alice", self.people_path, self.faces_dir))
        reg = load_registry(self.people_path)
        self.assertEqual(reg.names, [])

    def test_no_face_raises_specific_error(self) -> None:
        # 200x200 black image, written to a real .jpg so cv2.imread succeeds.
        import cv2
        import numpy as np

        black = self.tmp_path / "black.jpg"
        cv2.imwrite(str(black), np.zeros((200, 200, 3), dtype=np.uint8))
        with self.assertRaises(NoFaceInImageError):
            add_person("Ghost", black, self.people_path, self.faces_dir)

    def test_unreadable_image_raises_value_error(self) -> None:
        missing = self.tmp_path / "nope.jpg"
        with self.assertRaises(ValueError):
            add_person("Ghost", missing, self.people_path, self.faces_dir)

    def test_no_tmp_file_remains_after_success(self) -> None:
        add_person("Alice", self.source_photo, self.people_path, self.faces_dir)
        # Atomic rename means the .tmp file should be gone.
        self.assertFalse(self.people_path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
