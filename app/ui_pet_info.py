"""鼠标停在鲸鱼娘身上时浮出的信息卡：现在做什么、接下来做什么。

和旧版左下角小卡片的内容一致，只是改成悬停才出现：逐像素透明的圆角卡片，
不抢焦点、不挡鼠标。
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from tkinter import font as tkfont

from .theme import COLORS, FAMILY, px, round_rect

TRANSPARENT_KEY = "#FF00FE"
WIDTH = 280          # 96dpi 下的卡片宽度
PAD = 14

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

user32 = ctypes.WinDLL("user32", use_last_error=True)
_get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_get_long.argtypes = [wintypes.HWND, ctypes.c_int]
_get_long.restype = ctypes.c_ssize_t
_set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_set_long.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]


class PetInfoPanel(tk.Toplevel):
    """悬停信息卡：prepare() 排版，show_at() 显示，hide() 收起。"""

    def __init__(self, root: tk.Misc) -> None:
        super().__init__(root)
        self.withdraw()
        self.overrideredirect(True)
        self.title("时间表 · 现在做什么")
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.configure(bg=TRANSPARENT_KEY)

        self._title_font = tkfont.Font(family=FAMILY, size=11, weight="bold")
        self._text_font = tkfont.Font(family=FAMILY, size=9)
        self._small_font = tkfont.Font(family=FAMILY, size=8)

        self._canvas = tk.Canvas(
            self,
            width=px(WIDTH),
            height=px(120),
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack()
        self._width = px(WIDTH)
        self._height = px(120)
        self._visible = False
        self._styled = False
        # 先套上「不激活」样式，第一次 deiconify 就不会抢焦点
        self._make_passive()

    # ---------------------------------------------------------- 尺寸与排版

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def size(self) -> tuple[int, int]:
        return self._width, self._height

    def _status_color(self, key: str) -> str:
        return COLORS.get(key, COLORS["text_2"])

    def prepare(self, data: dict) -> tuple[int, int]:
        width = px(WIDTH)
        pad = px(PAD)
        header_h = px(17)
        gap = px(8)
        current_h = px(23)
        status_h = px(18) if data.get("current_status") else 0
        bar_h = px(13) if data.get("progress") is not None else 0
        sep_h = px(15)
        next_lines = self._wrap(
            data.get("next_text") or "接下来无事项",
            self._text_font,
            width - pad * 2 - px(50),
            max_lines=2,
        )
        next_h = px(19) * len(next_lines)
        height = pad + header_h + gap + current_h + status_h + bar_h + sep_h + next_h + pad

        self._width, self._height = width, height
        self._canvas.configure(width=width, height=height)
        self._draw(data, width, height, pad, header_h, gap, current_h, status_h, bar_h, sep_h, next_lines)
        return width, height

    def _wrap(self, text: str, font: tkfont.Font, max_width: int, max_lines: int = 2) -> list[str]:
        lines: list[str] = []
        rest = text
        while rest and len(lines) < max_lines:
            if font.measure(rest) <= max_width:
                lines.append(rest)
                rest = ""
                break
            cut = len(rest)
            while cut > 1 and font.measure(rest[:cut] + "…") > max_width:
                cut -= 1
            if len(lines) == max_lines - 1:
                lines.append(rest[:cut] + "…")
                rest = ""
            else:
                lines.append(rest[:cut])
                rest = rest[cut:]
        return lines or [""]

    def _fit(self, text: str, font: tkfont.Font, max_width: int) -> str:
        if font.measure(text) <= max_width:
            return text
        while text and font.measure(text + "…") > max_width:
            text = text[:-1]
        return text + "…"

    def _draw(
        self,
        data: dict,
        width: int,
        height: int,
        pad: int,
        header_h: int,
        gap: int,
        current_h: int,
        status_h: int,
        bar_h: int,
        sep_h: int,
        next_lines: list[str],
    ) -> None:
        canvas = self._canvas
        canvas.delete("all")
        round_rect(
            canvas,
            0,
            0,
            width,
            height,
            px(12),
            fill=COLORS["surface"],
            outline=COLORS["border_strong"],
            width=px(1),
        )

        y = pad
        head = f"{data.get('clock', '')}  {data.get('date', '')}"
        if data.get("paused"):
            head += " · 已暂停"
        canvas.create_text(
            pad,
            y,
            text=head,
            anchor="nw",
            font=self._small_font,
            fill=COLORS["amber"] if data.get("paused") else COLORS["text_3"],
        )
        y += header_h + gap

        canvas.create_text(
            pad,
            y + px(4),
            text="现在",
            anchor="nw",
            font=self._small_font,
            fill=COLORS["text_3"],
        )
        title = data.get("current_title") or "当前无事项"
        canvas.create_text(
            pad + px(38),
            y,
            text=self._fit(title, self._title_font, width - pad * 2 - px(38)),
            anchor="nw",
            font=self._title_font,
            fill=COLORS["text"] if data.get("current_status") else COLORS["text_3"],
        )

        status = data.get("current_status") or ""
        if status:
            canvas.create_text(
                pad + px(38),
                y + px(24),
                text=status,
                anchor="nw",
                font=self._text_font,
                fill=self._status_color(data.get("status_color", "text_2")),
            )
        y += current_h + status_h

        progress = data.get("progress")
        if progress is not None:
            track_w = width - pad * 2
            top = y + px(3)
            round_rect(
                canvas,
                pad,
                top,
                pad + track_w,
                top + px(4),
                px(2),
                fill=COLORS["bg_alt"],
                outline="",
            )
            filled = max(px(3), int(track_w * max(0.0, min(1.0, float(progress)))))
            round_rect(
                canvas,
                pad,
                top,
                pad + filled,
                top + px(4),
                px(2),
                fill=self._status_color(data.get("status_color", "green")),
                outline="",
            )
        y += bar_h

        canvas.create_line(
            pad, y + px(4), width - pad, y + px(4), fill=COLORS["border"], width=px(1)
        )
        y += sep_h

        canvas.create_text(
            pad,
            y + px(2),
            text="接下来",
            anchor="nw",
            font=self._small_font,
            fill=COLORS["text_3"],
        )
        for index, line in enumerate(next_lines):
            canvas.create_text(
                pad + px(50),
                y + index * px(19),
                text=line,
                anchor="nw",
                font=self._text_font,
                fill=COLORS["text_2"] if data.get("next_text") else COLORS["text_3"],
            )

    # ---------------------------------------------------------- 显示

    def show_at(self, x: int, y: int) -> None:
        self.geometry(f"{self._width}x{self._height}+{int(x)}+{int(y)}")
        if not self._visible:
            self.deiconify()
            self._visible = True
            self._make_passive()

    def hide(self) -> None:
        if not self._visible:
            return
        self._visible = False
        try:
            self.withdraw()
        except tk.TclError:
            pass

    def _make_passive(self) -> None:
        """不抢焦点、不在 Alt+Tab / 任务栏里出现。"""
        if self._styled:
            return
        self._styled = True
        try:
            self.update_idletasks()
            frame = self.wm_frame()
            hwnd = int(frame, 16) if isinstance(frame, str) else int(frame)
            style = _get_long(wintypes.HWND(hwnd), GWL_EXSTYLE)
            _set_long(
                wintypes.HWND(hwnd),
                GWL_EXSTYLE,
                style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            )
            user32.SetWindowPos(
                wintypes.HWND(hwnd),
                None,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        except Exception:  # noqa: BLE001 - 拿不到句柄也不影响显示
            pass
