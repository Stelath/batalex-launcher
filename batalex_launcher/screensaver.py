"""The idle screensaver: a fullscreen overlay that shuffles through the
media library until any input dismisses it."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

from .config import Config
from .media import MediaLibrary
from .media_widgets import BigClock, MediaCycler


class _Vignette(QWidget):
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        horiz = QLinearGradient(0, 0, w, 0)
        horiz.setColorAt(0.0, QColor(0, 0, 0, 60))
        horiz.setColorAt(0.12, QColor(0, 0, 0, 0))
        horiz.setColorAt(0.88, QColor(0, 0, 0, 0))
        horiz.setColorAt(1.0, QColor(0, 0, 0, 60))
        p.fillRect(self.rect(), horiz)
        vert = QLinearGradient(0, 0, 0, h)
        vert.setColorAt(0.0, QColor(0, 0, 0, 50))
        vert.setColorAt(0.14, QColor(0, 0, 0, 0))
        vert.setColorAt(0.9, QColor(0, 0, 0, 0))
        vert.setColorAt(1.0, QColor(0, 0, 0, 60))
        p.fillRect(self.rect(), vert)
        p.end()


class ScreensaverOverlay(QWidget):
    """Fullscreen, always-on-top media screensaver. Any key press, click or
    mouse move dismisses it (after a short grace period)."""

    dismissed = Signal()

    def __init__(self, cfg: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setMouseTracking(True)

        self.cycler = MediaCycler(
            MediaLibrary(
                cfg.screensaver.media_dirs,
                cfg.image_extensions,
                cfg.video_extensions,
                shuffle=cfg.screensaver.shuffle,
            ),
            cfg.screensaver.cycle_seconds,
            cfg.appearance,
            empty_hint="",
            parent=self,
        )
        self.vignette = _Vignette(self)

        if cfg.screensaver.show_clock:
            self.clock = BigClock(cfg.screensaver.clock_24h, self)
        else:
            self.clock = None

        self.hint = QLabel("Press any key to go back", self)
        self.hint.setStyleSheet(
            f"color: {cfg.appearance.text_dim}; background: transparent; font-size: 22px;"
        )
        self.hint.adjustSize()

        self._grace = QElapsedTimer()
        self._hint_fade: QPropertyAnimation | None = None

    # -------------------------------------------------------------- #
    def show_fullscreen(self, screen) -> None:
        if screen is not None:
            self.move(screen.geometry().topLeft())
        self.showFullScreen()

    def showEvent(self, event) -> None:
        self._grace.start()
        self.cycler.start()
        if self.clock is not None:
            h = self.height()
            self.clock.set_time_size(max(64, int(h * 0.095)))
            self.clock.adjustSize()
        # Fade the hint out after a few seconds.
        self.hint.show()
        effect = QGraphicsOpacityEffect(self.hint)
        self.hint.setGraphicsEffect(effect)
        QTimer.singleShot(6000, lambda: self._fade_hint(effect))
        super().showEvent(event)

    def _fade_hint(self, effect: QGraphicsOpacityEffect) -> None:
        if not self.hint.isVisible():
            return
        self._hint_fade = QPropertyAnimation(effect, b"opacity", self)
        self._hint_fade.setDuration(1500)
        self._hint_fade.setStartValue(1.0)
        self._hint_fade.setEndValue(0.0)
        self._hint_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._hint_fade.finished.connect(self.hint.hide)
        self._hint_fade.start()

    def closeEvent(self, event) -> None:
        self.cycler.stop()
        super().closeEvent(event)

    # -------------------------------------------------------------- #
    def resizeEvent(self, event) -> None:
        self.cycler.setGeometry(self.rect())
        self.vignette.setGeometry(self.rect())
        self.vignette.raise_()
        if self.clock is not None:
            self.clock.move(64, 52)
            self.clock.raise_()
        self.hint.move(
            (self.width() - self.hint.width()) // 2, self.height() - self.hint.height() - 46
        )
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        self._dismiss()

    def mousePressEvent(self, event) -> None:
        self._dismiss()

    def wheelEvent(self, event) -> None:
        self._dismiss()

    def mouseMoveEvent(self, event) -> None:
        if self._grace.isValid() and self._grace.elapsed() > 500:
            self._dismiss()

    def _dismiss(self) -> None:
        if self._grace.isValid() and self._grace.elapsed() < 400:
            return
        self.cycler.stop()
        self.dismissed.emit()
        self.close()
