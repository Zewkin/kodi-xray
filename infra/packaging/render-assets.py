#!/usr/bin/env python3
"""Render the small, code-owned Kodi textures from their SVG design source."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2] / "kodi-addon" / "script.kodi.xray" / "resources"


def icon() -> None:
    image = Image.new("RGB", (512, 512), "#151515")
    draw = ImageDraw.Draw(image)
    accent = "#db0a5b"
    white = "#f0f0f0"
    for start, end in (
        ((86, 160), (166, 160)),
        ((346, 160), (426, 160)),
        ((86, 352), (166, 352)),
        ((346, 352), (426, 352)),
    ):
        draw.line((start, end), fill=accent, width=18)
        for point in (start, end):
            draw.ellipse((point[0] - 9, point[1] - 9, point[0] + 9, point[1] + 9), fill=accent)
    draw.ellipse((164, 164, 348, 348), outline=white, width=18)
    draw.ellipse((210, 228, 234, 252), fill=white)
    draw.ellipse((278, 228, 302, 252), fill=white)
    points = []
    for step in range(41):
        t = step / 40
        inverse = 1 - t
        x = inverse**3 * 218 + 3 * inverse**2 * t * 243 + 3 * inverse * t**2 * 269 + t**3 * 294
        y = inverse**3 * 294 + 3 * inverse**2 * t * 312 + 3 * inverse * t**2 * 312 + t**3 * 294
        points.append((round(x), round(y)))
    draw.line(points, fill=white, width=12, joint="curve")
    for point in (points[0], points[-1]):
        draw.ellipse((point[0] - 6, point[1] - 6, point[0] + 6, point[1] + 6), fill=white)
    image.save(ROOT / "icon.png", optimize=True)


def texture(name: str, color: str) -> None:
    Image.new("RGB", (8, 8), color).save(ROOT / "media" / name, optimize=True)


if __name__ == "__main__":
    icon()
    texture("dark.png", "#151515")
    texture("accent.png", "#db0a5b")
