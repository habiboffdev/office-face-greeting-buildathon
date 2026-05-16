"""Tests for recognition.worker.

Camera I/O is mocked. The integration smoke against a real camera is
operator-driven (Task 8 of Story 2.3) — we don't run that here.
"""

from __future__ import annotations

import io
import json
import multiprocessing
import queue as queue_module
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from recognition import worker


class _FakeCapture:
    """Minimal stand-in for cv2.VideoCapture."""

    def __init__(self, frames: list[np.ndarray], opened: bool = True) -> None:
        self._frames = list(frames)
        self._opened = opened
        self.grab_calls = 0
        self.retrieve_calls = 0
        self.release_calls = 0

    def isOpened(self) -> bool:  # noqa: N802 (cv2 API)
        return self._opened

    def grab(self) -> bool:
        self.grab_calls += 1
        return bool(self._frames)

    def retrieve(self):
        self.retrieve_calls += 1
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.release_calls += 1


class TestReadLatestFrame(unittest.TestCase):
    def test_drains_buffer_to_latest(self) -> None:
        frames = [np.full((10, 10, 3), i, dtype=np.uint8) for i in range(7)]
        cap = _FakeCapture(frames)
        result = worker._read_latest_frame(cap)
        self.assertTrue(cap.grab_calls > 1, "should drain via grab")
        self.assertEqual(cap.retrieve_calls, 1)
        # Result should be one of the buffer frames (the implementation
        # decodes after the drain — exact identity isn't crucial; non-None is).
        self.assertIsNotNone(result)

    def test_returns_none_on_empty_buffer(self) -> None:
        cap = _FakeCapture([])
        self.assertIsNone(worker._read_latest_frame(cap))


class TestInvalidCameraExit(unittest.TestCase):
    def test_isOpened_false_returns_1_with_stderr_message(self) -> None:
        fake = _FakeCapture([], opened=False)
        stderr = io.StringIO()
        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
             mock.patch.object(sys, "stderr", stderr):
            exit_code = worker.run({"camera_device_index": 99, "people_db_path": "people.json"})
        self.assertEqual(exit_code, 1)
        self.assertIn("cannot open camera index 99", stderr.getvalue())

    def test_uses_directshow_backend_by_default(self) -> None:
        fake = _FakeCapture([], opened=False)
        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake) as video_capture:
            worker.run({"camera_device_index": 3, "people_db_path": "people.json"})
        self.assertEqual(video_capture.call_args.args[0], 3)
        self.assertEqual(video_capture.call_args.args[1], worker.cv2.CAP_DSHOW)


