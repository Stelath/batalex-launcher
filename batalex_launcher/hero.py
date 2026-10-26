"""The big picture at the top of the home screen: full-bleed photos/videos
with a Ken Burns effect, crossfading on a timer, plus a bottom gradient and
an optional clock pill."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .config import Config
from .media import MediaLibrary
from .media_widgets import ClockLabel, MediaCycler


class _GradientOverlay(QWidget):
    """Darkens the bottom of the hero so rows sit legibly on top of it."""

    def __init__(self, cfg: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        h = self.height()
        bg = QColor(self._cfg.appearance.background)

        grad = QLinearGradient(0, 0, 0, h)
        transparent = QColor(bg)
        transparent.setAlpha(0)
        solid = QColor(bg)
        solid.setAlpha(255)
        grad.setColorAt(0.0, transparent)
        grad.setColorAt(0.55, transparent)
        grad.setColorAt(1.0, solid)
        p.fillRect(self.rect(), grad)

        # Subtle top vignette for the clock.
        top = QLinearGradient(0, 0, 0, h * 0.22)
        dark = QColor(0, 0, 0, 80)
        clear = QColor(0, 0, 0, 0)
        top.setColorAt(0.0, dark)
        top.setColorAt(1.0, clear)
        p.fillRect(self.rect(), top)
        p.end()


class Hero(QWidget):
    def __init__(self, cfg: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        self.cycler = MediaCycler(
            MediaLibrary(
                cfg.hero_dirs(),
                cfg.image_extensions,
                cfg.video_extensions,
                shuffle=cfg.screensaver.shuffle,
            ),
            cfg.hero.cycle_seconds,
            cfg.appearance,
            empty_hint="Add photos or videos to your screensaver media folder to\nsee them here",
            parent=self,
        )
        self.overlay = _GradientOverlay(cfg, self)

        if cfg.hero.show_clock:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 18, 30, 0)
            row = QHBoxLayout()
            row.addStretch(1)
            self.clock = ClockLabel(cfg.screensaver.clock_24h)
            row.addWidget(self.clock, 0, Qt.AlignmentFlag.AlignTop)
            outer.addLayout(row)
            outer.addStretch(1)
        else:
            self.clock = None

    def start(self) -> None:
        self.cycler.start()

    def stop(self) -> None:
        self.cycler.stop()

    def resizeEvent(self, event) -> None:
        self.cycler.setGeometry(self.rect())
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        if self.clock is not None:
            self.clock.raise_()
        super().resizeEvent(event)
