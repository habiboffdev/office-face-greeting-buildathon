"""Fullscreen Qt player — main process of the kiosk.

Story 1.3 scope: scan ``video_folder`` for .mp4 files, play the first one
fullscreen on the primary display, advance on EndOfMedia, loop forever,
exit cleanly on Esc.

Forward-compatibility hooks for later stories:

* :attr:`Player.main_window` and :attr:`Player.video_widget` are exposed so
  Story 1.4 can stack a QLabel overlay above the video widget without
  re-wiring construction.
* :meth:`Player.show_greeting` is triggered from a non-blocking
  multiprocessing.Queue poller. The recognition worker owns CPU-heavy face
  matching; Qt only drains greeting events on its normal event loop.

PyQt6 6.11 gotchas baked into this module:

* QMediaPlaylist was removed in Qt6 — playlist advancement is manual via
  the EndOfMedia mediaStatusChanged signal.
* Qt6 split audio out of QMediaPlayer; QAudioOutput is wired explicitly.
* QApplication, QMainWindow, QMediaPlayer, QVideoWidget, and QAudioOutput
  are all retained as Player attributes so Qt6's silent GC of media
  objects can't kill playback.
* setSource takes a QUrl, not a string — QUrl.fromLocalFile is used so
  Windows drive-letter colons aren't reinterpreted as URI schemes.
"""

from __future__ import annotations

import queue
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QKeyEvent, QResizeEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QApplication, QMainWindow

from datetime import datetime

import re

from player.debug_overlay import DebugCameraOverlay
from player.greeting_queue import drain_greeting_queue
from player.greeting_text import build_greeting
from player.overlay import GreetingOverlay
from player.playlist import active_video_folder, advance, next_after_rescan, scan_playlist

# Mirrors recognition.writer._safe_name so the player process doesn't pull in
# cv2 / face_recognition / filelock just to resolve a photo path.
_UNSAFE_NAME_CHARS = re.compile(r"[^a-z0-9._-]+")


def _safe_photo_stem(name: str) -> str | None:
    cleaned = _UNSAFE_NAME_CHARS.sub("_", name.strip().lower()).strip("_")
    return cleaned or None

GREETING_QUEUE_POLL_MS = 100
DEBUG_CAMERA_POLL_MS = 100
PLAYBACK_WATCHDOG_MS = 1500


class _PlayerWindow(QMainWindow):
    """QMainWindow subclass that exits cleanly on Esc and forwards G keypress."""

    def __init__(self, on_close, on_greeting_trigger) -> None:
        super().__init__()
        self._on_close = on_close
        self._on_greeting_trigger = on_greeting_trigger
        self._overlay: GreetingOverlay | None = None
        self._debug_overlay: DebugCameraOverlay | None = None

    def attach_overlay(self, overlay: GreetingOverlay) -> None:
        self._overlay = overlay

    def attach_debug_overlay(self, overlay: DebugCameraOverlay) -> None:
        self._debug_overlay = overlay

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        if event.key() == Qt.Key.Key_G:
            self._on_greeting_trigger()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        if self._overlay is not None:
            self._overlay.reposition()
        if self._debug_overlay is not None:
            self._debug_overlay.reposition()
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        self._on_close()
        super().closeEvent(event)


