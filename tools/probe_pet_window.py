"""桌宠窗口自检：开一个原生分层窗口，截图看它到底长什么样。

用法：
    python tools/probe_pet_window.py [输出目录]

会截三张：常态、眨眼、移动之后。只在开发时用。
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app import paths  # noqa: E402
from app.win32_pet import PetWindow, premultiply  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def grab(left: int, top: int, width: int, height: int) -> Image.Image:
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    gdi32.SelectObject(memory, bitmap)
    gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x00CC0020)

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory)
    user32.ReleaseDC(None, screen)
    return image


def load_frames(height: int) -> list[tuple[int, int, bytes]]:
    frames = []
    for name in ("whale-girl-open.png", "whale-girl-blink.png"):
        with Image.open(paths.ASSETS_DIR / "pet" / name) as image:
            image = image.convert("RGBA")
            width = max(1, round(image.width * height / image.height))
            frames.append(premultiply(image.resize((width, height), Image.LANCZOS)))
    return frames


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "build/pet-probe")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass

    events: list[tuple[str, object]] = []
    height = 260
    frames = load_frames(height)
    window = PetWindow(frames, 120, 160, topmost=True, on_event=lambda k, p: events.append((k, p)))
    window.start()
    print("started", window.position, "size", frames[0][0], frames[0][1])

    time.sleep(0.6)
    x, y = window.position
    width, height_px = frames[0][0], frames[0][1]
    grab(x - 40, y - 40, width + 80, height_px + 80).save(out_dir / "1-idle.png")

    window.blink()
    time.sleep(0.05)
    grab(x - 40, y - 40, width + 80, height_px + 80).save(out_dir / "2-blink.png")

    time.sleep(0.5)
    grab(x - 40, y - 40, width + 80, height_px + 80).save(out_dir / "3-after-blink.png")

    # 暂停提醒 -> 闭眼打盹
    window.set_paused(True)
    time.sleep(0.25)
    grab(x - 40, y - 40, width + 80, height_px + 80).save(out_dir / "4-paused.png")
    window.set_paused(False)
    time.sleep(0.25)
    grab(x - 40, y - 40, width + 80, height_px + 80).save(out_dir / "5-resumed.png")

    print("events", events)
    window.close()
    print("closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
