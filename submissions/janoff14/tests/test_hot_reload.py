"""Tests for recognition.hot_reload.PeopleRegistryReloader (Story 3.5)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recognition.hot_reload import PeopleRegistryReloader


def _wait_for(predicate, timeout: float = 3.0, poll: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll)
    return predicate()


class PeopleRegistryReloaderTests(unittest.TestCase):
    def test_modification_sets_reload_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            path.write_text(json.dumps({"people": []}), encoding="utf-8")
            reloader = PeopleRegistryReloader(path)
            reloader.start()
            try:
                self.assertFalse(reloader.reload_pending)
                path.write_text(json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}), encoding="utf-8")
                self.assertTrue(_wait_for(lambda: reloader.reload_pending, timeout=3.0))
            finally:
                reloader.stop()

    def test_atomic_replace_sets_reload_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            path.write_text(json.dumps({"people": []}), encoding="utf-8")
            reloader = PeopleRegistryReloader(path)
            reloader.start()
            try:
                tmp_path = path.with_suffix(path.suffix + ".tmp")
                tmp_path.write_text(
                    json.dumps({"people": [{"name": "Bob", "encoding": [0.0] * 128}]}),
                    encoding="utf-8",
                )
                import os
                os.replace(tmp_path, path)
                self.assertTrue(_wait_for(lambda: reloader.reload_pending, timeout=3.0))
            finally:
                reloader.stop()

    def test_clear_pending_then_event_resets_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            path.write_text(json.dumps({"people": []}), encoding="utf-8")
            reloader = PeopleRegistryReloader(path)
            reloader.start()
            try:
                path.write_text(json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}), encoding="utf-8")
                self.assertTrue(_wait_for(lambda: reloader.reload_pending))
                reloader.clear_pending()
                self.assertFalse(reloader.reload_pending)
                # Sleep briefly to let the previous event drain, then write again.
                time.sleep(0.2)
                path.write_text(
                    json.dumps({"people": [{"name": "Carol", "encoding": [0.0] * 128}]}),
                    encoding="utf-8",
                )
                self.assertTrue(_wait_for(lambda: reloader.reload_pending, timeout=3.0))
            finally:
                reloader.stop()

    def test_unrelated_file_in_same_dir_does_not_set_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            path.write_text(json.dumps({"people": []}), encoding="utf-8")
            reloader = PeopleRegistryReloader(path)
            reloader.start()
            try:
                noise = Path(tmp) / "other.txt"
                noise.write_text("hello", encoding="utf-8")
                time.sleep(0.5)
                self.assertFalse(reloader.reload_pending)
            finally:
                reloader.stop()

    def test_stop_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            path.write_text(json.dumps({"people": []}), encoding="utf-8")
            reloader = PeopleRegistryReloader(path)
            reloader.start()
            reloader.stop()
            reloader.stop()  # second call must not raise

    def test_start_creates_missing_parent_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nested" / "people.json"
            reloader = PeopleRegistryReloader(missing)
            reloader.start()
            try:
                self.assertTrue(missing.parent.is_dir())
            finally:
                reloader.stop()

    def test_request_reload_sets_flag_synthetically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "people.json"
            reloader = PeopleRegistryReloader(path)
            self.assertFalse(reloader.reload_pending)
            reloader.request_reload()
            self.assertTrue(reloader.reload_pending)


if __name__ == "__main__":
    unittest.main()
