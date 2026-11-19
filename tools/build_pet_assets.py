"""把鲸鱼娘素材裁成桌宠用的两组帧（睁眼 / 闭眼）。

源图来自 YunYueSama/codex-deepseek-pet 的 assets/whale/idle-front.png：
一张 2048x1024 的透明底图，左右各一帧 —— 左边睁眼，右边闭眼。

用法：
    python tools/build_pet_assets.py            # 直接下载源图并生成
    python tools/build_pet_assets.py --check    # 只检查已生成的素材
"""

from __future__ import annotations

import argparse
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "pet"
SOURCE_URL = (
    "https://raw.githubusercontent.com/YunYueSama/codex-deepseek-pet/main/assets/whale/idle-front.png"
)
CACHE = ROOT / "build" / "pet-candidates" / "codex-idle-front.png"
PAD = 10
SHADOW_ALPHA = 46


def load_source() -> Image.Image:
    if CACHE.exists():
        return Image.open(CACHE).convert("RGBA")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "timetable-build"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    CACHE.write_bytes(raw)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def split_frames(sheet: Image.Image) -> tuple[Image.Image, Image.Image]:
    half = sheet.width // 2
    left = sheet.crop((0, 0, half, sheet.height))
    right = sheet.crop((half, 0, sheet.width, sheet.height))

    boxes = [frame.getchannel("A").getbbox() for frame in (left, right)]
    if any(box is None for box in boxes):
        raise SystemExit("源图里没找到角色像素")
    union = (
        min(box[0] for box in boxes) - PAD,
        min(box[1] for box in boxes) - PAD,
        max(box[2] for box in boxes) + PAD,
        max(box[3] for box in boxes) + PAD,
    )
    return left.crop(union), right.crop(union)


def add_ground_shadow(frame: Image.Image) -> Image.Image:
    """在脚下压一层很淡的椭圆阴影，贴在桌面壁上更像站着的。"""
    width, height = frame.size
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    w = int(width * 0.62)
    h = max(10, int(height * 0.035))
    x0 = (width - w) // 2
    y0 = height - h - 4
    draw.ellipse((x0, y0, x0 + w, y0 + h), fill=(18, 24, 38, SHADOW_ALPHA))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(2, h // 2)))
    return Image.alpha_composite(shadow, frame)


def build(check_only: bool = False) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = {
        "whale-girl-open.png": 0,
        "whale-girl-blink.png": 1,
    }
    if check_only:
        ok = True
        for name in targets:
            path = OUT_DIR / name
            if not path.exists():
                print(f"缺少 {path}")
                ok = False
                continue
            with Image.open(path) as image:
                print(f"{name}: {image.size} {image.mode}")
        return 0 if ok else 1

    open_frame, blink_frame = split_frames(load_source())
    frames = (add_ground_shadow(open_frame), add_ground_shadow(blink_frame))
    for name, frame in zip(targets, frames):
        path = OUT_DIR / name
        frame.save(path, optimize=True)
        print(f"{name}: {frame.size} -> {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
