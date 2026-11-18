"""图标预览：把候选图标按托盘实际尺寸排在一起，方便挑一个最好认的。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app.icons import render  # noqa: E402

SIZES = (16, 20, 24, 32, 48, 128)
STYLES = ("clock", "calendar")


def main() -> None:
    pad = 16
    label_h = 8
    cell_w = sum(s + pad for s in SIZES) + pad
    sheet = Image.new("RGB", (cell_w, (140 + pad) * len(STYLES) + pad), (245, 247, 251))
    for row, style in enumerate(STYLES):
        y = pad + row * (140 + pad)
        x = pad
        for size in SIZES:
            icon = render(size, style)
            sheet.paste(icon, (x, y + (128 - size) // 2), icon)
            # 16px 图放大展示，便于肉眼判断轮廓
            if size <= 24:
                zoom = icon.resize((96, 96), Image.NEAREST)
                sheet.paste(zoom, (x, y + 140 - label_h))
            x += size + pad
    out = Path(__file__).resolve().parents[1] / "build" / "icon-preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
