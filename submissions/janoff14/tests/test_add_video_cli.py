"""Tests for the add_video.py CLI fallback (Story 4.2)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import add_video as cli


class AddVideoCliTests(unittest.TestCase):
    def test_success_copies_and_prints_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "promo.mp4"
            source.write_bytes(b"video-bytes")
            video_folder = root / "videos"

            stdout = io.StringIO()
            with mock.patch.object(cli, "load_config", return_value={"video_folder": str(video_folder)}), \
                 mock.patch.object(sys, "stdout", stdout):
                code = cli.main([str(source)])

            self.assertEqual(code, 0)
            self.assertTrue((video_folder / "promo.mp4").exists())
            self.assertIn("Added: promo.mp4. Playlist now has 1 videos.", stdout.getvalue())

    def test_missing_args_prints_usage_and_exits_one(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            code = cli.main([])
        self.assertEqual(code, 1)
        self.assertIn("Usage:", stderr.getvalue())

    def test_too_many_args_prints_usage_and_exits_one(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            code = cli.main(["a.mp4", "b.mp4"])
        self.assertEqual(code, 1)
        self.assertIn("Usage:", stderr.getvalue())

    def test_missing_source_prints_error_and_exits_two(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            code = cli.main(["no/such/file.mp4"])
        self.assertEqual(code, 2)
        self.assertIn("video file not found", stderr.getvalue())

    def test_unsupported_extension_prints_error_and_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.avi"
            source.write_bytes(b"data")
            video_folder = root / "videos"

            stderr = io.StringIO()
            with mock.patch.object(cli, "load_config", return_value={"video_folder": str(video_folder)}), \
                 mock.patch.object(sys, "stderr", stderr):
                code = cli.main([str(source)])

            self.assertEqual(code, 2)
            self.assertIn("unsupported video format", stderr.getvalue())
            self.assertIn(".avi", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
