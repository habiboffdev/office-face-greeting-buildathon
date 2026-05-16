"""Tests for player.video_writer (Story 3.6)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.playlist import VIDEO_EXTENSIONS, scan_playlist
from player.video_writer import (
    SUPPORTED_VIDEO_EXTENSIONS,
    UnsupportedVideoFormatError,
    add_video,
    remove_video,
)


def _write_bytes(path: Path, payload: bytes = b"video-bytes") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class VideoWriterTests(unittest.TestCase):
    def test_happy_path_copies_to_final_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "incoming" / "promo.mp4")
            video_folder = root / "videos"

            final = add_video(source, video_folder)

            self.assertEqual(final, video_folder / "promo.mp4")
            self.assertTrue(final.exists())
            self.assertEqual(final.read_bytes(), b"video-bytes")

    def test_creates_videos_and_tmp_dirs_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "promo.mov")
            video_folder = root / "videos"

            add_video(source, video_folder)

            self.assertTrue((video_folder / ".tmp").is_dir())

    def test_tmp_dir_is_empty_after_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "promo.webm")
            video_folder = root / "videos"

            add_video(source, video_folder)

            tmp_dir = video_folder / ".tmp"
            self.assertEqual(list(tmp_dir.iterdir()), [])

    def test_unsupported_extension_raises_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "bad.avi")
            video_folder = root / "videos"

            with self.assertRaises(UnsupportedVideoFormatError):
                add_video(source, video_folder)

            self.assertFalse((video_folder / "bad.avi").exists())

    def test_missing_source_raises_filenotfound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                add_video(root / "missing.mp4", root / "videos")

    def test_overwrite_same_filename_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_folder = root / "videos"
            source_a = _write_bytes(root / "a" / "promo.mp4", b"first")
            add_video(source_a, video_folder)
            source_b = _write_bytes(root / "b" / "promo.mp4", b"second")

            final = add_video(source_b, video_folder)

            self.assertEqual(final.read_bytes(), b"second")

    def test_target_filename_override_uses_basename_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "source.mp4")
            video_folder = root / "videos"

            final = add_video(source, video_folder, target_filename="../escape/clean.mp4")

            self.assertEqual(final, video_folder / "clean.mp4")
            self.assertTrue(final.exists())

    def test_extension_set_is_consumed_by_playlist_scanner(self) -> None:
        self.assertEqual(SUPPORTED_VIDEO_EXTENSIONS, VIDEO_EXTENSIONS)
        self.assertIn(".mp4", VIDEO_EXTENSIONS)
        self.assertIn(".mov", VIDEO_EXTENSIONS)
        self.assertIn(".webm", VIDEO_EXTENSIONS)

    def test_scan_playlist_picks_up_video_after_add(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_bytes(root / "promo.mp4")
            video_folder = root / "videos"

            add_video(source, video_folder)
            entries = scan_playlist(video_folder)

            self.assertEqual([p.name for p in entries], ["promo.mp4"])


class RemoveVideoTests(unittest.TestCase):
    def test_existing_file_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_folder = root / "videos"
            video_folder.mkdir()
            target = _write_bytes(video_folder / "promo.mp4")

            self.assertTrue(remove_video("promo.mp4", video_folder))
            self.assertFalse(target.exists())

    def test_missing_file_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()

            self.assertFalse(remove_video("ghost.mp4", video_folder))

    def test_path_traversal_sanitized_to_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video_folder = root / "videos"
            video_folder.mkdir()
            outside = _write_bytes(root / "secret.mp4")
            inside = _write_bytes(video_folder / "secret.mp4")

            self.assertTrue(remove_video("../secret.mp4", video_folder))
            self.assertFalse(inside.exists())
            self.assertTrue(outside.exists())

    def test_empty_filename_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            self.assertFalse(remove_video("", video_folder))

    def test_directory_not_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp) / "videos"
            video_folder.mkdir()
            sub = video_folder / "subdir"
            sub.mkdir()

            self.assertFalse(remove_video("subdir", video_folder))
            self.assertTrue(sub.is_dir())


if __name__ == "__main__":
    unittest.main()
