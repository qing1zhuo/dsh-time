"""生成应用图标（托盘 / 窗口 / 快捷方式共用）。

不依赖外部图片资源，首次运行时会自动写出 assets/app.ico。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

TOP = (86, 150, 255)
BOTTOM = (28, 82, 214)
WHITE = (255, 255, 255, 255)
ORANGE = (255, 176, 74, 255)
NAVY = (18, 48, 120, 255)

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _gradient(size: int) -> Image.Image:
    column = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        column.putpixel(
            (0, y),
            tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)),
        )
    return column.resize((size, size), Image.BILINEAR)


def _rounded_mask(size: int, ratio: float = 0.235) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _base(size: int) -> Image.Image:
    image = _gradient(size).convert("RGBA")
    image.putalpha(_rounded_mask(size))
    return image


def _draw_clock(size: int) -> Image.Image:
    scale = 4
    big = size * scale
    image = _base(big)
    draw = ImageDraw.Draw(image)
    cx = cy = big / 2.0
    radius = big * 0.285
    stroke = max(2, int(round(big * 0.062)))
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=WHITE, width=stroke)

    def hand(angle_degrees: float, length: float, width: int) -> None:
        angle = math.radians(angle_degrees - 90)
        x = cx + math.cos(angle) * length
        y = cy + math.sin(angle) * length
        draw.line([cx, cy, x, y], fill=WHITE, width=width)
        draw.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=WHITE)

    hand(300, radius * 0.56, stroke)
    hand(60, radius * 0.78, max(2, int(round(big * 0.048))))
    hub = max(2, int(round(big * 0.045)))
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=WHITE)

    # 右下角的小提示点，让图标在托盘里更有「提醒」感
    dot = big * 0.075
    dx, dy = big * 0.775, big * 0.775
    draw.ellipse([dx - dot, dy - dot, dx + dot, dy + dot], fill=WHITE)
    draw.ellipse([dx - dot * 0.55, dy - dot * 0.55, dx + dot * 0.55, dy + dot * 0.55], fill=(255, 138, 61, 255))

    return image.resize((size, size), Image.LANCZOS)


def _draw_calendar(size: int) -> Image.Image:
    scale = 4
    big = size * scale
    image = _base(big)
    draw = ImageDraw.Draw(image)
    page = [big * 0.20, big * 0.20, big * 0.80, big * 0.82]
    draw.rounded_rectangle(page, radius=big * 0.075, fill=WHITE)
    header = [page[0], page[1], page[2], page[1] + big * 0.145]
    draw.rounded_rectangle(header, radius=big * 0.075, fill=(255, 138, 61, 255))
    draw.rectangle([header[0], header[3] - big * 0.05, header[2], header[3]], fill=(255, 138, 61, 255))
    # 两个装订环
    for x in (big * 0.35, big * 0.65):
        draw.rounded_rectangle(
            [x - big * 0.028, big * 0.13, x + big * 0.028, big * 0.26],
            radius=big * 0.028,
            fill=(255, 255, 255, 235),
        )
    # 日期格
    cell = big * 0.085
    for row in range(2):
        for col in range(3):
            x = big * 0.285 + col * big * 0.145
            y = big * 0.42 + row * big * 0.155
            fill = (40, 92, 214, 255) if (row, col) == (0, 1) else (198, 214, 240, 255)
            draw.rounded_rectangle([x, y, x + cell, y + cell], radius=big * 0.02, fill=fill)
    return image.resize((size, size), Image.LANCZOS)


def render(size: int = 256, style: str = "clock") -> Image.Image:
    if style == "calendar":
        return _draw_calendar(size)
    return _draw_clock(size)


def make_ico(path: Path, style: str = "clock") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    master = render(256, style)
    master.save(path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    return path


def make_png(path: Path, size: int = 256, style: str = "clock") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    render(size, style).save(path, format="PNG")
    return path


if __name__ == "__main__":
    make_ico(Path(__file__).resolve().parents[1] / "assets" / "app.ico")
    print("icon written")
