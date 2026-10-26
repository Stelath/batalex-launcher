"""Shared media widgets: Ken Burns photos, video layers, crossfading cyclers,
and clocks. Used by both the home-screen hero and the screensaver."""
from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from .config import Appearance
from .media import MediaLibrary
from .widgets import cover_source


class KenBurnsImage(QWidget):
    """A photo that slowly pans/zooms while it is displayed."""

    def __init__(self, appearance: Appearance, parent: QWidget | None = None):
        super().__init__(parent)
        self._a = appearance
        self._pixmap = None
        self._progress = 0.0
        self._z0 = self._z1 = 1.06
        self._dx0 = self._dx1 = self._dy0 = self._dy1 = 0.0
        self._anim: QPropertyAnimation | None = None

    def getProgress(self) -> float:
        return self._progress

    def setProgress(self, value: float) -> None:
        self._progress = value
        self.update()

    progress = Property(float, getProgress, setProgress)

    def set_pixmap(self, pixmap, duration_ms: int) -> None:
        self.stop()
        self._pixmap = pixmap
        self._z0 = random.uniform(1.03, 1.09)
        self._z1 = self._z0 + random.uniform(0.04, 0.09)
        self._dx0, self._dy0 = random.uniform(-0.02, 0.02), random.uniform(-0.02, 0.02)
        self._dx1, self._dy1 = random.uniform(-0.02, 0.02), random.uniform(-0.02, 0.02)
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(max(1000, duration_ms))
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._anim.start()
        self.update()

    def stop(self) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

    def paintEvent(self, event) -> None:
        if self._pixmap is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t = self._progress
        z = self._z0 + (self._z1 - self._z0) * t
        dx = (self._dx0 + (self._dx1 - self._dx0) * t) * self.width()
        dy = (self._dy0 + (self._dy1 - self._dy0) * t) * self.height()
        w, h = self.width() * z, self.height() * z
        target = QRectF(self.width() / 2 + dx - w / 2, self.height() / 2 + dy - h / 2, w, h)
        p.drawPixmap(target, self._pixmap, cover_source(self._pixmap, target))
        p.end()


class MediaLayer(QWidget):
    """Displays exactly one media item (photo or video) filling the widget."""

    video_error = Signal()

    def __init__(self, appearance: Appearance, parent: QWidget | None = None):
        super().__init__(parent)
        self._a = appearance
        self._image = KenBurnsImage(appearance, self)
        self._video: QVideoWidget | None = None
        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._is_video = False

    def is_video(self) -> bool:
        return self._is_video

    def _ensure_video(self) -> QVideoWidget:
        if self._video is None:
            self._video = QVideoWidget(self)
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._audio.setVolume(0.0)  # screensavers stay silent
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video)
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.errorOccurred.connect(self._on_error)
        return self._video

    def _on_status(self, status) -> None:
        if (
            status == QMediaPlayer.MediaStatus.EndOfMedia
            and self._player is not None
        ):
            self._player.setPosition(0)
            self._player.play()

    def _on_error(self, error, message: str) -> None:
        if self._is_video:
            self.video_error.emit()

    def show_media(self, path: Path, cycle_seconds: float, is_video: bool) -> bool:
        if is_video:
            video = self._ensure_video()
            self._image.stop()
            self._image.hide()
            video.show()
            self._player.setSource(QUrl.fromLocalFile(str(path)))
            self._player.play()
            self._is_video = True
            return True
        from PySide6.QtGui import QPixmap

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        if self._video is not None:
            self._video.hide()
            self._player.stop()
        self._image.show()
        self._image.set_pixmap(pixmap, int(cycle_seconds * 1000))
        self._is_video = False
        return True

    def stop(self) -> None:
        self._image.stop()
        if self._player is not None:
            self._player.stop()

    def resizeEvent(self, event) -> None:
        self._image.setGeometry(self.rect())
        if self._video is not None:
            self._video.setGeometry(self.rect())