class TestStopEventCleanShutdown(unittest.TestCase):
    def test_stop_event_set_before_loop_returns_cleanly(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 3)
        stop_event = multiprocessing.Event()
        stop_event.set()  # Already set; loop should never iterate.
        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake):
            exit_code = worker.run(
                {"camera_device_index": 0, "people_db_path": "does-not-exist.json"},
                stop_event=stop_event,
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(fake.release_calls, 1)

    def test_exits_when_parent_process_is_gone(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 3)
        parent = mock.Mock()
        parent.is_alive.return_value = False
        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
             mock.patch.object(worker.multiprocessing, "parent_process", return_value=parent):
            exit_code = worker.run(
                {"camera_device_index": 0, "people_db_path": "does-not-exist.json"}
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(fake.release_calls, 1)


class TestMatchPrinting(unittest.TestCase):
    def test_match_prints_to_stdout_unknown_silent(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 2)
        stop_event = multiprocessing.Event()

        # Patch recognize_dual to return "Alice" first call, None second, then signal stop.
        call_count = {"n": 0}

        def fake_recognize(frame, registry, tolerance):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "Alice"
            stop_event.set()
            return None

        stdout = io.StringIO()
        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
             mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
             mock.patch.object(sys, "stdout", stdout):
            exit_code = worker.run(
                {"camera_device_index": 0, "people_db_path": "does-not-exist.json"},
                stop_event=stop_event,
            )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("MATCH: Alice", output)
        # Unknown frame produces no line — only one MATCH line total.
        self.assertEqual(output.count("MATCH:"), 1)

    def test_match_pushes_greeting_queue_event(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 2)
        stop_event = multiprocessing.Event()
        greeting_queue = multiprocessing.Queue(maxsize=8)
        call_count = {"n": 0}

        def fake_recognize(frame, registry, tolerance):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "Alice"
            stop_event.set()
            return None

        try:
            with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
                 mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize):
                exit_code = worker.run(
                    {"camera_device_index": 0, "people_db_path": "does-not-exist.json"},
                    stop_event=stop_event,
                    greeting_queue=greeting_queue,
                )
            self.assertEqual(exit_code, 0)
            event = greeting_queue.get(timeout=1)
            self.assertEqual(event["name"], "Alice")
            self.assertIsInstance(event["timestamp"], float)
        finally:
            greeting_queue.close()
            greeting_queue.join_thread()

    def test_match_logs_notification_even_without_greeting_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 2)
            stop_event = multiprocessing.Event()
            call_count = {"n": 0}

            def fake_recognize(frame, registry, tolerance):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return "Alice"
                stop_event.set()
                return None

            with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
                 mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
                 mock.patch.object(worker.time, "time", return_value=123.0):
                exit_code = worker.run(
                    {
                        "camera_device_index": 0,
                        "people_db_path": "does-not-exist.json",
                        "log_directory": tmp,
                    },
                    stop_event=stop_event,
                )

            self.assertEqual(exit_code, 0)
            records = (Path(tmp) / "recognitions.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(records), 1)
            self.assertEqual(json.loads(records[0])["name"], "Alice")


class TestGreetingCooldown(unittest.TestCase):
    def test_cooldown_helper_tracks_per_person_windows(self) -> None:
        last_greeted_at: dict[str, float] = {}

        self.assertTrue(worker._should_emit_greeting("Alice", 100.0, 60.0, last_greeted_at))
        self.assertEqual(last_greeted_at["Alice"], 100.0)

        self.assertFalse(worker._should_emit_greeting("Alice", 130.0, 60.0, last_greeted_at))
        self.assertEqual(last_greeted_at["Alice"], 100.0)

        self.assertTrue(worker._should_emit_greeting("Alice", 190.0, 60.0, last_greeted_at))
        self.assertEqual(last_greeted_at["Alice"], 190.0)

    def test_cooldown_is_per_person(self) -> None:
        last_greeted_at = {"Alice": 100.0}

        self.assertTrue(worker._should_emit_greeting("Bob", 130.0, 60.0, last_greeted_at))
        self.assertEqual(last_greeted_at["Bob"], 130.0)

    def test_non_positive_cooldown_disables_suppression(self) -> None:
        last_greeted_at = {"Alice": 100.0}

        self.assertTrue(worker._should_emit_greeting("Alice", 101.0, 0.0, last_greeted_at))
        self.assertEqual(last_greeted_at["Alice"], 101.0)

    def test_run_suppresses_queue_events_inside_configured_cooldown(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 3)
        stop_event = multiprocessing.Event()
        greeting_queue = queue_module.Queue(maxsize=8)
        call_count = {"n": 0}

        def fake_recognize(frame, registry, tolerance):
            call_count["n"] += 1
            if call_count["n"] == 3:
                stop_event.set()
            return "Alice"

        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
             mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
             mock.patch.object(worker.time, "time", side_effect=[100.0, 130.0, 190.0]):
            exit_code = worker.run(
                {
                    "camera_device_index": 0,
                    "people_db_path": "does-not-exist.json",
                    "cooldown_seconds": 60,
                },
                stop_event=stop_event,
                greeting_queue=greeting_queue,
            )

        self.assertEqual(exit_code, 0)
        first = greeting_queue.get_nowait()
        second = greeting_queue.get_nowait()
        self.assertEqual(first["name"], "Alice")
        self.assertEqual(first["timestamp"], 100.0)
        self.assertEqual(second["name"], "Alice")
        self.assertEqual(second["timestamp"], 190.0)
        with self.assertRaises(queue_module.Empty):
            greeting_queue.get_nowait()


class TestGreetingQueueBackpressure(unittest.TestCase):
    def test_full_greeting_queue_drops_stale_event_for_newest(self) -> None:
        greeting_queue = queue_module.Queue(maxsize=1)
        greeting_queue.put_nowait({"name": "Old"})

        emitted = worker._try_put_greeting_event(greeting_queue, {"name": "New"})

        self.assertTrue(emitted)
        self.assertEqual(greeting_queue.get_nowait()["name"], "New")
        with self.assertRaises(queue_module.Empty):
            greeting_queue.get_nowait()


class TestDebugCameraFeed(unittest.TestCase):
    def test_debug_queue_gets_jpeg_frame_and_status_lines(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)])
        stop_event = multiprocessing.Event()
        debug_queue = queue_module.Queue(maxsize=2)

        def fake_recognize(frame, registry, tolerance):
            stop_event.set()
            return None

        with mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
             mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
             mock.patch.object(worker.time, "time", side_effect=[1.0, 1.0]):
            exit_code = worker.run(
                {"camera_device_index": 0, "people_db_path": "does-not-exist.json"},
                stop_event=stop_event,
                debug_camera_queue=debug_queue,
            )

        self.assertEqual(exit_code, 0)
        event = debug_queue.get_nowait()
        self.assertIsInstance(event["jpeg"], bytes)
        self.assertGreater(len(event["jpeg"]), 0)
        self.assertIn("match: none", event["lines"])


