"""Tests for recognition.notifications (Story 5.6)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recognition.notifications import (
    append_recognition_event,
    initial_offset,
    read_new_events,
)


class NotificationsTests(unittest.TestCase):
    def test_append_writes_parseable_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            path = append_recognition_event(log_dir, "Alice", 1700000000.0)
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertEqual(len(content.splitlines()), 1)
            record = json.loads(content.strip())
            self.assertEqual(record["name"], "Alice")
            self.assertEqual(record["timestamp"], 1700000000.0)

    def test_append_creates_missing_log_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "nested"
            append_recognition_event(log_dir, "Alice", 1.0)
            self.assertTrue((log_dir / "recognitions.jsonl").exists())

    def test_append_multiple_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            append_recognition_event(log_dir, "Alice", 1.0)
            append_recognition_event(log_dir, "Bob", 2.0)
            content = (log_dir / "recognitions.jsonl").read_text(encoding="utf-8")
            self.assertEqual(len(content.splitlines()), 2)

    def test_read_new_events_empty_when_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events, offset = read_new_events(Path(tmp) / "missing.jsonl", 0)
            self.assertEqual(events, [])
            self.assertEqual(offset, 0)

    def test_read_new_events_returns_only_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            append_recognition_event(log_dir, "Alice", 1.0)
            path = log_dir / "recognitions.jsonl"

            events, offset = read_new_events(path, 0)
            self.assertEqual([e["name"] for e in events], ["Alice"])

            append_recognition_event(log_dir, "Bob", 2.0)
            new_events, new_offset = read_new_events(path, offset)
            self.assertEqual([e["name"] for e in new_events], ["Bob"])
            self.assertGreater(new_offset, offset)

    def test_read_new_events_skips_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rec.jsonl"
            path.write_text(
                json.dumps({"name": "Alice", "timestamp": 1.0}) + "\n"
                "{not valid json}\n"
                + json.dumps({"name": "Bob", "timestamp": 2.0}) + "\n",
                encoding="utf-8",
            )
            events, _ = read_new_events(path, 0)
            self.assertEqual([e["name"] for e in events], ["Alice", "Bob"])

    def test_initial_offset_returns_eof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            append_recognition_event(log_dir, "Alice", 1.0)
            path = log_dir / "recognitions.jsonl"
            offset = initial_offset(path)
            self.assertEqual(offset, path.stat().st_size)

    def test_initial_offset_zero_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(initial_offset(Path(tmp) / "missing.jsonl"), 0)


if __name__ == "__main__":
    unittest.main()
