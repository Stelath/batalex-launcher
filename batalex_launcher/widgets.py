"""Apple TV style widgets: focusable tiles and horizontally scrolling rows."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import Appearance, AppItem


def pick_font_family() -> str:
    """First nice sans-serif family available on this system."""
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    for want in (
        "Inter",
        "SF Pro Display",
        "SF Pro Text",
        "Noto Sans",
        "Ubuntu",
        "Cantarell",
        "Liberation Sans",
        "DejaVu Sans",
    ):
        if want in families:
            return want
    return ""


def cover_source(pm: QPixmap, target: QRectF) -> QRectF:
    """Source rect of ``pm`` that cover-crops it into ``target``."""
    sw, sh = pm.width(), pm.height()
    scale = max(target.width() / sw, target.height() / sh)
    dw, dh = target.width() / scale, target.height() / scale
    return QRectF((sw - dw) / 2.0, (sh - dh) / 2.0, dw, dh)


class Tile(QWidget):
    """One app: a rounded-rectangle icon image with a label underneath.

    The widget is intentionally larger than the visible rectangle so the
    focus zoom and drop shadow can overflow the image without being clipped
    by the layout.
    """

    hovered = Signal(object)
    pressed = Signal(object)

    def __init__(self, item: AppItem, appearance: Appearance, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self._a = appearance
        z = appearance.focus_zoom
        self._pad_x = appearance.tile_width * (z - 1) / 2.0 + 8
        self._pad_y = appearance.tile_height * (z - 1) / 2.0 + 8
        self._label_h = 38
        self._zoom = 1.0
        self._focused = False
        self.setFixedSize(
            int(appearance.tile_width + 2 * self._pad_x),
            int(appearance.tile_height + 2 * self._pad_y + self._label_h),
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 10)
        self._shadow.setBlurRadius(24)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(self._shadow)

        self._pixmap: QPixmap | None = None
        if item.icon is not None:
            pm = QPixmap(str(item.icon))
            if not pm.isNull():
                self._pixmap = pm

        self._zoom_anim = QPropertyAnimation(self, b"zoom", self)
        self._zoom_anim.setDuration(180)
        self._zoom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._shadow_anim.setDuration(180)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -------------------------------------------------------------- #
    def getZoom(self) -> float:
        return self._zoom

    def setZoom(self, value: float) -> None:
        self._zoom = value
        self.update()

    zoom = Property(float, getZoom, setZoom)

    # -------------------------------------------------------------- #
    def set_focused(self, focused: bool) -> None:
        if self._focused == focused:
            return
        self._focused = focused
        self._zoom_anim.stop()
        self._zoom_anim.setStartValue(self._zoom)
        self._zoom_anim.setEndValue(self._a.focus_zoom if focused else 1.0)
        self._zoom_anim.start()
        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(self._shadow.blurRadius())
        self._shadow_anim.setEndValue(54.0 if focused else 24.0)
        self._shadow_anim.start()
        color = QColor(self._a.accent if focused else QColor(0, 0, 0))
        color.setAlpha(110 if focused else 120)
        self._shadow.setColor(color)
        self.update()

    def image_rect(self) -> QRectF:
        z = self._zoom
        tw, th = self._a.tile_width, self._a.tile_height
        cx = self.width() / 2.0
        cy = self._pad_y + th / 2.0
        w, h = tw * z, th * z
        return QRectF(cx - w / 2.0, cy - h / 2.0, w, h)

    # -------------------------------------------------------------- #
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.image_rect()
        radius = self._a.tile_radius * (self._zoom ** 0.6)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        if self._pixmap is not None:
            p.setClipPath(path)
            p.drawPixmap(rect, self._pixmap, cover_source(self._pixmap, rect))
            p.setClipping(False)
        else:
            # Placeholder: accent gradient with the app's initial letter.
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(self._a.accent))
            grad.setColorAt(1.0, QColor(self._a.background).lighter(175))
            p.fillPath(path, grad)
            font = QFont(self._a.font_family)
            font.setPixelSize(int(rect.height() * 0.44))
            font.setWeight(QFont.Weight.DemiBold)
            p.setFont(font)
            p.setPen(QColor(255, 255, 255, 215))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.item.name[:1].upper())

        if self._focused:
            p.setPen(QPen(QColor(255, 255, 255, 72), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        label_rect = QRectF(0.0, self.height() - self._label_h, self.width(), self._label_h)
        font = QFont(self._a.font_family)
        font.setPixelSize(self._a.tile_label_size)
        font.setWeight(QFont.Weight.DemiBold if self._focused else QFont.Weight.Medium)
        p.setFont(font)
        p.setPen(QColor(self._a.text if self._focused else self._a.text_dim))
        p.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self.item.name,
        )
        p.end()

    # -------------------------------------------------------------- #
    def enterEvent(self, event) -> None:
        self.hovered.emit(self)
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit(self)
        super().mousePressEvent(event)


class TileRow(QWidget):
    """A labelled horizontal row of tiles with smooth scrolling."""

    activated = Signal(int)  # tile index

    def __init__(
        self,
        title: str,
        items: list[AppItem],
        appearance: Appearance,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._a = appearance
        self.tiles: list[Tile] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(appearance.side_margin, 0, appearance.side_margin, 0)
        layout.setSpacing(10)

        self.title_label = QLabel(title)
        title_font = QFont(appearance.font_family)
        title_font.setPixelSize(appearance.row_label_size)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(
            f"color: {appearance.text}; background: transparent;"
        )
        layout.addWidget(self.title_label)

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.container = QWidget()
        hbox = QHBoxLayout(self.container)
        zoom_pad = appearance.tile_width * (appearance.focus_zoom - 1) / 2.0 + 8
        hbox.setContentsMargins(int(zoom_pad), 2, int(zoom_pad), 14)
        hbox.setSpacing(4)
        for item in items:
            tile = Tile(item, appearance)
            tile.hovered.connect(self._on_hover)
            tile.pressed.connect(self._on_press)
            hbox.addWidget(tile, 0, Qt.AlignmentFlag.AlignTop)
            self.tiles.append(tile)
        hbox.addStretch(1)
        self.scroll.setWidget(self.container)
        self.scroll.setWidgetResizable(True)
        tile_h = appearance.tile_height + 2 * (
            appearance.tile_height * (appearance.focus_zoom - 1) / 2.0 + 8
        ) + 38
        self.scroll.setFixedHeight(int(tile_h) + 16)
        layout.addWidget(self.scroll)

        self._current = 0
        self._scroll_anim = QPropertyAnimation(
            self.scroll.horizontalScrollBar(), b"value", self
        )
        self._scroll_anim.setDuration(250)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -------------------------------------------------------------- #
    def count(self) -> int:
        return len(self.tiles)

    def current(self) -> int:
        return self._current

    def set_current(self, index: int, animate: bool = True) -> None:
        if not self.tiles:
            return
        index = max(0, min(index, len(self.tiles) - 1))
        if index == self._current and self.tiles[index]._focused:
            return
        self.tiles[self._current].set_focused(False)
        self._current = index
        self.tiles[index].set_focused(True)
        self._scroll_to(index, animate)

    def _scroll_to(self, index: int, animate: bool) -> None:
        tile = self.tiles[index]
        target = tile.x() + tile.width() / 2.0 - self.scroll.viewport().width() / 2.0
        bar = self.scroll.horizontalScrollBar()
        target = max(bar.minimum(), min(int(target), bar.maximum()))
        self._scroll_anim.stop()
        if not animate:
            bar.setValue(target)
            return
        self._scroll_anim.setStartValue(bar.value())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()

    def _on_hover(self, tile: Tile) -> None:
        if tile in self.tiles:
            self.set_current(self.tiles.index(tile))

    def _on_press(self, tile: Tile) -> None:
        if tile in self.tiles:
            self.set_current(self.tiles.index(tile))
            self.activated.emit(self._current)

    def wheelEvent(self, event) -> None:
        bar = self.scroll.horizontalScrollBar()
        bar.setValue(bar.value() + int(event.angleDelta().y() * 1.5))
        event.accept()
