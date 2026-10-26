"""Entry point for batalex-launcher."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication


class _ActivityFilter(QObject):
    """Resets idle/cursor timers on any user input, app-wide."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
        ):
            self._window.notify_activity()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="batalex-launcher",
        description="An Apple TV-style application launcher and screensaver.",
    )
    parser.add_argument("--config", type=Path, help="path to config.yaml")
    parser.add_argument(
        "--windowed", action="store_true", help="run in a normal window instead of fullscreen"
    )
    parser.add_argument(
        "--no-screensaver", action="store_true", help="disable the screensaver for this run"
    )
    parser.add_argument(
        "--screenshot",
        metavar="PATH",
        help="render the home screen once, save it to PATH and exit (for testing)",
    )
    parser.add_argument(
        "--screensaver-shot",
        metavar="PATH",
        help="render the screensaver once, save it to PATH and exit (for testing)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("batalex-launcher")
    app.setStyle("Fusion")

    from .config import Config, ConfigError

    try:
        cfg = Config.load(args.config)
    except ConfigError as exc:
        parser.exit(2, f"error: {exc}\n")

    if args.no_screensaver:
        cfg.screensaver.enabled = False

    from .mainwindow import MainWindow
    from .widgets import pick_font_family

    family = cfg.appearance.font_family or pick_font_family()
    if family:
        cfg.appearance.font_family = family
        font = app.font()
        font.setFamily(family)
        app.setFont(font)

    # Dark palette everywhere: the window paints its own background, this
    # covers scroll-area viewports and any other stragglers.
    from PySide6.QtGui import QColor, QPalette

    bg = QColor(cfg.appearance.background)
    text = QColor(cfg.appearance.text)
    panel = QColor(cfg.appearance.background).lighter(140)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, bg)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, panel)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, panel)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    app.setPalette(palette)

    window = MainWindow(cfg, fullscreen=not args.windowed)
    window.resize(1720, 980)
    if args.windowed or args.screenshot or args.screensaver_shot:
        window.show()
    else:
        window.showFullScreen()

    _ActivityFilter(window)

    def _grab(widget, path: str) -> None:
        widget.grab().save(path)
        print(f"[batalex-launcher] saved screenshot to {path}")
        app.quit()

    if args.screenshot:
        QTimer.singleShot(2000, lambda: _grab(window, args.screenshot))
    if args.screensaver_shot:
        def _grab_saver() -> None:
            from .screensaver import ScreensaverOverlay

            saver = ScreensaverOverlay(cfg)
            saver.resize(1720, 980)
            saver.show()
            QTimer.singleShot(1200, lambda: _grab(saver, args.screensaver_shot))

        QTimer.singleShot(800, _grab_saver)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
