"""小窗右键菜单：自己画的卡片式菜单。

用 Tk 自带的 tk_popup 时，主窗口是隐藏的，菜单有时候根本弹不出来、有时候
收不回去；这里改成自己的 Toplevel：圆角卡片 + 悬停高亮 + 点外面自动收起。
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from tkinter import font as tkfont

from .theme import COLORS, FAMILY, px, round_rect

TRANSPARENT_KEY = "#FF00FE"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.restype = ctypes.c_int
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = ctypes.c_int

VK_LBUTTON = 0x01
WATCH_MS = 70

ITEM_HEIGHT = 30
SEPARATOR_HEIGHT = 9
PAD_Y = 6
MIN_WIDTH = 148


class PetMenu(tk.Toplevel):
    """items: [("command", 文案, 回调) / ("check", 文案, 是否勾选, 回调) / ("sep",)]"""

    def __init__(self, root: tk.Misc, items, on_close=None) -> None:  # noqa: ANN001
        super().__init__(root)
        self.withdraw()
        self.overrideredirect(True)
        self.title("时间表小窗菜单")
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.configure(bg=TRANSPARENT_KEY)

        self._items = items
        self._on_close = on_close
        self._closing = False
        self._hover: int | None = None
        self._hover_items: dict[int, int] = {}
        self._rows: list[tuple[int, int, int] | None] = []
        self._armed = False
        self._focus_job: str | None = None
        self._watch_job: str | None = None
        self._pressed = False

        self._font = tkfont.Font(family=FAMILY, size=10)
        self._font_bold = tkfont.Font(family=FAMILY, size=10, weight="bold")
        self._width, self._height = self._measure()
        self.canvas = tk.Canvas(
            self,
            width=self._width,
            height=self._height,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        self.canvas.pack()
        self._draw()

        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<FocusOut>", self._on_focus_out)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)

    # ---------------------------------------------------------- 尺寸

    def _measure(self) -> tuple[int, int]:
        width = MIN_WIDTH
        height = PAD_Y * 2
        for item in self._items:
            if item[0] == "sep":
                height += px(SEPARATOR_HEIGHT)
                continue
            height += px(ITEM_HEIGHT)
            width = max(width, self._font.measure(item[1]) + px(64))
        return width, height

    # ---------------------------------------------------------- 绘制

    def _draw(self) -> None:
        width, height = self._width, self._height
        round_rect(
            self.canvas,
            0,
            0,
            width,
            height,
            px(10),
            fill=COLORS["surface"],
            outline=COLORS["border_strong"],
            width=px(1),
        )
        y = PAD_Y
        for index, item in enumerate(self._items):
            if item[0] == "sep":
                line_y = y + px(SEPARATOR_HEIGHT) // 2
                self.canvas.create_line(
                    px(12), line_y, width - px(12), line_y, fill=COLORS["border"], width=px(1)
                )
                self._rows.append(None)
                y += px(SEPARATOR_HEIGHT)
                continue

            row_top = y
            row_bottom = y + px(ITEM_HEIGHT)
            self._rows.append((row_top, row_bottom, index))
            tag = f"row{index}"
            self._hover_items[index] = round_rect(
                self.canvas,
                px(4),
                row_top + px(2),
                width - px(4),
                row_bottom - px(2),
                px(7),
                fill=COLORS["surface"],
                outline="",
                tags=(tag,),
            )
            if item[0] == "check" and item[2]:
                self.canvas.create_text(
                    px(18),
                    (row_top + row_bottom) // 2,
                    text="✓",
                    anchor="w",
                    font=self._font_bold,
                    fill=COLORS["accent"],
                    tags=(tag,),
                )
            self.canvas.create_text(
                px(34),
                (row_top + row_bottom) // 2,
                text=item[1],
                anchor="w",
                font=self._font,
                fill=COLORS["text"],
                tags=(tag,),
            )
            self.canvas.tag_bind(tag, "<Enter>", lambda _e, i=index: self._set_hover(i))
            self.canvas.tag_bind(tag, "<Leave>", lambda _e: self._set_hover(None))
            y = row_bottom

    def _set_hover(self, index: int | None) -> None:
        if index == self._hover:
            return
        previous = self._hover
        self._hover = index
        if previous is not None and previous in self._hover_items:
            self.canvas.itemconfigure(self._hover_items[previous], fill=COLORS["surface"])
        if index is not None and index in self._hover_items:
            self.canvas.itemconfigure(self._hover_items[index], fill=COLORS["accent_soft"])

    # ---------------------------------------------------------- 交互

    def _on_motion(self, event) -> None:  # noqa: ANN001
        self._set_hover(self._hit(event.y))

    def _hit(self, y: int) -> int | None:
        for entry in self._rows:
            if entry is None:
                continue
            top, bottom, index = entry
            if top <= y < bottom:
                return index
        return None

    def _on_click(self, event) -> None:  # noqa: ANN001
        inside = 0 <= event.x <= self._width and 0 <= event.y <= self._height
        index = self._hit(event.y) if inside else None
        if index is None:
            self.close()
            return
        item = self._items[index]
        if item[0] == "sep":
            self.close()
            return
        callback = item[2] if item[0] == "command" else item[3]
        self.close()
        if callback is not None:
            callback()

    def _on_focus_out(self, _event=None) -> None:  # noqa: ANN001
        if self._armed:
            self.close()

    # ---------------------------------------------------------- 显示

    def post(self, x: int, y: int, bounds: tuple[int, int, int, int] | None = None) -> None:
        """bounds: (left, top, right, bottom)，多显示器时用来贴边。"""
        if bounds:
            left, top, right, bottom = bounds
        else:
            left, top = 0, 0
            right, bottom = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(left + 4, min(int(x), right - self._width - 4))
        y = max(top + 4, min(int(y), bottom - self._height - 4))
        self.geometry(f"{self._width}x{self._height}+{x}+{y}")
        self.deiconify()
        self.lift()
        # 主窗口是隐藏的，进程本来没有前台权；这里趁刚刚点过小窗，把前台要过来，
        # 这样点到别处时 <FocusOut> 才会真的触发，菜单能自己收起。
        try:
            user32.SetForegroundWindow(int(self.winfo_id()))
        except Exception:  # noqa: BLE001
            pass
        try:
            self.focus_force()
        except tk.TclError:
            pass
        self._focus_job = self.after(140, self._arm)
        self._watch_job = self.after(WATCH_MS, self._watch)

    def _arm(self) -> None:
        self._armed = True

    # ---------------------------------------------------------- 点外面收起

    def _watch(self) -> None:
        """主窗口隐藏时进程不一定拿得到前台，FocusOut 可能不触发。

        这里每 70ms 看一眼左键：只要按下时鼠标不在菜单上，就收起。
        """
        if self._closing or not self.winfo_exists():
            return
        pressed = self._left_button_down()
        if pressed and not self._pressed and not self._cursor_inside():
            self.close()
            return
        self._pressed = pressed
        self._watch_job = self.after(WATCH_MS, self._watch)

    def _left_button_down(self) -> bool:
        return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

    def _cursor_inside(self) -> bool:
        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return True
        x, y = point.x, point.y
        left, top = self.winfo_rootx(), self.winfo_rooty()
        return left <= x < left + self._width and top <= y < top + self._height

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        for job in (self._focus_job, self._watch_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._focus_job = None
        self._watch_job = None
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self._on_close is not None:
            self._on_close()