class MediaCycler(QWidget):
    """Crossfades between items from a MediaLibrary every ``cycle_seconds``.

    Photos get a Ken Burns pan/zoom; videos play muted and loop until the
    cycle advances.
    """

    mediaChanged = Signal(object)

    def __init__(
        self,
        library: MediaLibrary,
        cycle_seconds: float,
        appearance: Appearance,
        empty_hint: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._lib = library
        self._cycle = max(2.0, cycle_seconds)
        self._a = appearance
        self._layers = [MediaLayer(appearance, self), MediaLayer(appearance, self)]
        for layer in self._layers:
            layer.hide()
        self._layers[0].video_error.connect(self._on_video_error)
        self._layers[1].video_error.connect(self._on_video_error)
        self._current = 0
        self._started = False
        self._transitioning = False
        self._effects: list[QGraphicsOpacityEffect | None] = [None, None]
        self._fade_anim: QPropertyAnimation | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(int(self._cycle * 1000))
        self._timer.timeout.connect(self.advance)

        self._hint = QLabel(empty_hint, self)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color: {appearance.text_dim}; background: transparent; font-size: 22px;"
        )
        self._hint.hide()

    # -------------------------------------------------------------- #
    def start(self) -> None:
        self._timer.start()
        if not self._started and not self._transitioning:
            self._started = True
            self.advance(instant=True)

    def stop(self) -> None:
        self._timer.stop()
        for layer in self._layers:
            layer.stop()

    def set_active(self, active: bool) -> None:
        if active:
            self.start()
        else:
            self.stop()

    def library(self) -> MediaLibrary:
        return self._lib

    # -------------------------------------------------------------- #
    def advance(self, instant: bool = False) -> None:
        if self._transitioning:
            return
        path = self._lib.next()
        if path is None:
            self._show_empty()
            return
        self._show(path, instant)

    def _show(self, path: Path, instant: bool) -> None:
        incoming = self._layers[1 - self._current]
        outgoing = self._layers[self._current]
        ok = incoming.show_media(path, self._cycle, self._lib.is_video(path))
        if not ok:
            # Broken file: skip ahead (bounded recursion).
            nxt = self._lib.next()
            if nxt is None:
                self._show_empty()
            else:
                self._show(nxt, instant)
            return

        self._hint.hide()
        incoming.raise_()
        if instant or incoming.is_video() or outgoing.is_video():
            self._clear_effect(incoming)
            incoming.show()
            outgoing.stop()
            self._current = 1 - self._current
        else:
            self._transitioning = True
            effect = self._ensure_effect(incoming)
            effect.setOpacity(0.0)
            incoming.show()
            self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
            self._fade_anim.setDuration(1100)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_anim.finished.connect(
                lambda layer=incoming, old=outgoing: self._finish_fade(layer, old)
            )
            self._fade_anim.start()
        self.mediaChanged.emit(path)

    def _finish_fade(self, incoming: MediaLayer, outgoing: MediaLayer) -> None:
        outgoing.stop()
        self._clear_effect(incoming)
        self._current = 1 - self._current
        self._transitioning = False

    def _on_video_error(self) -> None:
        # Current video can't play: skip to the next item right away.
        self._transitioning = False
        self.advance(instant=True)

    # -------------------------------------------------------------- #
    def _ensure_effect(self, layer: MediaLayer) -> QGraphicsOpacityEffect:
        idx = self._layers.index(layer)
        if self._effects[idx] is None:
            self._effects[idx] = QGraphicsOpacityEffect(layer)
            layer.setGraphicsEffect(self._effects[idx])
        return self._effects[idx]

    def _clear_effect(self, layer: MediaLayer) -> None:
        idx = self._layers.index(layer)
        if self._effects[idx] is not None:
            self._effects[idx].setOpacity(1.0)
            layer.setGraphicsEffect(None)
            self._effects[idx] = None

    def _show_empty(self) -> None:
        self._hint.setText(self._hint.text())
        self._hint.show()
        self._hint.raise_()

    # -------------------------------------------------------------- #
    def paintEvent(self, event) -> None:
        grad = QLinearGradient(self.rect().topLeft(), self.rect().bottomLeft())
        base = QColor(self._a.background)
        top = QColor(base).lighter(135)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, base)
        p = QPainter(self)
        p.fillRect(self.rect(), grad)
        p.end()

    def resizeEvent(self, event) -> None:
        for layer in self._layers:
            layer.setGeometry(self.rect())
        self._hint.setGeometry(self.rect())


class ClockLabel(QLabel):
    """Small clock pill (top-right of the hero)."""

    def __init__(self, use_24h: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._24h = use_24h
        self.setStyleSheet(
            "color: #f5f5f7; background: rgba(20, 20, 26, 140);"
            "border-radius: 17px; padding: 8px 18px; font-size: 21px; font-weight: 500;"
        )
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._tick()

    def _tick(self) -> None:
        now = datetime.now()
        if self._24h:
            self.setText(now.strftime("%H:%M"))
        else:
            self.setText(now.strftime("%I:%M %p").lstrip("0"))
        self.adjustSize()

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)


class BigClock(QWidget):
    """Large screensaver clock: time + date, top-left."""

    def __init__(self, use_24h: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._24h = use_24h
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.time_label = QLabel()
        time_font = QFont()
        time_font.setWeight(QFont.Weight.Light)
        time_font.setPixelSize(100)
        self.time_label.setFont(time_font)
        self.time_label.setStyleSheet("color: rgba(245,245,247,235); background: transparent;")
        layout.addWidget(self.time_label)

        self.date_label = QLabel()
        date_font = QFont()
        date_font.setWeight(QFont.Weight.Medium)
        date_font.setPixelSize(30)
        self.date_label.setFont(date_font)
        self.date_label.setStyleSheet("color: rgba(245,245,247,160); background: transparent;")
        layout.addWidget(self.date_label)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._tick()

    def set_time_size(self, px: int) -> None:
        f = self.time_label.font()
        f.setPixelSize(px)
        self.time_label.setFont(f)
        f2 = self.date_label.font()
        f2.setPixelSize(max(18, int(px * 0.3)))
        self.date_label.setFont(f2)
        self.adjustSize()

    def _tick(self) -> None:
        now = datetime.now()
        if self._24h:
            self.time_label.setText(now.strftime("%H:%M"))
        else:
            self.time_label.setText(now.strftime("%I:%M %p").lstrip("0"))
        self.date_label.setText(now.strftime("%A, %B ") + str(now.day))

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)
