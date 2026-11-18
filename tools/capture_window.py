"""把指定窗口的内容抓成 PNG（不要求窗口在最前面）。

用法：python tools/capture_window.py "时间表" build/window.png
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

PW_RENDERFULLCONTENT = 0x00000002
BI_RGB = 0


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


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


def find_window(title: str, timeout: float = 8.0) -> int:
    """按精确标题找 Tk 顶层窗口，最多等 timeout 秒。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = user32.FindWindowW("TkTopLevel", title)
        if hwnd:
            return hwnd
        found: list[int] = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam, bucket=found):  # noqa: ANN001
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if buffer.value == title:
                    bucket.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        if found:
            return found[0]
        time.sleep(0.25)
    return 0


def capture_hwnd(hwnd: int, out: Path) -> bool:
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return False

    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    ok = user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT)

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)

    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(hwnd, window_dc)
    return bool(ok)


def capture(title: str, out: Path) -> int:
    user32.SetProcessDPIAware()
    hwnd = find_window(title)
    if not hwnd:
        print(f"window not found: {title}")
        return 1
    ok = capture_hwnd(hwnd, out)
    print(f"printwindow={int(ok)} -> {out}")
    return 0 if ok else 2


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "时间表"
    target = Path(sys.argv[2] if len(sys.argv) > 2 else "build/window.png")
    raise SystemExit(capture(title, target))
