"""Tests for recognition.camera_capture."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from recognition.camera_capture import CameraCaptureError, capture_frame_to_file


class _FakeCapture:
    def __init__(self, opened: bool = True) -> None:
        self.opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        return True, object()

    def release(self) -> None:
        self.released = True


class CameraCaptureTests(unittest.TestCase):
    def test_capture_writes_frame_and_releases_camera(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeCapture()
            output = Path(tmp) / "capture.jpg"
            with mock.patch("recognition.camera_capture.cv2.VideoCapture", return_value=fake), \
                 mock.patch("recognition.camera_capture.cv2.imwrite", return_value=True) as imwrite:
                result = capture_frame_to_file(0, output, warmup_frames=1)

            self.assertEqual(result, output)
            imwrite.assert_called_once()
            self.assertTrue(fake.released)

    def test_uses_directshow_backend_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeCapture()
            with mock.patch("recognition.camera_capture.cv2.VideoCapture", return_value=fake) as video_capture, \
                 mock.patch("recognition.camera_capture.cv2.imwrite", return_value=True):
                capture_frame_to_file(1, Path(tmp) / "capture.jpg", warmup_frames=1)

            self.assertEqual(video_capture.call_args.args[0], 1)
            self.assertEqual(video_capture.call_args.args[1], 700)  # cv2.CAP_DSHOW

    def test_unavailable_camera_raises_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeCapture(opened=False)
            with mock.patch("recognition.camera_capture.cv2.VideoCapture", return_value=fake):
                with self.assertRaises(CameraCaptureError):
                    capture_frame_to_file(0, Path(tmp) / "capture.jpg")
            self.assertTrue(fake.released)


if __name__ == "__main__":
    unittest.main()
