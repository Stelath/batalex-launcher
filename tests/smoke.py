#!/usr/bin/env python3
"""Offscreen smoke test for batalex-launcher.

Exercises keyboard navigation, app launch/hide/restore, screensaver trigger
and dismissal, and the exit action. Run:

    python tests/smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

FAILURES: list[str] = []


def check(name: str, condition: bool) -> None:
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        FAILURES.append(name)


def main() -> int:
    app = QApplication(["smoke"])

    from batalex_launcher.config import Config
    from batalex_launcher.mainwindow import MainWindow

    cfg = Config.load(REPO_ROOT / "config" / "config.yaml")
    cfg.idle_seconds = 0.3
    cfg.cursor_hide_seconds = 0
    # Make the first app a quick command so launch/restore can be tested.
    cfg.rows[0].items[0].command = "sleep 0.4"

    window = MainWindow(cfg, fullscreen=False)
    window.resize(1720, 980)
    window.show()
    QTest.qWait(300)

    # -- initial focus ---------------------------------------------------- #
    check("initial focus on first tile", window._row == 0 and window._col == 0)
    check("first tile is visually focused", window.tile_rows[0].tiles[0]._focused)

    # -- navigation ------------------------------------------------------- #
    QTest.keyClick(window, Qt.Key.Key_Right)
    check("Right moves focus", window._col == 1)
    check("focus follows in row", window.tile_rows[0].tiles[1]._focused)
    check("old tile unfocused", not window.tile_rows[0].tiles[0]._focused)
    QTest.keyClick(window, Qt.Key.Key_Down)
    check("Down moves to row 2", window._row == 1 and window._col == 1)
    QTest.keyClick(window, Qt.Key.Key_Left)
    check("Left moves focus", window._col == 0)
    QTest.keyClick(window, Qt.Key.Key_Up)
    check("Up moves to row 1", window._row == 0 and window._col == 0)

    # -- launch + restore ------------------------------------------------- #
    # Use the fullscreen hide() path: the offscreen platform cannot minimize.
    window._fullscreen = True
    QTest.keyClick(window, Qt.Key.Key_Return)
    check("window hidden during launch", window._hidden and not window.isVisible())
    QTest.qWait(1200)
    check("window restored after app exit", window._proc is None and window.isVisible())
    window._fullscreen = False

    # -- screensaver ------------------------------------------------------ #
    window._reset_idle()
    QTest.qWait(700)
    check("screensaver opened on idle", window._saver is not None)
    saver = window._saver
    QTest.qWait(600)  # pass the input grace period
    QTest.keyClick(saver, Qt.Key.Key_A)
    QTest.qWait(200)
    check("screensaver dismissed by key", window._saver is None)

    # -- esc_action ------------------------------------------------------- #
    quitting = []
    orig_quit = QApplication.quit
    QApplication.quit = classmethod(lambda cls: quitting.append(True))
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QApplication.quit = orig_quit
    check("Escape requests quit", bool(quitting))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
