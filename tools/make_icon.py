"""Erzeugt assets/icon.ico (256x256 PNG-in-ICO) ohne externe Abhaengigkeiten.

Aufruf:  python tools/make_icon.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

SIZE = 256
BG = (24, 24, 24, 255)
ACCENT = (29, 185, 84, 255)
TRANSPARENT = (0, 0, 0, 0)
RADIUS = 56


def _rounded_rect_alpha(x: float, y: float) -> float:
    """Weiche Kante fuer die abgerundeten Ecken (einfaches Antialiasing)."""
    cx = min(max(x, RADIUS), SIZE - RADIUS)
    cy = min(max(y, RADIUS), SIZE - RADIUS)
    distance = math.hypot(x - cx, y - cy)
    if distance <= RADIUS - 1:
        return 1.0
    if distance >= RADIUS + 1:
        return 0.0
    return (RADIUS + 1 - distance) / 2


def _note_alpha(x: float, y: float) -> float:
    # Notenkopf (Ellipse)
    head_cx, head_cy, head_rx, head_ry = 96.0, 172.0, 40.0, 32.0
    ellipse = ((x - head_cx) / head_rx) ** 2 + ((y - head_cy) / head_ry) ** 2
    if ellipse <= 1.0:
        return 1.0
    # Hals
    if 120 <= x <= 140 and 52 <= y <= 176:
        return 1.0
    # Faehnchen
    if 120 <= x <= 196 and 52 <= y <= 74:
        return 1.0
    if 176 <= x <= 196 and 52 <= y <= 108:
        return 1.0
    return 0.0


def _blend(bottom: tuple[int, int, int, int], top: tuple[int, int, int, int], alpha: float):
    return tuple(
        int(round(bottom[i] * (1 - alpha) + top[i] * alpha)) for i in range(4)
    )


def build_png() -> bytes:
    rows = []
    for y in range(SIZE):
        row = bytearray([0])  # Filter 0
        for x in range(SIZE):
            shape = _rounded_rect_alpha(x + 0.5, y + 0.5)
            pixel = _blend(TRANSPARENT, BG, shape)
            note = _note_alpha(x + 0.5, y + 0.5) * shape
            if note:
                pixel = _blend(pixel, ACCENT, note)
            row.extend(pixel)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    png = build_png()
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack(
        "<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22
    ) + png
    target = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ico)
    print(f"geschrieben: {target} ({len(ico)} Bytes)")


if __name__ == "__main__":
    main()
