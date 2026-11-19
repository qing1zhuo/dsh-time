"""把 DesktopPet 接到一个假 app 上，验证点击、右键菜单、位置保存。

用法：python tools/probe_pet_app.py [输出目录]
"""

from __future__ import annotations

import ctypes
import logging
import queue
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import theme  # noqa: E402
from app.store import Settings  # noqa: E402
from app.ui_desktop_pet import DesktopPet  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONUP = 0x0201, 0x0202, 0x0205


class FakeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = Settings()
        self.events: queue.Queue = queue.Queue()
        self.paused = False
        self.saved: list[str] = []
        self.opened = 0
        self.entries: list = []
        self.log = logging.getLogger("probe")
        self.store = self

    def enabled_entries(self) -> list:
        return [entry for entry in self.entries if getattr(entry, "enabled", True)]

    def save(self) -> None:
        self.saved.append(f"{self.settings.pet_x},{self.settings.pet_y}")

    def work_area(self) -> tuple[int, int, int, int]:
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def virtual_screen(self) -> tuple[int, int, int, int]:
        return self.work_area()

    def show_main(self) -> None:
        self.opened += 1

    def new_entry(self) -> None:
        pass

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def set_pet_enabled(self, enabled: bool) -> None:
        self.settings.pet_enabled = bool(enabled)

    def quit_app(self) -> None:
        pass


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "build/pet-probe")
    out_dir.mkdir(parents=True, exist_ok=True)

    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    app = FakeApp(root)
    pet = DesktopPet(app)
    print("pet position", pet.position)

    state = {"cursor": (pet.position[0] + 60, pet.position[1] + 100)}
    pet._window._cursor_pos = lambda: state["cursor"]  # type: ignore[attr-defined]
    hwnd = ctypes.c_void_p(pet._window._hwnd)

    deadline = time.time() + 6
    seen_menu = False
    while time.time() < deadline:
        root.update()
        try:
            while True:
                kind, payload = app.events.get_nowait()
                print("event", kind, payload)
                if kind == "pet_click":
                    pet.on_click()
                elif kind == "pet_menu":
                    pet.show_menu(*payload)
                    seen_menu = True
                elif kind == "pet_moved":
                    pet.on_moved(*payload)
        except queue.Empty:
            pass
        if not seen_menu and time.time() % 1 < 0.1:
            pass
        time.sleep(0.03)

    # 单击
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
    time.sleep(0.2)
    root.update()
    print("opened:", app.opened)

    # 右键菜单
    user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, 0)
    deadline = time.time() + 2
    menu_shown = False
    while time.time() < deadline:
        root.update()
        try:
            while True:
                kind, payload = app.events.get_nowait()
                print("event", kind, payload)
                if kind == "pet_menu":
                    pet.show_menu(*payload)
                    menu_shown = True
                elif kind == "pet_click":
                    pet.on_click()
        except queue.Empty:
            pass
        if menu_shown:
            break
        time.sleep(0.03)
    print("menu shown:", menu_shown)
    time.sleep(0.4)
    root.update()
    # 截图看菜单是否真的弹出来了
    try:
        from tools.probe_pet_window import grab

        x, y = state["cursor"]
        grab(x - 170, y - 60, 470, 420).save(out_dir / "menu.png")
        print("menu screenshot saved")
    except Exception as exc:  # noqa: BLE001
        print("screenshot failed", exc)

    pet.close_menu()
    root.update()

    # 拖动后保存位置
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, 0)
    time.sleep(0.05)
    state["cursor"] = (state["cursor"][0] + 50, state["cursor"][1] + 30)
    user32.PostMessageW(hwnd, 0x0200, 0, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
    deadline = time.time() + 2
    while time.time() < deadline and not app.saved:
        root.update()
        try:
            while True:
                kind, payload = app.events.get_nowait()
                print("event", kind, payload)
                if kind == "pet_moved":
                    pet.on_moved(*payload)
        except queue.Empty:
            pass
        time.sleep(0.03)
    print("saved:", app.saved)

    pet.close()
    root.update()
    # 关掉再打开一次，确认原生窗口能干净地重建
    pet2 = DesktopPet(app)
    print("recreated at", pet2.position)
    pet2.close()
    root.update()
    root.destroy()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
