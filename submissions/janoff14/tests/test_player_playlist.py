"""Headless tests for player.playlist — no QApplication required.

These verify the pure-function pieces of the player so the playlist contract
can change without booting Qt. Anything that needs a real display lives in
manual verification (Task 6 of Story 1.3).

Run with: python -m unittest tests.test_player_playlist
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Allow `python -m unittest tests.test_player_playlist` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.playlist import advance, scan_playlist


def _touch(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_bytes(b"")
    return path


class TestScanPlaylist(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_empty_list_when_folder_has_no_videos(self) -> None:
        self.assertEqual(scan_playlist(self.tmp_path), [])

    def test_returns_empty_list_when_folder_missing(self) -> None:
        missing = self.tmp_path / "does-not-exist"
        self.assertEqual(scan_playlist(missing), [])

    def test_finds_mp4_files(self) -> None:
        a = _touch(self.tmp_path, "a.mp4")
        b = _touch(self.tmp_path, "b.mp4")
        self.assertEqual(scan_playlist(self.tmp_path), [a, b])

    def test_sorts_alphabetically(self) -> None:
        _touch(self.tmp_path, "zebra.mp4")
        _touch(self.tmp_path, "apple.mp4")
        _touch(self.tmp_path, "mango.mp4")
        result = [p.name for p in scan_playlist(self.tmp_path)]
        self.assertEqual(result, ["apple.mp4", "mango.mp4", "zebra.mp4"])

    def test_case_insensitive_extension(self) -> None:
        _touch(self.tmp_path, "lower.mp4")
        _touch(self.tmp_path, "upper.MP4")
        _touch(self.tmp_path, "mixed.Mp4")
        result = sorted(p.name.lower() for p in scan_playlist(self.tmp_path))
        self.assertEqual(result, ["lower.mp4", "mixed.mp4", "upper.mp4"])

    def test_ignores_non_video_files(self) -> None:
        _touch(self.tmp_path, "promo.mp4")
        _touch(self.tmp_path, "readme.txt")
        _touch(self.tmp_path, ".gitkeep")
        _touch(self.tmp_path, "thumb.jpg")
        result = [p.name for p in scan_playlist(self.tmp_path)]
        self.assertEqual(result, ["promo.mp4"])

    def test_ignores_subfolders(self) -> None:
        # The .tmp/ folder is used by later stories for atomic writes; the
        # player must never see partial files there.
        tmp_subdir = self.tmp_path / ".tmp"
        tmp_subdir.mkdir()
        _touch(tmp_subdir, "partial.mp4")
        _touch(self.tmp_path, "ready.mp4")
        result = [p.name for p in scan_playlist(self.tmp_path)]
        self.assertEqual(result, ["ready.mp4"])


class TestAdvance(unittest.TestCase):
    def test_wraps_at_end(self) -> None:
        self.assertEqual(advance(2, 3), 0)

    def test_increments_in_middle(self) -> None:
        self.assertEqual(advance(0, 3), 1)
        self.assertEqual(advance(1, 3), 2)

    def test_single_item_playlist_loops_to_self(self) -> None:
        self.assertEqual(advance(0, 1), 0)

    def test_zero_length_playlist_raises(self) -> None:
        with self.assertRaises(ValueError):
            advance(0, 0)


if __name__ == "__main__":
    unittest.main()
