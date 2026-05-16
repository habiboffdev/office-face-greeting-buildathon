"""Greeting overlay shown above the fullscreen video player.

The overlay is a top-level translucent window positioned over the player.
That is the reliable Windows/Qt pattern for drawing above QVideoWidget's
native Media Foundation surface without interfering with playback.
"""

from __future__ import annotations

import os
import string
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

MIN_FONT_PT = 24
DEFAULT_FONT_SIZE_FACTOR = 0.08
DEFAULT_HOLD_MS = 5_000
DEFAULT_FADE_MS = 520
MIN_HOLD_MS = 4_000
MAX_HOLD_MS = 6_000
AVATAR_PX = 112

CARD_QSS = """
QFrame#greetingCard {
    border-radius: 32px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(11, 18, 32, 240),
        stop: 0.55 rgba(20, 34, 54, 232),
        stop: 1 rgba(12, 22, 38, 236)
    );
    border: 1px solid rgba(255, 255, 255, 28);
}
QFrame#accentBar {
    border-radius: 4px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #8AF7D6,
        stop: 0.55 #7CC4FF,
        stop: 1 #B791FF
    );
}
QLabel#statusDot {
    background: #62E7B0;
    border-radius: 5px;
    min-width: 10px;
    min-height: 10px;
    max-width: 10px;
    max-height: 10px;
}
QLabel#greetingEyebrow {
    color: rgba(176, 232, 219, 235);
    font-weight: 700;
    letter-spacing: 3px;
}
QLabel#greetingTitle {
    color: #ffffff;
    font-weight: 800;
    letter-spacing: -0.5px;
}
QLabel#greetingDetail {
    color: rgba(218, 232, 246, 220);
    font-weight: 500;
    letter-spacing: 0px;
}
QLabel#brandTag {
    color: rgba(170, 196, 224, 200);
    font-weight: 700;
    letter-spacing: 4px;
}
"""


def compute_font_size(display_height_px: int, factor: float) -> int:
    """Return the font point size for the greeting overlay."""
    if display_height_px <= 0:
        return MIN_FONT_PT
    pixel_height = display_height_px * factor
    point_size = int(pixel_height / 1.333)
    return max(MIN_FONT_PT, point_size)


def clamp_hold_ms(hold_ms: int) -> int:
    """Constrain the visible hold duration to the requested 4-6 seconds."""
    return max(MIN_HOLD_MS, min(MAX_HOLD_MS, int(hold_ms)))


def split_greeting_text(text: str) -> tuple[str, str]:
    """Split a greeting into title and optional detail text."""
    normalized = " ".join(str(text).strip().split())
    for separator in (" - ", " -- "):
        if separator in normalized:
            title, detail = normalized.split(separator, 1)
            return title.strip(), detail.strip()
    return normalized, ""


def _is_offscreen_qt() -> bool:
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"


