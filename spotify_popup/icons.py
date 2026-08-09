"""App-/Tray-Icon. Nutzt assets/icon.ico, faellt sonst auf ein gezeichnetes Icon zurueck."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap

from .paths import asset_path, custom_icon_path


def app_icon(size: int = 64, muted: bool = False) -> QIcon:
    if not muted:
        for path in (custom_icon_path(), asset_path("icon.ico")):
            if path:
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    background = QPainterPath()
    background.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    painter.fillPath(background, QColor("#181818"))

    accent = QColor("#666666") if muted else QColor("#1DB954")
    # stilisierte Note: Notenkopf + Hals
    head = QPainterPath()
    head.addEllipse(QRectF(size * 0.22, size * 0.55, size * 0.28, size * 0.24))
    painter.fillPath(head, accent)
    painter.fillRect(QRectF(size * 0.46, size * 0.20, size * 0.07, size * 0.50), accent)
    painter.fillRect(QRectF(size * 0.46, size * 0.20, size * 0.30, size * 0.08), accent)
    painter.end()
    return QIcon(pixmap)
