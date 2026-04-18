"""Generate the trainer app icon assets with PyQt5."""

from __future__ import annotations

import os
import sys

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication


def _ball_path(size: int) -> QPainterPath:
    path = QPainterPath()
    inset = size * 0.12
    rect = QRectF(inset, inset, size - inset * 2, size - inset * 2)
    path.addEllipse(rect)
    return path


def generate_icon(output_dir: str) -> None:
    app = QApplication.instance() or QApplication([])
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    background = QPainterPath()
    background.addRoundedRect(QRectF(10, 10, size - 20, size - 20), 56, 56)
    bg_gradient = QLinearGradient(0, 0, size, size)
    bg_gradient.setColorAt(0.0, QColor("#0b1018"))
    bg_gradient.setColorAt(0.45, QColor("#141d29"))
    bg_gradient.setColorAt(1.0, QColor("#1c2a39"))
    painter.fillPath(background, bg_gradient)

    glow_gradient = QLinearGradient(24, 24, size - 24, size - 24)
    glow_gradient.setColorAt(0.0, QColor(255, 173, 51, 230))
    glow_gradient.setColorAt(0.55, QColor(255, 127, 0, 220))
    glow_gradient.setColorAt(1.0, QColor(209, 74, 12, 220))
    ball = _ball_path(size)
    painter.fillPath(ball, glow_gradient)

    painter.setPen(QPen(QColor("#512308"), 8))
    painter.drawEllipse(QRectF(size * 0.12, size * 0.12, size * 0.76, size * 0.76))
    painter.drawArc(QRectF(size * 0.22, size * 0.18, size * 0.56, size * 0.64), 16 * 120, 16 * 120)
    painter.drawArc(QRectF(size * 0.22, size * 0.18, size * 0.56, size * 0.64), -16 * 60, 16 * 120)
    painter.drawLine(QPointF(size * 0.50, size * 0.12), QPointF(size * 0.50, size * 0.88))
    painter.drawArc(QRectF(size * 0.12, size * 0.34, size * 0.76, size * 0.32), 0, 16 * 180)
    painter.drawArc(QRectF(size * 0.12, size * 0.34, size * 0.76, size * 0.32), 16 * 180, 16 * 180)

    font = QFont("Microsoft YaHei UI", 106)
    font.setBold(True)
    font.setHintingPreference(QFont.PreferFullHinting)
    painter.setFont(font)

    shadow_rect = QRectF(0, size * 0.14, size, size * 0.72)
    painter.setPen(QColor(8, 12, 18, 110))
    painter.drawText(shadow_rect.translated(4, 6), Qt.AlignCenter, "改")

    text_gradient = QLinearGradient(size * 0.28, size * 0.18, size * 0.72, size * 0.82)
    text_gradient.setColorAt(0.0, QColor("#fff7df"))
    text_gradient.setColorAt(0.45, QColor("#fff0c2"))
    text_gradient.setColorAt(1.0, QColor("#ffd87f"))
    painter.setPen(QPen(text_gradient, 1))
    painter.drawText(shadow_rect, Qt.AlignCenter, "改")

    painter.end()

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "trainer_icon.png")
    ico_path = os.path.join(output_dir, "trainer_icon.ico")
    if not pixmap.save(png_path):
        raise RuntimeError("Failed to save PNG icon output.")

    icon = QIcon(pixmap)
    icon_pixmap = icon.pixmap(size, size)
    if not icon_pixmap.save(ico_path):
        raise RuntimeError("Failed to save ICO icon output.")

    if app is not None and not QApplication.instance():
        app.quit()


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    generate_icon(os.path.join(repo_root, "assets"))
