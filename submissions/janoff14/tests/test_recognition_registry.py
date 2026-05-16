"""Tests for recognition.registry.

Pure I/O + array reshape — no face_recognition or OpenCV needed for the
registry itself, only json + numpy.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from recognition.registry import Registry, load_registry


class TestLoadRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.json_path = self.tmp_path / "people.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file_returns_empty_registry(self) -> None:
        reg = load_registry(self.tmp_path / "does-not-exist.json")
        self.assertEqual(reg.names, [])
        self.assertEqual(reg.encodings.shape, (0, 128))

    def test_empty_people_list_returns_empty_registry(self) -> None:
        self.json_path.write_text(json.dumps({"people": []}))
        reg = load_registry(self.json_path)
        self.assertEqual(reg.names, [])
        self.assertEqual(reg.encodings.shape, (0, 128))

    def test_one_person_returns_one_row(self) -> None:
        encoding = [0.1] * 128
        payload = {"people": [{"name": "Alice", "encoding": encoding}]}
        self.json_path.write_text(json.dumps(payload))
        reg = load_registry(self.json_path)
        self.assertEqual(reg.names, ["Alice"])
        self.assertEqual(reg.encodings.shape, (1, 128))
        np.testing.assert_allclose(reg.encodings[0], encoding)

    def test_optional_greeting_metadata_is_loaded(self) -> None:
        encoding = [0.1] * 128
        payload = {
            "people": [{
                "name": "Alice",
                "encoding": encoding,
                "language": "uz",
                "birthday": "05-16",
                "custom_message": "demo day",
                "flavor": ["nice scarf"],
                "telegram_chat_id": "999",
            }]
        }
        self.json_path.write_text(json.dumps(payload))
        reg = load_registry(self.json_path)
        self.assertEqual(reg.languages, ["uz"])
        self.assertEqual(reg.birthdays, ["05-16"])
        self.assertEqual(reg.custom_messages, ["demo day"])
        self.assertEqual(reg.flavors, [["nice scarf"]])
        self.assertEqual(reg.telegram_chat_ids, ["999"])

    def test_multiple_people_preserves_order(self) -> None:
        payload = {
            "people": [
                {"name": "Alice", "encoding": [0.1] * 128},
                {"name": "Bob", "encoding": [0.2] * 128},
                {"name": "Carol", "encoding": [0.3] * 128},
            ]
        }
        self.json_path.write_text(json.dumps(payload))
        reg = load_registry(self.json_path)
        self.assertEqual(reg.names, ["Alice", "Bob", "Carol"])
        self.assertEqual(reg.encodings.shape, (3, 128))

    def test_malformed_json_raises_with_path(self) -> None:
        self.json_path.write_text("{not valid json")
        with self.assertRaises(ValueError) as cm:
            load_registry(self.json_path)
        self.assertIn(str(self.json_path), str(cm.exception))

    def test_registry_is_frozen(self) -> None:
        reg = Registry(names=["x"], encodings=np.zeros((1, 128)))
        with self.assertRaises(Exception):
            reg.names = ["y"]  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