class Player:
    """Controller that owns the Qt window, media pipeline, and playlist state."""

    def __init__(
        self,
        playlist: list[Path],
        font_size_factor: float = 0.08,
        display_duration_seconds: int = 5,
        greeting_queue=None,
        debug_camera_queue=None,
        greeting_poll_interval_ms: int = GREETING_QUEUE_POLL_MS,
        debug_camera_poll_interval_ms: int = DEBUG_CAMERA_POLL_MS,
        video_folder: Path | None = None,
        playlist_schedule: list[dict[str, Any]] | None = None,
        holidays: dict[str, str] | None = None,
        faces_folder: Path | None = None,
    ) -> None:
        if not playlist:
            raise ValueError("playlist must contain at least one video")
        self._playlist = playlist
        self._index = 0
        self._video_folder = Path(video_folder) if video_folder is not None else None
        self._playlist_schedule = list(playlist_schedule or [])
        self._holidays = dict(holidays) if holidays else {}
        self._faces_folder = Path(faces_folder) if faces_folder is not None else None

        self.main_window = _PlayerWindow(
            on_close=self._shutdown,
            on_greeting_trigger=lambda: self.show_greeting("TEST GREETING"),
        )
        self.video_widget = QVideoWidget(self.main_window)
        self.main_window.setCentralWidget(self.video_widget)

        # Overlay is a top-level translucent window above the main window —
        # the only reliable way to composite over QVideoWidget's native
        # Media Foundation surface on Windows.
        self.overlay = GreetingOverlay(
            self.main_window,
            font_size_factor=font_size_factor,
            hold_ms=display_duration_seconds * 1000,
        )
        self.main_window.attach_overlay(self.overlay)
        self.debug_overlay: DebugCameraOverlay | None = None
        if debug_camera_queue is not None:
            self.debug_overlay = DebugCameraOverlay(self.main_window)
            self.main_window.attach_debug_overlay(self.debug_overlay)

        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.0)
        try:
            self.audio_output.setMuted(True)
        except AttributeError:
            pass
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)

        self._shutdown_done = False
        self._greeting_queue = greeting_queue
        self._debug_camera_queue = debug_camera_queue
        self._greeting_poll_interval_ms = greeting_poll_interval_ms
        self._debug_camera_poll_interval_ms = debug_camera_poll_interval_ms
        self._greeting_poll_timer: QTimer | None = None
        self._debug_camera_poll_timer: QTimer | None = None
        self._playback_watchdog_timer: QTimer | None = None

    def start(self) -> None:
        self.main_window.showFullScreen()
        # Snap overlay to the main window now that it has a real geometry.
        self.overlay.reposition()
        self._load_and_play(self._index)
        self._playback_watchdog_timer = QTimer(self.main_window)
        self._playback_watchdog_timer.timeout.connect(self._ensure_playing)
        self._playback_watchdog_timer.start(PLAYBACK_WATCHDOG_MS)
        if self._greeting_queue is not None:
            self._greeting_poll_timer = QTimer(self.main_window)
            self._greeting_poll_timer.timeout.connect(self._poll_greeting_queue)
            self._greeting_poll_timer.start(self._greeting_poll_interval_ms)
        if self._debug_camera_queue is not None and self.debug_overlay is not None:
            self.debug_overlay.show()
            self._debug_camera_poll_timer = QTimer(self.main_window)
            self._debug_camera_poll_timer.timeout.connect(self._poll_debug_camera_queue)
            self._debug_camera_poll_timer.start(self._debug_camera_poll_interval_ms)

    def show_greeting(
        self,
        name: str,
        flavors: list[str] | None = None,
        language: str | None = None,
        birthday: str | None = None,
        custom_message: str | None = None,
    ) -> None:
        """Fade a greeting overlay over the video.

        Story 2.4 wires this from a multiprocessing.Queue poller; Story 5.1
        adds optional *flavors* from the queue event so the contextual
        greeting builder can pick a personality line.
        """
        if not name or name == "TEST GREETING":
            display_text = "TEST GREETING"
        else:
            display_text = build_greeting(
                name,
                now=datetime.now(),
                holidays=self._holidays,
                flavors=flavors or [],
                language=language,
                birthday=birthday,
                custom_message=custom_message,
            )
        photo_path = self._resolve_photo_path(name)
        self.overlay.reposition()
        self.overlay.start_fade(display_text, photo_path=photo_path)

    def _resolve_photo_path(self, name: str) -> str | None:
        if not name or name == "TEST GREETING" or self._faces_folder is None:
            return None
        safe = _safe_photo_stem(name)
        if safe is None:
            return None
        candidate = self._faces_folder / f"{safe}.jpg"
        return str(candidate) if candidate.is_file() else None

    def _poll_greeting_queue(self) -> None:
        drain_greeting_queue(self._greeting_queue, self.show_greeting)

    def _poll_debug_camera_queue(self) -> None:
        if self._debug_camera_queue is None or self.debug_overlay is None:
            return
        latest = None
        while True:
            try:
                latest = self._debug_camera_queue.get_nowait()
            except queue.Empty:
                break
        if isinstance(latest, dict):
            self.debug_overlay.update_event(latest)

    def _load_and_play(self, index: int) -> None:
        path = self._playlist[index]
        self.audio_output.setVolume(0.0)
        try:
            self.audio_output.setMuted(True)
        except AttributeError:
            pass
        self.media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.media_player.play()

    def _ensure_playing(self) -> None:
        if self._shutdown_done:
            return
        status = self.media_player.mediaStatus()
        if status in {
            QMediaPlayer.MediaStatus.NoMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        }:
            return
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.audio_output.setVolume(0.0)
            try:
                self.audio_output.setMuted(True)
            except AttributeError:
                pass
            self.media_player.play()

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._video_folder is not None:
                current_path = self._playlist[self._index]
                active_folder = active_video_folder(self._video_folder, self._playlist_schedule)
                new_playlist = scan_playlist(active_folder)
                self._playlist, self._index = next_after_rescan(
                    current_path, self._index, new_playlist
                )
            else:
                self._index = advance(self._index, len(self._playlist))
            self._load_and_play(self._index)

    def _shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        if self._playback_watchdog_timer is not None:
            self._playback_watchdog_timer.stop()
        if self._greeting_poll_timer is not None:
            self._greeting_poll_timer.stop()
        if self._debug_camera_poll_timer is not None:
            self._debug_camera_poll_timer.stop()
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        if self.overlay is not None:
            self.overlay.close()  # close the top-level overlay window too
        if self.debug_overlay is not None:
            self.debug_overlay.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def run_player(config: dict[str, Any], greeting_queue=None, debug_camera_queue=None) -> int:
    """Boot the Qt application and play the kiosk loop.

    Returns the Qt exit code so ``run.py`` can pass it to ``sys.exit``.
    """
    video_folder = Path(config.get("video_folder", "videos")).resolve()
    faces_folder = Path(config.get("faces_folder", "faces")).resolve()
    playlist_schedule = config.get("playlist_schedule") or []
    active_folder = active_video_folder(video_folder, playlist_schedule).resolve()
    playlist = scan_playlist(active_folder)
    if not playlist:
        print(
            f"ERROR: no .mp4 files found in {active_folder}",
            file=sys.stderr,
        )
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    player = Player(
        playlist,
        font_size_factor=float(config.get("font_size_factor", 0.08)),
        display_duration_seconds=int(config.get("display_duration_seconds", 5)),
        greeting_queue=greeting_queue,
        debug_camera_queue=debug_camera_queue if config.get("debug_camera_overlay", False) else None,
        video_folder=video_folder,
        playlist_schedule=playlist_schedule,
        holidays=config.get("holidays") or {},
        faces_folder=faces_folder,
    )
    player.start()
    # Keep a reference attached to the app so GC can't kill the pipeline.
    app._kiosk_player = player  # type: ignore[attr-defined]
    return app.exec()
