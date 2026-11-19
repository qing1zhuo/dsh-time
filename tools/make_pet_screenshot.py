"""生成桌宠截图（虚构的示例日程，不涉及真实课表）。

用法：python tools/make_pet_screenshot.py
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

DOCS = Path(__file__).resolve().parents[1] / "docs"


def demo_entries() -> list[Entry]:
    now = datetime.now().replace(second=0, microsecond=0)
    return [
        Entry(
            title="音乐鉴赏",
            kind="once",
            date_str=date.today().isoformat(),
            start=(now - timedelta(minutes=15)).strftime("%H:%M"),
            end=(now + timedelta(minutes=25)).strftime("%H:%M"),
        ),
        Entry(
            title="交实验报告",
            kind="once",
            date_str=date.today().isoformat(),
            start=(now + timedelta(minutes=28)).strftime("%H:%M"),
            end=(now + timedelta(minutes=58)).strftime("%H:%M"),
        ),
    ]


def dispatch(app: FakeApp, pet: DesktopPet) -> None:
    try:
        while True:
            kind, payload = app.events.get_nowait()
            if kind == "pet_click":
                pet.on_click()
            elif kind == "pet_menu":
                pet.show_menu(*payload)
            elif kind == "pet_enter":
                pet.on_hover_enter()
            elif kind == "pet_dragstart":
                pet.on_drag_start()
            elif kind == "pet_wheel":
                pet.on_wheel(int(payload))
    except queue.Empty:
        pass


def pump(app: FakeApp, pet: DesktopPet, root: tk.Tk, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        dispatch(app, pet)
        time.sleep(0.02)


def main() -> int:
    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    app = FakeApp(root)
    app.log = logging.getLogger("screenshot")
    app.entries = demo_entries()
    app.settings.pet_scale = 1.25

    pet = DesktopPet(app)
    hwnd = ctypes.c_void_p(pet._window._hwnd)
    pump(app, pet, root, 0.4)

    x, y = pet.position
    w, h = pet._window.size
    left = max(0, x - 70)
    top = max(0, y - 330)
    width = w + 320
    height = h + 350

    # 在桌宠后面铺一块干净的背景板，避免截到桌面图标或壁纸
    backdrop = tk.Toplevel(root)
    backdrop.overrideredirect(True)
    backdrop.attributes("-topmost", True)
    backdrop.configure(bg="#F2F5FA")
    backdrop.geometry(f"{width}x{height}+{left}+{top}")
    backdrop.update_idletasks()

    # 背景板后建，会盖在桌宠上；把桌宠重新提到最前
    pet._window.set_topmost(True)
    pump(app, pet, root, 0.3)

    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, 0)
    pump(app, pet, root, 0.9)
    if pet._panel is not None and pet._panel.visible:
        pet._panel.lift()

    image = grab(left, top, width, height)
    DOCS.mkdir(parents=True, exist_ok=True)
    image.save(DOCS / "screenshot-pet-hover.png")
    print("saved", DOCS / "screenshot-pet-hover.png", image.size)
    backdrop.destroy()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
