"""The main launcher window: hero on top, app rows below, idle tracking,
screensaver triggering, and app launching."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QProcess, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import AppItem, Config
from .hero import Hero
from .screensaver import ScreensaverOverlay
from .widgets import TileRow


class MainWindow(QWidget):
    def __init__(self, cfg: Config, fullscreen: bool = True):
        super().__init__()
        self.cfg = cfg
        self._fullscreen = fullscreen
        self.setWindowTitle("batalex-launcher")
        if fullscreen:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Hero (big picture)
        if cfg.hero.enabled:
            self.hero = Hero(cfg, self)
            root.addWidget(self.hero, 0)
        else:
            self.hero = None

        # App rows
        self.rows_scroll = QScrollArea(self)
        self.rows_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.rows_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.rows_scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        rows_layout = QVBoxLayout(container)
        rows_layout.setContentsMargins(0, 24, 0, 48)
        rows_layout.setSpacing(cfg.appearance.row_spacing)
        self.tile_rows: list[TileRow] = []
        for i, row in enumerate(cfg.rows):
            tile_row = TileRow(row.title, row.items, cfg.appearance)
            tile_row.activated.connect(
                lambda col, r=i: self._on_tile_activated(r, col)
            )
            rows_layout.addWidget(tile_row)
            self.tile_rows.append(tile_row)
        rows_layout.addStretch(1)
        self.rows_scroll.setWidget(container)
        self.rows_scroll.setWidgetResizable(True)
        root.addWidget(self.rows_scroll, 1)

        self._row = -1
        self._col = -1

        # Timers
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._start_screensaver)
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.timeout.connect(self._blank_cursor)

        self._saver: ScreensaverOverlay | None = None
        self._proc: QProcess | None = None
        self._hidden = False

        # Toast
        self._toast = QLabel(self)
        self._toast.setStyleSheet(
            "color: #f5f5f7; background: rgba(28, 28, 34, 220);"
            "border-radius: 20px; padding: 14px 28px; font-size: 22px;"
        )
        self._toast.adjustSize()
        self._toast.hide()
        self._toast_effect: QGraphicsOpacityEffect | None = None

    # ------------------------------------------------------------------ #
    def showEvent(self, event) -> None:
        self.set_logical(0, 0, animate=False)
        self._reset_idle()
        self._unblank_cursor()
        if self.hero is not None:
            self.hero.start()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        if self.hero is not None:
            self.hero.setFixedHeight(
                max(220, int(self.height() * self.cfg.hero.height_ratio))
            )
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QColor, QPainter

        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.cfg.appearance.background))
        p.end()

    # ------------------------------------------------------------------ #
    # Focus / navigation
    # ------------------------------------------------------------------ #
    def set_logical(self, row: int, col: int, animate: bool = True) -> None:
        if not self.tile_rows:
            return
        row = max(0, min(row, len(self.tile_rows) - 1))
        col = max(0, min(col, self.tile_rows[row].count() - 1))
        if row == self._row and col == self._col:
            return
        self._row = row
        self._col = col
        for i, tile_row in enumerate(self.tile_rows):
            if i == row:
                tile_row.set_current(col, animate=animate)
            else:
                tile_row.set_current(
                    min(tile_row.current(), tile_row.count() - 1), animate=False
                )
                tile_row.tiles[tile_row.current()].set_focused(False)
        self._ensure_row_visible(row)

    def _ensure_row_visible(self, row: int) -> None:
        tile_row = self.tile_rows[row]
        bar = self.rows_scroll.verticalScrollBar()
        y = tile_row.y() + tile_row.title_label.y()
        h = tile_row.height()
        if y < bar.value():
            bar.setValue(y)
        elif y + h > bar.value() + self.rows_scroll.viewport().height():
            bar.setValue(y + h - self.rows_scroll.viewport().height())

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.set_logical(self._row, self._col - 1)
        elif key == Qt.Key.Key_Right:
            self.set_logical(self._row, self._col + 1)
        elif key == Qt.Key.Key_Up:
            self.set_logical(self._row - 1, self._col)
        elif key == Qt.Key.Key_Down:
            self.set_logical(self._row + 1, self._col)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            item = self.cfg.rows[self._row].items[self._col]
            self._activate_item(item)
        elif key == Qt.Key.Key_Escape:
            self._esc_pressed()
        else:
            super().keyPressEvent(event)
        self.notify_activity()

    def _esc_pressed(self) -> None:
        action = self.cfg.esc_action
        if action == "exit":
            QApplication.quit()
        elif action == "desktop":
            self._go_desktop()

    def _on_tile_activated(self, row: int, col: int) -> None:
        self.set_logical(row, col)
        item = self.cfg.rows[row].items[col]
        self._activate_item(item)

    # ------------------------------------------------------------------ #
    # Launching
    # ------------------------------------------------------------------ #
    def _activate_item(self, item: AppItem) -> None:
        if item.action == "exit":
            QApplication.quit()
        elif item.action == "desktop":
            self._go_desktop()
        elif item.action == "screensaver":
            self._start_screensaver()
        elif item.command:
            self._launch(item)

    def _launch(self, item: AppItem) -> None:
        if self._proc is not None:
            self.toast("Already running an app…")
            return
        proc = QProcess(self)
        proc.finished.connect(self._on_proc_finished)
        proc.errorOccurred.connect(self._on_proc_error)
        self._proc = proc
        self._launched_command = item.command
        if self.cfg.hide_on_launch:
            self._hide_for_launch()
        proc.start("sh", ["-c", item.command])
        self._reset_idle()

    def _hide_for_launch(self) -> None:
        self._hidden = True
        if self.hero is not None:
            self.hero.stop()
        if self._fullscreen:
            self.hide()
        else:
            self.showMinimized()

    def _restore_from_launch(self) -> None:
        self._hidden = False
        if self._fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
        self.activateWindow()
        self.raise_()
        if self.hero is not None and self._saver is None:
            self.hero.start()
        self._reset_idle()
        self._unblank_cursor()

    def _on_proc_finished(self, code: int, status) -> None:
        self._proc = None
        if self.cfg.restore_on_exit or not self.cfg.hide_on_launch:
            self._restore_from_launch()

    def _on_proc_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            command = getattr(self, "_launched_command", "")
            self.toast(f"Failed to launch: {command}")
            self._proc = None
            self._restore_from_launch()

    def _go_desktop(self) -> None:
        if self.cfg.desktop_command:
            QProcess.startDetached("sh", ["-c", self.cfg.desktop_command])
        # Stay running; come back via the taskbar / Alt-Tab.
        if self.hero is not None:
            self.hero.stop()
        self._hidden = True
        self.showMinimized()

    # ------------------------------------------------------------------ #
    # Screensaver / idle
    # ------------------------------------------------------------------ #
    def notify_activity(self) -> None:
        if self._saver is not None or self._hidden:
            return
        self._reset_idle()
        self._unblank_cursor()

    def _reset_idle(self) -> None:
        self._idle_timer.stop()
        if self.cfg.screensaver.enabled and self.cfg.idle_seconds > 0:
            self._idle_timer.start(int(self.cfg.idle_seconds * 1000))

    def _unblank_cursor(self) -> None:
        self.unsetCursor()
        self._cursor_timer.stop()
        if self.cfg.cursor_hide_seconds > 0:
            self._cursor_timer.start(int(self.cfg.cursor_hide_seconds * 1000))

    def _blank_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.BlankCursor)

    def _start_screensaver(self) -> None:
        if self._saver is not None or not self.cfg.screensaver.enabled or self._hidden:
            return
        self._saver = ScreensaverOverlay(self.cfg)
        self._saver.dismissed.connect(self._on_saver_dismissed)
        if self.hero is not None:
            self.hero.stop()
        screen = self.screen() or QApplication.primaryScreen()
        self._saver.show_fullscreen(screen)

    def _on_saver_dismissed(self) -> None:
        saver = self._saver
        self._saver = None
        if saver is not None:
            saver.deleteLater()
        if self.hero is not None:
            self.hero.start()
        self._reset_idle()
        self._unblank_cursor()

    # ------------------------------------------------------------------ #
    def toast(self, message: str, duration_ms: int = 3000) -> None:
        self._toast.setText(message)
        self._toast.adjustSize()
        self._toast.move(
            (self.width() - self._toast.width()) // 2, self.height() - self._toast.height() - 90
        )
        self._toast_effect = QGraphicsOpacityEffect(self._toast)
        self._toast.setGraphicsEffect(self._toast_effect)
        self._toast.show()
        self._toast.raise_()
        anim = QPropertyAnimation(self._toast_effect, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._toast_anim = anim
        QTimer.singleShot(duration_ms, self._fade_toast)

    def _fade_toast(self) -> None:
        if self._toast_effect is None:
            return
        anim = QPropertyAnimation(self._toast_effect, b"opacity", self)
        anim.setDuration(500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self._toast.hide)
        anim.start()
        self._toast_anim = anim

    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:
        if self.hero is not None:
            self.hero.stop()
        if self._saver is not None:
            self._saver.close()
        super().closeEvent(event)
