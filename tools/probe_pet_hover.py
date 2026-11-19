"""悬停信息卡 + 滚轮缩放的自检。

用法：python tools/probe_pet_hover.py [输出目录]
"""

from __future__ import annotations

import ctypes
import logging
import queue
import sys
import time
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import theme  # noqa: E402
from app.model import Entry  # noqa: E402
from app.ui_desktop_pet import DesktopPet  # noqa: E402
from tools.probe_pet_app import FakeApp  # noqa: E402
from tools.probe_pet_window import grab  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
WM_MOUSEMOVE = 0x0200
WM_MOUSELEAVE = 0x02A3
WM_MOUSEWHEEL = 0x020A


def dispatch(app: FakeApp, pet: DesktopPet, root: tk.Tk, ignore_leave: bool = False) -> None:
    try:
        while True:
            kind, payload = app.events.get_nowait()
            print("event", kind, payload)
            if kind == "pet_click":
                pet.on_click()
            elif kind == "pet_menu":
                pet.show_menu(*payload)
            elif kind == "pet_moved":
                pet.on_moved(*payload)
            elif kind == "pet_enter":
                pet.on_hover_enter()
            elif kind == "pet_leave":
                if not ignore_leave:
                    pet.on_hover_leave()
            elif kind == "pet_dragstart":
                pet.on_drag_start()
            elif kind == "pet_wheel":
                pet.on_wheel(int(payload))
    except queue.Empty:
        pass


def pump(app: FakeApp, pet: DesktopPet, root: tk.Tk, seconds: float, ignore_leave: bool = False) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        dispatch(app, pet, root, ignore_leave)
        time.sleep(0.02)


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "build/pet-probe")
    out_dir.mkdir(parents=True, exist_ok=True)

    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    app = FakeApp(root)
    app.log = logging.getLogger("probe")
    now = datetime.now()
    app.entries = [
        Entry(
            title="离散数学",
            kind="once",
            date_str=date.today().isoformat(),
            start=(now - timedelta(minutes=15)).strftime("%H:%M"),
            end=(now + timedelta(minutes=25)).strftime("%H:%M"),
        ),
        Entry(
            title="交作业",
            kind="once",
            date_str=date.today().isoformat(),
            start=(now + timedelta(minutes=28)).strftime("%H:%M"),
            end=(now + timedelta(minutes=58)).strftime("%H:%M"),
        ),
    ]
    pet = DesktopPet(app)
    hwnd = ctypes.c_void_p(pet._window._hwnd)
    print("start size", pet._window.size, "pos", pet.position)

    # 悬停 -> 信息卡（合成事件里系统会立刻补一个 leave，这里先忽略）
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, 0)
    pump(app, pet, root, 0.6, ignore_leave=True)
    print("panel visible:", bool(pet._panel and pet._panel.visible))
    x, y = pet.position
    w, h = pet._window.size
    grab(max(0, x - 60), max(0, y - 320), w + 300, h + 340).save(out_dir / "hover-panel.png")

    # 滚轮放大两格
    before_bottom = pet.position[1] + pet._window.size[1]
    for _ in range(2):
        user32.PostMessageW(hwnd, WM_MOUSEWHEEL, (120 << 16) & 0xFFFFFFFF, 0)
    pump(app, pet, root, 0.7)
    after_bottom = pet.position[1] + pet._window.size[1]
    print("after zoom in:", pet.scale, pet._window.size, "panel:", pet._panel.visible)
    print("bottom stays:", before_bottom, after_bottom, "saved:", app.saved[-1:])
    x, y = pet.position
    w, h = pet._window.size
    grab(max(0, x - 60), max(0, y - 320), w + 300, h + 340).save(out_dir / "zoomed.png")

    # 滚轮缩小
    user32.PostMessageW(hwnd, WM_MOUSEWHEEL, ((-120 << 16) & 0xFFFF0000), 0)
    pump(app, pet, root, 0.7)
    print("after zoom out:", pet.scale, pet._window.size)

    # 鼠标离开 -> 收起
    user32.PostMessageW(hwnd, WM_MOUSELEAVE, 0, 0)
    pump(app, pet, root, 0.6)
    print("panel visible after leave:", bool(pet._panel and pet._panel.visible))

    pet.close()
    root.update()
    root.destroy()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