class _FakeReloader:
    """In-test stand-in for PeopleRegistryReloader (no watchdog thread)."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self._pending = False

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    @property
    def reload_pending(self) -> bool:
        return self._pending

    def clear_pending(self) -> None:
        self._pending = False

    def request_reload(self) -> None:
        self._pending = True


class TestHotReloadIntegration(unittest.TestCase):
    def test_reload_swaps_registry_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            people_db.write_text(json.dumps({"people": []}), encoding="utf-8")

            fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 3)
            stop_event = multiprocessing.Event()

            captured_registries: list[int] = []
            call_count = {"n": 0}
            instances: list[_FakeReloader] = []

            def make_reloader(path):
                inst = _FakeReloader(path)
                instances.append(inst)
                return inst

            def fake_recognize(frame, registry, tolerance):
                call_count["n"] += 1
                captured_registries.append(len(registry.names))
                if call_count["n"] == 1:
                    # After first frame, simulate a write landing on disk.
                    people_db.write_text(
                        json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}),
                        encoding="utf-8",
                    )
                    instances[0].request_reload()
                elif call_count["n"] >= 2:
                    stop_event.set()
                return None

            stdout = io.StringIO()
            with mock.patch.object(worker, "PeopleRegistryReloader", side_effect=make_reloader), \
                 mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
                 mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
                 mock.patch.object(sys, "stdout", stdout):
                exit_code = worker.run(
                    {"camera_device_index": 0, "people_db_path": str(people_db)},
                    stop_event=stop_event,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured_registries[0], 0)
            self.assertGreaterEqual(captured_registries[-1], 1)
            self.assertIn("REGISTRY_RELOADED count=1", stdout.getvalue())
            self.assertEqual(instances[0].start_calls, 1)
            self.assertEqual(instances[0].stop_calls, 1)

    def test_malformed_reload_keeps_old_registry_and_logs_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            people_db.write_text(
                json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}),
                encoding="utf-8",
            )

            fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)] * 3)
            stop_event = multiprocessing.Event()

            instances: list[_FakeReloader] = []

            def make_reloader(path):
                inst = _FakeReloader(path)
                instances.append(inst)
                return inst

            captured_names: list[list[str]] = []
            call_count = {"n": 0}

            def fake_recognize(frame, registry, tolerance):
                call_count["n"] += 1
                captured_names.append(list(registry.names))
                if call_count["n"] == 1:
                    people_db.write_text("{not valid json", encoding="utf-8")
                    instances[0].request_reload()
                elif call_count["n"] >= 2:
                    stop_event.set()
                return None

            stderr = io.StringIO()
            with mock.patch.object(worker, "PeopleRegistryReloader", side_effect=make_reloader), \
                 mock.patch.object(worker.cv2, "VideoCapture", return_value=fake), \
                 mock.patch.object(worker, "recognize_dual", side_effect=fake_recognize), \
                 mock.patch.object(sys, "stderr", stderr):
                exit_code = worker.run(
                    {"camera_device_index": 0, "people_db_path": str(people_db)},
                    stop_event=stop_event,
                )

            self.assertEqual(exit_code, 0)
            # First frame saw Alice; after malformed reload, registry should still have Alice.
            self.assertEqual(captured_names[0], ["Alice"])
            self.assertEqual(captured_names[-1], ["Alice"])
            self.assertIn("REGISTRY_RELOAD_FAILED", stderr.getvalue())

    def test_reloader_stopped_on_clean_shutdown(self) -> None:
        fake = _FakeCapture([np.zeros((480, 640, 3), dtype=np.uint8)])
        stop_event = multiprocessing.Event()
        stop_event.set()

        instances: list[_FakeReloader] = []

        def make_reloader(path):
            inst = _FakeReloader(path)
            instances.append(inst)
            return inst

        with mock.patch.object(worker, "PeopleRegistryReloader", side_effect=make_reloader), \
             mock.patch.object(worker.cv2, "VideoCapture", return_value=fake):
            exit_code = worker.run(
                {"camera_device_index": 0, "people_db_path": "does-not-exist.json"},
                stop_event=stop_event,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(instances[0].start_calls, 1)
        self.assertEqual(instances[0].stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
