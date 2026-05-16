"""Headless tests for GreetingOverlay state transitions (AC 5).

Runs under QT_QPA_PLATFORM=offscreen so no real display is needed. Verifies:

* initial opacity is 0
* rapid re-triggers do not leak animation groups
* widget hides itself once the fade-out completes

Run with:
    set QT_QPA_PLATFORM=offscreen
    python -m unittest tests.test_overlay_state
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow

from player.overlay import AvatarLabel, GreetingOverlay, clamp_hold_ms, split_greeting_text


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestGreetingOverlayState(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _get_app()

    def setUp(self) -> None:
        self.window = QMainWindow()
        self.window.resize(1280, 720)
        self.overlay = GreetingOverlay(self.window, font_size_factor=0.08, hold_ms=4_000, fade_ms=50)

    def tearDown(self) -> None:
        self.overlay.deleteLater()
        self.window.deleteLater()
        # Pump events so deferred deletes actually run.
        self.app.processEvents()

    def test_initial_opacity_is_zero(self) -> None:
        self.assertEqual(self.overlay.opacity_effect.opacity(), 0.0)

    def test_initial_state_is_hidden(self) -> None:
        self.assertTrue(self.overlay.isHidden())

    def test_start_fade_does_not_raise(self) -> None:
        self.overlay.start_fade("TEST")  # should not throw

    def test_rapid_retrigger_leaves_single_animation(self) -> None:
        self.overlay.start_fade("FIRST")
        first_group = self.overlay.animation_group
        self.overlay.start_fade("SECOND")
        second_group = self.overlay.animation_group
        self.assertIsNotNone(second_group)
        # Either the group was replaced, or it's the same object with the new text.
        self.assertEqual(self.overlay.label.text(), "SECOND")
        # If a new group was created, the old one must be stopped.
        if first_group is not second_group:
            self.assertEqual(first_group.state().value, 0)  # 0 == Stopped

    def test_many_retriggers_do_not_crash_or_leave_old_text(self) -> None:
        for index in range(50):
            self.overlay.start_fade(f"PERSON {index}")
            self.app.processEvents()
        self.assertEqual(self.overlay.label.text(), "PERSON 49")

    def test_widget_hides_after_full_cycle(self) -> None:
        # 50ms fade + 4000ms hold + 50ms fade = 4100ms; wait a little extra.
        self.overlay.start_fade("BYE")
        QTimer.singleShot(4300, self.app.quit)
        self.app.exec()
        self.assertTrue(self.overlay.isHidden())

    def test_hold_duration_clamped_to_four_to_six_seconds(self) -> None:
        self.assertEqual(clamp_hold_ms(100), 4_000)
        self.assertEqual(clamp_hold_ms(5_000), 5_000)
        self.assertEqual(clamp_hold_ms(9_000), 6_000)

    def test_greeting_text_splits_detail_line(self) -> None:
        self.assertEqual(
            split_greeting_text("Good morning, Alice! - nice scarf today"),
            ("Good morning, Alice!", "nice scarf today"),
        )


class TestAvatarLabelPaint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _get_app()

    def test_avatar_paints_without_pyqt_type_error(self) -> None:
        avatar = AvatarLabel()
        avatar.set_initial("A")
        image = QImage(avatar.size(), QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            avatar.render(painter)
        finally:
            painter.end()
            avatar.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
