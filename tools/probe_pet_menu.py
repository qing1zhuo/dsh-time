"""小窗菜单自检：弹一次、截一张、点一行看看回调有没有跑。"""

from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import theme  # noqa: E402
from app.ui_pet_menu import PetMenu  # noqa: E402
from tools.probe_pet_window import grab  # noqa: E402


def main() -> int:
    out = Path("build/pet-probe/menu-custom.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass

    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    theme.setup_ttk(root)

    clicked: list[str] = []
    items = [
        ("command", "打开时间表", lambda: clicked.append("open")),
        ("command", "新建日程", lambda: clicked.append("new")),
        ("sep",),
        ("check", "暂停提醒", True, lambda: clicked.append("pause")),
        ("check", "总在最前", False, lambda: clicked.append("topmost")),
        ("sep",),
        ("command", "隐藏小窗", lambda: clicked.append("hide")),
        ("command", "退出时间表", lambda: clicked.append("quit")),
    ]
    menu = PetMenu(root, items)
    menu.post(420, 300)
    for _ in range(20):
        root.update()
        time.sleep(0.02)
    print("size", menu._width, menu._height, "mapped", menu.winfo_ismapped())
    grab(400, 280, menu._width + 40, menu._height + 40).save(out)
    print("saved", out)

    # 点「总在最前」那一行
    row = next(entry for entry in menu._rows if entry and entry[2] == 4)
    menu._on_click(SimpleNamespace(x=40, y=(row[0] + row[1]) // 2, y_root=0, x_root=0))
    for _ in range(10):
        root.update()
        time.sleep(0.02)
    print("clicked", clicked, "menu alive", menu.winfo_exists() if menu else None)

    # 点外面应该收起
    menu2 = PetMenu(root, items)
    menu2.post(420, 300)
    for _ in range(5):
        root.update()
        time.sleep(0.02)
    menu2._on_click(SimpleNamespace(x=-30, y=-30, y_root=0, x_root=0))
    for _ in range(5):
        root.update()
        time.sleep(0.02)
    print("outside click closed:", not menu2.winfo_exists())
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