class AvatarLabel(QLabel):
    """Circular avatar that renders a photo, with a gradient fallback ring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(AVATAR_PX, AVATAR_PX)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pixmap: QPixmap | None = None
        self._initial: str = "Hi"

    def set_photo(self, photo_path: Optional[str | Path]) -> None:
        if photo_path is None:
            self._pixmap = None
            self.update()
            return
        pix = QPixmap(str(photo_path))
        if pix.isNull():
            self._pixmap = None
        else:
            self._pixmap = pix.scaled(
                QSize(AVATAR_PX * 2, AVATAR_PX * 2),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.update()

    def set_initial(self, initial: str) -> None:
        self._initial = initial or "Hi"
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(2, 2, -2, -2)
        ellipse_rect = QRectF(rect)
        path = QPainterPath()
        path.addEllipse(ellipse_rect)
        painter.setClipPath(path)

        if self._pixmap is not None and not self._pixmap.isNull():
            target = rect
            src = self._pixmap
            x = (src.width() - target.width()) // 2
            y = (src.height() - target.height()) // 2
            painter.drawPixmap(target, src, src.rect().adjusted(x, y, -x, -y))
        else:
            gradient_brush = QBrush(QColor(255, 255, 255, 28))
            painter.fillRect(rect, gradient_brush)
            painter.setPen(QPen(QColor(255, 255, 255, 230)))
            font = QFont("Segoe UI")
            font.setBold(True)
            font.setPointSize(max(22, int(rect.height() * 0.42)))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._initial)

        painter.setClipping(False)
        ring_pen = QPen(QColor(255, 255, 255, 80))
        ring_pen.setWidth(2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ellipse_rect)


class GreetingOverlay(QWidget):
    """Animated welcome card that fades over the video."""

    def __init__(
        self,
        anchor_window: QWidget,
        font_size_factor: float = DEFAULT_FONT_SIZE_FACTOR,
        hold_ms: int = DEFAULT_HOLD_MS,
        fade_ms: int = DEFAULT_FADE_MS,
    ) -> None:
        # Parent the overlay to the anchor (kiosk) window so Windows ties their
        # z-order together. Without WindowStaysOnTopHint, the overlay can no
        # longer cover unrelated apps — it only stacks above its parent.
        super().__init__(anchor_window)
        self._anchor = anchor_window
        self.font_size_factor = font_size_factor
        self.hold_ms = clamp_hold_ms(hold_ms)
        self.fade_ms = fade_ms

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Watch the anchor for state and focus changes so the overlay hides
        # when the kiosk is minimized, hidden, or loses foreground focus.
        if anchor_window is not None:
            anchor_window.installEventFilter(self)

        self.card = QFrame(self)
        self.card.setObjectName("greetingCard")
        self.card.setStyleSheet(CARD_QSS)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(90)
        shadow.setOffset(0, 26)
        shadow.setColor(QColor(0, 0, 0, 210))
        self.card.setGraphicsEffect(shadow)

        self.accent_bar = QFrame(self.card)
        self.accent_bar.setObjectName("accentBar")
        self.accent_bar.setFixedWidth(6)

        self.avatar = AvatarLabel(self.card)

        self.status_dot = QLabel("", self.card)
        self.status_dot.setObjectName("statusDot")

        self.eyebrow = QLabel("FACE RECOGNIZED", self.card)
        self.eyebrow.setObjectName("greetingEyebrow")

        eyebrow_row = QHBoxLayout()
        eyebrow_row.setContentsMargins(0, 0, 0, 0)
        eyebrow_row.setSpacing(10)
        eyebrow_row.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        eyebrow_row.addWidget(self.eyebrow, alignment=Qt.AlignmentFlag.AlignVCenter)
        eyebrow_row.addStretch(1)

        self.label = QLabel("", self.card)
        self.label.setObjectName("greetingTitle")
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setWordWrap(True)

        self.detail_label = QLabel("", self.card)
        self.detail_label.setObjectName("greetingDetail")
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.detail_label.setWordWrap(True)

        self.brand_tag = QLabel("FACETAG KIOSK", self.card)
        self.brand_tag.setObjectName("brandTag")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        text_layout.addLayout(eyebrow_row)
        text_layout.addWidget(self.label)
        text_layout.addWidget(self.detail_label)
        text_layout.addSpacing(4)
        text_layout.addWidget(self.brand_tag)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(28, 26, 38, 26)
        card_layout.setSpacing(22)
        card_layout.addWidget(self.accent_bar)
        card_layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignVCenter)
        card_layout.addLayout(text_layout, stretch=1)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setWindowOpacity(0.0)

        self.animation_group: Optional[QSequentialAnimationGroup] = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_finished)
        self._apply_font()
        self.hide()
        self.reposition()

    def reposition(self) -> None:
        """Snap the overlay window to the anchor window."""
        if self._anchor is None:
            return
        top_left = self._anchor.mapToGlobal(self._anchor.rect().topLeft())
        self.setGeometry(
            top_left.x(),
            top_left.y(),
            self._anchor.width(),
            self._anchor.height(),
        )
        self._apply_font()
        self._layout_card()

    def _anchor_has_surface(self) -> bool:
        """Return True when the kiosk window has a surface to draw on.

        We deliberately do NOT require the anchor to be the *active* window —
        the kiosk monitor should still display the greeting while the user
        is interacting with another app (e.g. adding a person from the
        webapp in a browser). Z-order naturally keeps the overlay behind
        whatever app is in front of the kiosk window because the overlay
        is parented to that window (no WindowStaysOnTopHint).
        """
        if self._anchor is None:
            return False
        return self._anchor.isVisible() and not self._anchor.isMinimized()

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        """Hide the overlay when the kiosk window has no surface to draw on."""
        if watched is self._anchor and event is not None:
            etype = event.type()
            if etype in (QEvent.Type.WindowStateChange, QEvent.Type.Hide):
                if not self._anchor_has_surface() and self.isVisible():
                    self._cancel_animation()
                    self.hide()
            elif etype == QEvent.Type.Show:
                self.reposition()
        return super().eventFilter(watched, event)

    def _cancel_animation(self) -> None:
        if self.animation_group is not None:
            self.animation_group.stop()
            self.animation_group.setParent(None)
            self.animation_group = None
        if self._hide_timer is not None:
            self._hide_timer.stop()

    def start_fade(
        self,
        text: str,
        photo_path: Optional[str | Path] = None,
        eyebrow: Optional[str] = None,
    ) -> None:
        """Trigger a fade-in, hold, fade-out cycle with the greeting text."""
        # Suppress only when the kiosk window has no surface (minimized /
        # hidden). When another app is in front of the kiosk, the parented
        # window flag means the OS naturally clips the overlay behind it,
        # so it's safe to still paint on the kiosk monitor.
        if not _is_offscreen_qt() and not self._anchor_has_surface():
            return

        title, detail = split_greeting_text(text)
        self.label.setText(title)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        if eyebrow:
            self.eyebrow.setText(eyebrow.upper())
        else:
            self.eyebrow.setText("FACE RECOGNIZED")
        self.avatar.set_initial(self._badge_text(title))
        self.avatar.set_photo(photo_path)

        self._layout_card()
        self.setWindowOpacity(0.0)
        self.opacity_effect.setOpacity(0.0)

        if _is_offscreen_qt():
            if self.animation_group is not None:
                self.animation_group.stop()
                self.animation_group.setParent(None)
            self.animation_group = QSequentialAnimationGroup()
            self._hide_timer.stop()
            self._hide_timer.start(self.fade_ms + self.hold_ms + self.fade_ms)
            return

        self.raise_()
        self.show()

        if self.animation_group is not None:
            self.animation_group.stop()
            self.animation_group.setParent(None)
            self.animation_group = None

        target = self.card.geometry()
        # Subtle rise + scale entry: starts slightly smaller and lower, settles up.
        start_w = int(target.width() * 0.94)
        start_h = int(target.height() * 0.94)
        start_x = target.x() + (target.width() - start_w) // 2
        start_y = target.y() + 32
        start_rect = QRect(start_x, start_y, start_w, start_h)

        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(self.fade_ms)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        settle_in = QPropertyAnimation(self.card, b"geometry")
        settle_in.setDuration(self.fade_ms)
        settle_in.setStartValue(start_rect)
        settle_in.setEndValue(target)
        settle_in.setEasingCurve(QEasingCurve.Type.OutBack)

        enter = QParallelAnimationGroup(self)
        enter.addAnimation(fade_in)
        enter.addAnimation(settle_in)

        hold = QPauseAnimation(self.hold_ms)

        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(self.fade_ms)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        # Lift card slightly on exit for a polished exit motion.
        exit_rect = QRect(
            target.x(),
            target.y() - 18,
            target.width(),
            target.height(),
        )
        lift_out = QPropertyAnimation(self.card, b"geometry")
        lift_out.setDuration(self.fade_ms)
        lift_out.setStartValue(target)
        lift_out.setEndValue(exit_rect)
        lift_out.setEasingCurve(QEasingCurve.Type.InCubic)

        exit_group = QParallelAnimationGroup(self)
        exit_group.addAnimation(fade_out)
        exit_group.addAnimation(lift_out)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(enter)
        group.addAnimation(hold)
        group.addAnimation(exit_group)
        group.finished.connect(self._on_finished)

        self.animation_group = group
        group.start()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._stop_active_animation()
        super().closeEvent(event)

    def deleteLater(self) -> None:  # noqa: N802 - Qt API
        self._stop_active_animation()
        super().deleteLater()

    def _stop_active_animation(self) -> None:
        self._hide_timer.stop()
        if self.animation_group is not None:
            self.animation_group.stop()
            self.animation_group.setParent(None)
            self.animation_group = None

    def _apply_font(self) -> None:
        height = self._anchor.height() if self._anchor is not None else 1080
        title_size = min(60, compute_font_size(height, self.font_size_factor))

        title_font = QFont("Segoe UI")
        title_font.setBold(True)
        title_font.setPointSize(title_size)
        self.label.setFont(title_font)

        detail_font = QFont("Segoe UI")
        detail_font.setPointSize(max(17, int(title_size * 0.38)))
        detail_font.setWeight(QFont.Weight.Medium)
        self.detail_label.setFont(detail_font)

        eyebrow_font = QFont("Segoe UI")
        eyebrow_font.setPointSize(max(11, int(title_size * 0.22)))
        eyebrow_font.setBold(True)
        self.eyebrow.setFont(eyebrow_font)

        brand_font = QFont("Segoe UI")
        brand_font.setPointSize(max(9, int(title_size * 0.18)))
        brand_font.setBold(True)
        self.brand_tag.setFont(brand_font)

    def _layout_card(self) -> None:
        """Place the card in the lower third with responsive width."""
        max_width = max(620, int(self.width() * 0.78))
        text_width = max(380, max_width - 220)
        self.eyebrow.setMaximumWidth(text_width)
        self.label.setMaximumWidth(text_width)
        self.detail_label.setMaximumWidth(text_width)
        self.brand_tag.setMaximumWidth(text_width)

        # Stretch accent bar to card height (set after layout has measured).
        self.card.adjustSize()
        width = min(max_width, max(620, self.card.sizeHint().width()))
        height = max(168, self.card.sizeHint().height())
        self.accent_bar.setFixedHeight(max(72, height - 56))

        x = max(24, (self.width() - width) // 2)
        y = max(24, int(self.height() * 0.70) - height // 2)
        if y + height > self.height() - 54:
            y = max(24, self.height() - height - 54)
        self.card.setGeometry(x, y, width, height)

    def _badge_text(self, title: str) -> str:
        punctuation = string.punctuation + "!?.,"
        for token in reversed(title.split()):
            cleaned = token.strip(punctuation)
            if cleaned and cleaned[0].isalpha():
                return cleaned[0].upper()
        return "Hi"

    def _on_finished(self) -> None:
        self.opacity_effect.setOpacity(0.0)
        self.setWindowOpacity(0.0)
        self.hide()
