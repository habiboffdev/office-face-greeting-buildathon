"""Tests for player.playlist (pure helpers — no Qt)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from player.playlist import (
    active_video_folder,
    advance,
    minutes_since_midnight,
    next_after_rescan,
    scan_active_playlist,
    scan_playlist,
)


class NextAfterRescanTests(unittest.TestCase):
    def test_empty_new_playlist_falls_back_to_current(self) -> None:
        current = Path("videos/a.mp4")
        effective, idx = next_after_rescan(current, 0, [])
        self.assertEqual(effective, [current])
        self.assertEqual(idx, 0)

    def test_current_still_present_advances_past_it(self) -> None:
        a, b, c = Path("a.mp4"), Path("b.mp4"), Path("c.mp4")
        effective, idx = next_after_rescan(a, 0, [a, b, c])
        self.assertEqual(effective, [a, b, c])
        self.assertEqual(idx, 1)
        self.assertEqual(effective[idx], b)

    def test_current_still_present_wraps_at_end(self) -> None:
        a, b = Path("a.mp4"), Path("b.mp4")
        effective, idx = next_after_rescan(b, 1, [a, b])
        self.assertEqual(idx, 0)
        self.assertEqual(effective[idx], a)

    def test_current_deleted_uses_last_index_clamped(self) -> None:
        a, b, c = Path("a.mp4"), Path("b.mp4"), Path("c.mp4")
        # current "ghost.mp4" was deleted while playing; last_index was 2.
        effective, idx = next_after_rescan(Path("ghost.mp4"), 2, [a, b, c])
        self.assertEqual(effective, [a, b, c])
        # last_index 2 clamps to 2, advance → 0 (wraps).
        self.assertEqual(idx, 0)

    def test_current_deleted_last_index_beyond_new_length(self) -> None:
        a, b = Path("a.mp4"), Path("b.mp4")
        # last_index was 5 in a previously-longer list; new list has only 2.
        effective, idx = next_after_rescan(Path("ghost.mp4"), 5, [a, b])
        self.assertEqual(idx, 0)  # clamped to 1, advanced → 0

    def test_single_video_playlist_wraps_to_self(self) -> None:
        only = Path("only.mp4")
        effective, idx = next_after_rescan(only, 0, [only])
        self.assertEqual(effective, [only])
        self.assertEqual(idx, 0)


class ScanPlaylistTmpFilterTests(unittest.TestCase):
    def test_videos_dot_tmp_subdir_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            video_folder = Path(tmp)
            (video_folder / "a.mp4").write_bytes(b"x")
            tmp_dir = video_folder / ".tmp"
            tmp_dir.mkdir()
            (tmp_dir / "staging.mp4").write_bytes(b"y")

            entries = scan_playlist(video_folder)

            self.assertEqual([p.name for p in entries], ["a.mp4"])


class AdvanceTests(unittest.TestCase):
    def test_wraps(self) -> None:
        self.assertEqual(advance(2, 3), 0)
        self.assertEqual(advance(0, 3), 1)

    def test_zero_length_raises(self) -> None:
        with self.assertRaises(ValueError):
            advance(0, 0)


class ScheduledPlaylistTests(unittest.TestCase):
    def test_minutes_since_midnight_parses_hhmm(self) -> None:
        self.assertEqual(minutes_since_midnight("08:30"), 510)
        with self.assertRaises(ValueError):
            minutes_since_midnight("25:00")

    def test_active_folder_uses_first_matching_window(self) -> None:
        schedule = [
            {"start": "08:00", "end": "12:00", "folder": "videos/morning"},
            {"start": "12:00", "end": "18:00", "folder": "videos/day"},
        ]
        result = active_video_folder(
            Path("videos/default"),
            schedule,
            now=datetime(2026, 5, 16, 9, 0),
        )
        self.assertEqual(result, Path("videos/morning"))

    def test_active_folder_supports_overnight_window(self) -> None:
        schedule = [{"start": "18:00", "end": "08:00", "folder": "videos/night"}]
        result = active_video_folder(
            Path("videos/default"),
            schedule,
            now=datetime(2026, 5, 16, 23, 0),
        )
        self.assertEqual(result, Path("videos/night"))

    def test_active_folder_falls_back_to_default(self) -> None:
        schedule = [{"start": "08:00", "end": "12:00", "folder": "videos/morning"}]
        result = active_video_folder(
            Path("videos/default"),
            schedule,
            now=datetime(2026, 5, 16, 14, 0),
        )
        self.assertEqual(result, Path("videos/default"))

    def test_scan_active_playlist_scans_selected_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = root / "default"
            morning = root / "morning"
            default.mkdir()
            morning.mkdir()
            (default / "default.mp4").write_bytes(b"x")
            (morning / "morning.mp4").write_bytes(b"y")
            entries = scan_active_playlist(
                default,
                [{"start": "08:00", "end": "12:00", "folder": str(morning)}],
                now=datetime(2026, 5, 16, 9, 0),
            )
            self.assertEqual([p.name for p in entries], ["morning.mp4"])


if __name__ == "__main__":
    unittest.main()
