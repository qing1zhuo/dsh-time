"""桌宠交互自检：不真的动鼠标，直接往窗口里塞鼠标消息。"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app import paths  # noqa: E402
from app.win32_pet import (  # noqa: E402
    PetWindow,
    premultiply,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MOUSEMOVE,
    WM_RBUTTONUP,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)


def load_frames(height: int):
    frames = []
    for name in ("whale-girl-open.png", "whale-girl-blink.png"):
        with Image.open(paths.ASSETS_DIR / "pet" / name) as image:
            image = image.convert("RGBA")
            width = max(1, round(image.width * height / image.height))
            frames.append(premultiply(image.resize((width, height), Image.LANCZOS)))
    return frames


def main() -> int:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass

    events: list[tuple[str, object]] = []
    window = PetWindow(load_frames(200), 200, 200, topmost=True, on_event=lambda k, p: events.append((k, p)))
    window.start()
    hwnd = ctypes.c_void_p(window._hwnd)
    state = {"cursor": (300, 300)}
    window._cursor_pos = lambda: state["cursor"]  # type: ignore[method-assign]

    # 1) 原地点一下 -> click
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
    time.sleep(0.15)
    print("after click:", events, window.position)

    # 2) 按住拖 60,40 -> moved，位置跟着变
    events.clear()
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, 0)
    time.sleep(0.05)
    state["cursor"] = (360, 340)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
    time.sleep(0.15)
    print("after drag:", events, window.position)

    # 3) 右键 -> menu，位置是光标位置
    events.clear()
    user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, 0)
    time.sleep(0.15)
    print("after right click:", events)

    # 4) 总在最前开关
    events.clear()
    window.set_topmost(False)
    time.sleep(0.1)
    window.set_topmost(True)
    time.sleep(0.1)
    print("topmost ok, events:", events)

    window.close()
    print("closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
