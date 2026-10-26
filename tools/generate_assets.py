#!/usr/bin/env python3
"""Generate the bundled demo assets: app icon tiles (rectangular images)
and sample screensaver artwork.

Usage:  python tools/generate_assets.py
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "assets" / "icons"
SCREENSAVER_DIR = ROOT / "assets" / "screensaver"

ICON_W, ICON_H = 640, 360


def base_gradient(c1: str, c2: str, angle: float = 35.0) -> QLinearGradient:
    rad = math.radians(angle)
    x, y = math.cos(rad), math.sin(rad)
    g = QLinearGradient(
        QPointF(ICON_W / 2 - x * ICON_W / 2, ICON_H / 2 - y * ICON_H / 2),
        QPointF(ICON_W / 2 + x * ICON_W / 2, ICON_H / 2 + y * ICON_H / 2),
    )
    g.setColorAt(0.0, QColor(c1))
    g.setColorAt(1.0, QColor(c2))
    return g


def soft_shadow(p: QPainter, radius: float = 18.0) -> None:
    p.setPen(QPen(QColor(0, 0, 0, 60), 2))
    _ = radius


def draw_terminal(p: QPainter) -> None:
    font = QFont("DejaVu Sans Mono")
    font.setBold(True)
    font.setPixelSize(150)
    p.setFont(font)
    p.setPen(QColor("#3ddc68"))
    p.drawText(QRectF(0, -18, ICON_W, ICON_H), Qt.AlignmentFlag.AlignCenter, ">_")


def draw_files(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    # soft shadow behind the folder
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawRoundedRect(QRectF(196, 118, 278, 156), 16, 16)
    # back tab
    tab = QPainterPath()
    tab.addPolygon(
        [
            QPointF(190, 140),
            QPointF(268, 140),
            QPointF(300, 106),
            QPointF(450, 106),
            QPointF(450, 150),
            QPointF(190, 150),
        ]
    )
    p.setBrush(QColor("#dfe5ef"))
    p.drawPath(tab)
    # body
    body = QPainterPath()
    body.addRoundedRect(QRectF(182, 128, 276, 134), 14, 14)
    p.setBrush(QColor("#eef1f7"))
    p.drawPath(body)
    # darker front panel
    front = QPainterPath()
    front.addRoundedRect(QRectF(182, 168, 276, 94), 14, 14)
    p.setBrush(QColor("#c7d0df"))
    p.drawPath(front)
    p.setBrush(QColor("#eef1f7"))
    p.drawRect(QRectF(182, 168, 276, 22))


def draw_web(p: QPainter) -> None:
    cx, cy, r = ICON_W / 2, ICON_H / 2, 105
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 235), 16))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.drawEllipse(QPointF(cx, cy), r, r * 0.42)
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.setPen(QPen(QColor(255, 255, 255, 235), 13))
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))


def draw_music(p: QPainter) -> None:
    font = QFont("DejaVu Sans")
    font.setPixelSize(190)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 240))
    p.drawText(QRectF(0, -30, ICON_W, ICON_H), Qt.AlignmentFlag.AlignCenter, "♪")


def draw_videos(p: QPainter) -> None:
    tri = QPainterPath()
    cx, cy = ICON_W / 2 - 14, ICON_H / 2
    tri.moveTo(cx - 55, cy - 85)
    tri.lineTo(cx - 55, cy + 85)
    tri.lineTo(cx + 95, cy)
    tri.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 240))
    p.drawPath(tri)


def draw_photos(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(180, 78, 280, 204), 18, 18)
    p.drawPath(frame)
    # mountains + sun clipped inside the frame
    p.setClipPath(frame)
    p.setBrush(QColor("#ff9a3d"))
    p.drawRect(QRectF(180, 78, 280, 204))
    p.setBrush(QColor(255, 224, 130))
    p.drawEllipse(QPointF(395, 140), 30, 30)
    hills = QPainterPath()
    hills.moveTo(180, 282)
    hills.lineTo(285, 172)
    hills.lineTo(360, 252)
    hills.lineTo(410, 205)
    hills.lineTo(460, 255)
    hills.lineTo(460, 282)
    hills.closeSubpath()
    p.setBrush(QColor("#8a4b1d"))
    p.drawPath(hills)
    p.setClipping(False)


def draw_settings(p: QPainter) -> None:
    cx, cy, r_out, r_in = ICON_W / 2, ICON_H / 2, 96, 58
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    for i in range(8):
        angle = i * math.pi / 4
        tooth = QPainterPath()
        x = cx + math.cos(angle) * r_out
        y = cy + math.sin(angle) * r_out
        tooth.addRoundedRect(QRectF(x - 22, y - 22, 44, 44), 10, 10)
        p.drawPath(tooth)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QPointF(cx, cy), r_out - 6, r_out - 6)
    p.setBrush(QColor("#5a5a63"))
    p.drawEllipse(QPointF(cx, cy), r_in, r_in)


def draw_desktop(p: QPainter) -> None:
    p.setBrush(QColor(255, 255, 255, 235))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(170, 92, 300, 172), 16, 16)
    p.setBrush(QColor("#0aa89f"))
    p.drawRoundedRect(QRectF(186, 108, 268, 140), 10, 10)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawRect(QRectF(292, 268, 56, 14))
    p.drawRoundedRect(QRectF(252, 284, 136, 12), 6, 6)


def draw_exit(p: QPainter) -> None:
    cx, cy, r = ICON_W / 2, ICON_H / 2 + 8, 84
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 240), 20, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 45 * 16, 270 * 16)
    p.drawLine(QPointF(cx, cy - r - 16), QPointF(cx, cy))


def draw_screensaver(p: QPainter) -> None:
    # A moon + "zzz" style night icon.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 240))
    p.drawEllipse(QPointF(ICON_W / 2 - 20, ICON_H / 2), 82, 82)
    p.setBrush(QColor("#3b3b9e"))
    p.drawEllipse(QPointF(ICON_W / 2 + 14, ICON_H / 2 - 26), 72, 72)
    font = QFont("DejaVu Sans")
    font.setPixelSize(64)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 220))
    p.drawText(QPointF(ICON_W / 2 + 74, 120), "z")
    font.setPixelSize(84)
    p.setFont(font)
    p.drawText(QPointF(ICON_W / 2 + 108, 96), "Z")


ICONS = {
    "terminal": ("#3a3f4b", "#14161b", draw_terminal),
    "files": ("#5db4ff", "#1c69d4", draw_files),
    "web": ("#35c3ff", "#0a5cff", draw_web),
    "music": ("#ff6aa9", "#d92057", draw_music),
    "videos": ("#b47bff", "#5b2bd6", draw_videos),
    "photos": ("#ffc24b", "#ff7a18", draw_photos),
    "settings": ("#9a9aa5", "#3c3c44", draw_settings),
    "desktop": ("#3fe0d0", "#0b8f86", draw_desktop),
    "exit": ("#ff6f66", "#c22e28", draw_exit),
    "screensaver": ("#5b5bd6", "#23236e", draw_screensaver),
}


def gen_icons() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for name, (c1, c2, painter) in ICONS.items():
        from PySide6.QtGui import QImage

        img = QImage(ICON_W, ICON_H, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(base_gradient(c1, c2)))
        p.drawRect(img.rect())
        # subtle top gloss
        gloss = QLinearGradient(0, 0, 0, ICON_H)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 26))
        gloss.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.setBrush(gloss)
        p.drawRect(img.rect())
        painter(p)
        p.end()
        path = ICONS_DIR / f"{name}.png"
        img.save(str(path))
        print(f"wrote {path.relative_to(ROOT)}")


def gen_screensaver(count: int = 5) -> None:
    SCREENSAVER_DIR.mkdir(parents=True, exist_ok=True)
    palettes = [
        ("#0b1026", ["#1b3a6b", "#3b2d7a", "#0e6b5c"]),
        ("#14091f", ["#5c1b6b", "#8a2d52", "#1b3a8a"]),
        ("#041a1a", ["#0e6b5c", "#1b8a6e", "#135a7a"]),
        ("#1f0d08", ["#8a4b1d", "#b0622d", "#6b1b3a"]),
        ("#0a0f1e", ["#2456a8", "#3a7ad6", "#16294d"]),
    ]
    W, H = 1920, 1080
    for i, (base, blobs) in enumerate(palettes):
        rng = random.Random(1000 + i)
        from PySide6.QtGui import QImage

        img = QImage(W, H, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = QLinearGradient(0, 0, W, H)
        bg.setColorAt(0.0, QColor(base).lighter(115))
        bg.setColorAt(1.0, QColor(base))
        p.fillRect(img.rect(), bg)
        for color in blobs:
            for _ in range(2):
                cx = rng.uniform(0.1, 0.9) * W
                cy = rng.uniform(0.1, 0.9) * H
                r = rng.uniform(0.25, 0.55) * W
                blob = QRadialGradient(QPointF(cx, cy), r)
                c = QColor(color)
                blob.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 150))
                blob.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                p.fillRect(img.rect(), blob)
        # vignette
        vig = QRadialGradient(QPointF(W / 2, H / 2), W * 0.72)
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(img.rect(), vig)
        p.end()
        path = SCREENSAVER_DIR / f"aurora-{i + 1}.png"
        img.save(str(path))
        print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    _ = QApplication(sys.argv)
    gen_icons()
    gen_screensaver()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
