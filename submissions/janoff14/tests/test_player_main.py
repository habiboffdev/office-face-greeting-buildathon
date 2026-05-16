"""Tests for player.main controller setup."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer

from player.main import Player


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class PlayerSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _get_app()

    def test_audio_is_muted_for_promo_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "promo.mp4"
            path.write_bytes(b"fake")
            player = Player([path])
            try:
                self.assertEqual(player.audio_output.volume(), 0.0)
                if hasattr(player.audio_output, "isMuted"):
                    self.assertTrue(player.audio_output.isMuted())
            finally:
                player._shutdown()

    def test_playback_watchdog_resumes_paused_video_muted(self) -> None:
        class FakeMediaPlayer:
            def __init__(self) -> None:
                self.play_calls = 0

            def mediaStatus(self):
                return QMediaPlayer.MediaStatus.LoadedMedia

            def playbackState(self):
                return QMediaPlayer.PlaybackState.PausedState

            def play(self) -> None:
                self.play_calls += 1

            def stop(self) -> None:
                pass

            def setSource(self, _source) -> None:
                pass

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "promo.mp4"
            path.write_bytes(b"fake")
            player = Player([path])
            fake = FakeMediaPlayer()
            player.media_player = fake
            try:
                player.audio_output.setVolume(1.0)
                player._ensure_playing()
                self.assertEqual(fake.play_calls, 1)
                self.assertEqual(player.audio_output.volume(), 0.0)
            finally:
                player._shutdown()


if __name__ == "__main__":
    unittest.main()
