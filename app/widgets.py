"""自绘小控件：圆角按钮、胶囊标签、开关、滚动容器、日期选择器。"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, timedelta
from tkinter import font as tkfont
from typing import Callable

from .theme import COLORS, FAMILY, font, px, round_rect


# ------------------------------------------------------------------ 胶囊标签


class Chip(tk.Canvas):
    """圆角胶囊，可选中；用于筛选标签、星期选择、快捷日期。"""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        selected: bool = False,
        height: int = 30,
        pad_x: int = 14,
        font_size: int = 10,
        weight: str = "normal",
        parent_bg: str | None = None,
        radius: int | None = None,
        min_width: int = 0,
        fill: str = COLORS["surface"],
        hover_fill: str = COLORS["surface_2"],
        outline: str = COLORS["border_strong"],
        selected_fill: str = COLORS["accent_soft"],
        selected_outline: str = COLORS["accent"],
        selected_fg: str = COLORS["accent_ink"],
        fg: str = COLORS["text_2"],
        interactive: bool = True,
    ) -> None:
        self._parent_bg = parent_bg or COLORS["bg"]
        self._font = tkfont.Font(family=FAMILY, size=font_size, weight=weight)
        self._pad_x = px(pad_x)
        width = self._font.measure(text) + self._pad_x * 2
        if min_width:
            width = max(width, px(min_width))
        height_px = px(height)
        super().__init__(
            master,
            width=width,
            height=height_px,
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2" if interactive else "arrow",
        )
        self._text = text
        self._command = command
        self._selected = selected
        self._interactive = interactive
        self._hover = False
        self._radius = px(radius) if radius else height_px / 2
        self._width = width
        self._height = height_px
        self._style = {
            "fill": fill,
            "hover_fill": hover_fill,
            "outline": outline,
            "selected_fill": selected_fill,
            "selected_outline": selected_outline,
            "selected_fg": selected_fg,
            "fg": fg,
        }
        self._draw()
        if interactive:
            self.bind("<Button-1>", self._on_click)
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)

    # -- 绘制 ---------------------------------------------------------

    def _draw(self) -> None:
        self.delete("all")
        style = self._style
        if self._selected:
            fill, outline, fg = style["selected_fill"], style["selected_outline"], style["selected_fg"]
        elif self._hover and self._interactive:
            fill, outline, fg = style["hover_fill"], style["outline"], COLORS["text"]
        else:
            fill, outline, fg = style["fill"], style["outline"], style["fg"]
        w, h = self._width, self._height
        outline_width = px(1.4) if self._selected else px(1)
        round_rect(
            self,
            0.7,
            0.7,
            w - 0.7,
            h - 0.7,
            self._radius,
            fill=fill,
            outline=outline,
            width=outline_width,
        )
        self.create_text(
            w / 2,
            h / 2,
            text=self._text,
            fill=fg,
            font=self._font,
            anchor="center",
        )

    # -- 状态 ---------------------------------------------------------

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._draw()

    @property
    def selected(self) -> bool:
        return self._selected

    def set_text(self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        width = self._font.measure(text) + self._pad_x * 2
        self.configure(width=width)
        self._width = width
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._interactive = enabled
        self.configure(cursor="hand2" if enabled else "arrow")

    # -- 事件 ---------------------------------------------------------

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, _event=None) -> None:
        if not self._interactive:
            return
        if self._command:
            self._command()


# ------------------------------------------------------------------ 按钮


BUTTON_STYLES = {
    "primary": {
        "fill": COLORS["accent"],
        "hover": COLORS["accent_hover"],
        "press": COLORS["accent_press"],
        "fg": COLORS["white"],
        "outline": "",
    },
    "secondary": {
        "fill": COLORS["surface"],
        "hover": COLORS["surface_2"],
        "press": COLORS["bg_alt"],
        "fg": COLORS["text"],
        "outline": COLORS["border_strong"],
    },
    "soft": {
        "fill": COLORS["accent_soft"],
        "hover": "#DFE9FF",
        "press": "#D3E0FF",
        "fg": COLORS["accent_ink"],
        "outline": "",
    },
    "ghost": {
        "fill": "parent",
        "hover": COLORS["bg_alt"],
        "press": COLORS["border"],
        "fg": COLORS["text_2"],
        "outline": "",
    },
    "danger": {
        "fill": COLORS["red_soft"],
        "hover": "#FBDCDC",
        "press": "#F8CECE",
        "fg": COLORS["red"],
        "outline": "",
    },
}


class RoundButton(tk.Canvas):
    """圆角按钮，支持 primary / secondary / soft / ghost / danger。"""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        kind: str = "primary",
        height: int = 36,
        pad_x: int = 18,
        font_size: int = 10,
        weight: str = "bold",
        parent_bg: str | None = None,
        min_width: int | None = None,
        radius: int | None = None,
        tooltip: str = "",
    ) -> None:
        self._parent_bg = parent_bg or COLORS["bg"]
        style = dict(BUTTON_STYLES.get(kind, BUTTON_STYLES["primary"]))
        if style["fill"] == "parent":
            style["fill"] = self._parent_bg
        self._font = tkfont.Font(family=FAMILY, size=font_size, weight=weight)
        width = self._font.measure(text) + px(pad_x) * 2
        if min_width:
            width = max(width, px(min_width))
        height_px = px(height)
        super().__init__(
            master,
            width=width,
            height=height_px,
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._style = style
        self._width = width
        self._height = height_px
        self._radius = px(radius) if radius else px(10)
        self._state = "normal"
        self._enabled = True
        self._tooltip = tooltip
        self._draw()
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self) -> None:
        self.delete("all")
        if not self._enabled:
            fill, fg, outline = COLORS["bg_alt"], COLORS["text_3"], ""
        else:
            fill = self._style["fill"]
            if self._state == "hover":
                fill = self._style["hover"]
            elif self._state == "press":
                fill = self._style["press"]
            fg = self._style["fg"]
            outline = self._style["outline"]
        w, h = self._width, self._height
        round_rect(
            self,
            0.7,
            0.7,
            w - 0.7,
            h - 0.7,
            self._radius,
            fill=fill,
            outline=outline or fill,
            width=px(1),
        )
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    def set_text(self, text: str, *, width: int | None = None) -> None:
        self._text = text
        if width is not None:
            self._width = px(width)
            self.configure(width=self._width)
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _inside(self, event) -> bool:
        return 0 <= event.x <= self._width and 0 <= event.y <= self._height

    def _on_enter(self, _event=None) -> None:
        self._state = "hover"
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._state = "normal"
        self._draw()

    def _on_press(self, event) -> None:
        if not self._enabled:
            return
        self._state = "press"
        self._draw()

    def _on_release(self, event) -> None:
        if not self._enabled:
            return
        self._state = "hover" if self._inside(event) else "normal"
        self._draw()
        if self._inside(event) and self._command:
            self._command()


# ------------------------------------------------------------------ 开关


class Toggle(tk.Canvas):
    """iOS 风格开关。"""

    def __init__(
        self,
        master: tk.Misc,
        value: bool = False,
        command: Callable[[bool], None] | None = None,
        *,
        parent_bg: str | None = None,
        width: int = 46,
        height: int = 26,
    ) -> None:
        self._parent_bg = parent_bg or COLORS["surface"]
        self._track_w = px(width)
        self._track_h = px(height)
        super().__init__(
            master,
            width=self._track_w,
            height=self._track_h,
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._value = bool(value)
        self._command = command
        self._pos = 1.0 if self._value else 0.0
        self._anim_job: str | None = None
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def _draw(self) -> None:
        self.delete("all")
        w, h = self._track_w, self._track_h
        track = COLORS["accent"] if self._value else COLORS["border_strong"]
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h / 2, fill=track, outline=track)
        knob_r = h / 2 - px(3)
        cx = knob_r + px(2.5) + self._pos * (w - 2 * (knob_r + px(2.5)))
        cy = h / 2
        self.create_oval(cx - knob_r, cy - knob_r, cx + knob_r, cy + knob_r, fill=COLORS["white"], outline="")

    def _on_click(self, _event=None) -> None:
        self.set_value(not self._value, animate=True, notify=True)

    def set_value(self, value: bool, *, animate: bool = True, notify: bool = False) -> None:
        value = bool(value)
        if value == self._value and self._pos in (0.0, 1.0):
            if notify and self._command:
                self._command(self._value)
            return
        self._value = value
        target = 1.0 if value else 0.0
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None
        if animate:
            self._animate_to(target, 0)
        else:
            self._pos = target
            self._draw()
        if notify and self._command:
            self._command(self._value)

    def _animate_to(self, target: float, step: int) -> None:
        steps = 6
        start = self._pos
        self._pos = start + (target - start) * min(1.0, (step + 1) / steps)
        self._draw()
        if step + 1 < steps:
            self._anim_job = self.after(12, lambda: self._animate_to(target, step + 1))
        else:
            self._pos = target
            self._anim_job = None
            self._draw()

    @property
    def value(self) -> bool:
        return self._value


# ------------------------------------------------------------------ 滚动容器


def _install_wheel_binding(widget: tk.Misc) -> None:
    root = widget.winfo_toplevel()
    if getattr(root, "_wheel_bound", False):
        return
    root._wheel_bound = True  # type: ignore[attr-defined]

    def on_wheel(event):
        target = event.widget
        while target is not None:
            if isinstance(target, ScrollFrame):
                target.scroll(event.delta)
                return "break"
            target = getattr(target, "master", None)
        return None

    root.bind_all("<MouseWheel>", on_wheel, add="+")


class ScrollFrame(tk.Frame):
    """垂直滚动区域，滚动条按需显示。"""

    # 一个滚轮格（delta=120）滚动的逻辑像素，约等于 3 行文字
    PIXELS_PER_NOTCH = 60

    def __init__(self, master: tk.Misc, *, bg: str | None = None, pad_right: int = 0) -> None:
        bg = bg or COLORS["bg"]
        super().__init__(master, bg=bg)
        self._bg = bg
        self._pad_right = px(pad_right)
        self._wheel_accum = 0.0
        self._body_height = 0
        self._view_height = 0
        self._bulk = False
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=1)
        self.scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            width=px(9),
            relief="flat",
            bd=0,
            troughcolor=bg,
            activebackground=COLORS["text_3"],
            bg=COLORS["border_strong"],
            highlightthickness=0,
            elementborderwidth=0,
        )
        self.body = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(px(6), 0))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scrollbar.grid_remove()

        self.body.bind("<Configure>", self._sync_region)
        self.canvas.bind("<Configure>", self._sync_width)
        _install_wheel_binding(self)

    def _sync_region(self, event=None) -> None:
        if self._bulk:
            return
        self._apply_region()

    def _apply_region(self) -> None:
        width = max(1, self.canvas.winfo_width())
        self._body_height = self.body.winfo_height()
        self.canvas.configure(scrollregion=(0, 0, width, max(self._body_height, 1)))
        self._update_scrollbar()

    def _sync_width(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._view_height = event.height
        if not self._bulk:
            self._apply_region()

    def begin_bulk(self) -> None:
        """批量插入大量行时先关掉反复重算，插完再统一算一次。"""
        self._bulk = True

    def end_bulk(self) -> None:
        self._bulk = False
        self.body.update_idletasks()
        self._apply_region()

    def refresh_region(self) -> None:
        """分批插入内容时，让滚动条和滚动范围跟上当前高度。"""
        self._apply_region()

    def _on_scroll(self, first: str, last: str) -> None:
        # 滚动过程中只更新滚动条滑块，可见性交给尺寸变化时处理，减少每帧开销
        self.scrollbar.set(first, last)

    def _update_scrollbar(self) -> None:
        needed = self._body_height > self._view_height + 1
        if needed and not self.scrollbar.winfo_ismapped():
            self.scrollbar.grid()
        elif not needed and self.scrollbar.winfo_ismapped():
            self.scrollbar.grid_remove()

    def scroll(self, delta: int) -> None:
        """按像素滚动；支持高分辨率滚轮/触控板的小增量。"""
        if not delta:
            return
        self._wheel_accum += delta
        per_notch = px(self.PIXELS_PER_NOTCH)
        pixels = int(-self._wheel_accum / 120.0 * per_notch)
        if pixels == 0:
            return
        # 扣掉已经消费的滚动量，保留零头，触控板的小步长才不会丢
        self._wheel_accum += pixels * 120.0 / per_notch
        self._wheel_accum = max(-120.0, min(120.0, self._wheel_accum))
        self.canvas.yview_scroll(pixels, "units")

    def to_top(self) -> None:
        self.canvas.yview_moveto(0)

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()


# ------------------------------------------------------------------ 容器与标签


class Card(tk.Frame):
    """白底卡片。"""

    def __init__(self, master: tk.Misc, *, bg: str | None = None, pad: int = 16, border: bool = True) -> None:
        surface = bg or COLORS["surface"]
        super().__init__(
            master,
            bg=surface,
            highlightthickness=1 if border else 0,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
            bd=0,
        )
        self.content = tk.Frame(self, bg=surface)
        self.content.pack(fill="both", expand=True, padx=px(pad), pady=px(pad))


class Badge(tk.Label):
    def __init__(self, master: tk.Misc, text: str, *, fg: str | None = None, bg: str | None = None, font_size: int = 9) -> None:
        super().__init__(
            master,
            text=text,
            bg=bg or COLORS["accent_soft"],
            fg=fg or COLORS["accent_ink"],
            font=font(font_size),
            padx=px(8),
            pady=px(3),
            bd=0,
        )


class Divider(tk.Frame):
    def __init__(self, master: tk.Misc, *, color: str | None = None) -> None:
        super().__init__(master, bg=color or COLORS["border"], height=1)


class MenuRow(tk.Frame):
    """卡片里的一行操作：左边文字，右边箭头，鼠标悬停高亮。"""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        bg: str | None = None,
        fg: str | None = None,
    ) -> None:
        surface = bg or COLORS["surface"]
        super().__init__(master, bg=surface, cursor="hand2")
        self._bg = surface
        self._fg = fg or COLORS["text_2"]
        self._command = command
        inner = tk.Frame(self, bg=surface)
        inner.pack(fill="x", padx=px(2), pady=px(7))
        self._label = tk.Label(
            inner,
            text=text,
            font=font(9),
            fg=self._fg,
            bg=surface,
            anchor="w",
        )
        self._label.pack(side="left", fill="x", expand=True)
        self._arrow = tk.Label(
            inner, text="›", font=font(12), fg=COLORS["text_3"], bg=surface
        )
        self._arrow.pack(side="right")

        for widget in (self, inner, self._label, self._arrow):
            widget.bind("<Button-1>", lambda _e: self._command())
            widget.bind("<Enter>", lambda _e: self._set_hover(True))
            widget.bind("<Leave>", lambda _e: self._set_hover(False))

    def _set_hover(self, hovering: bool) -> None:
        color = COLORS["surface_2"] if hovering else self._bg
        for widget in (self, self._label.master, self._label, self._arrow):
            widget.configure(bg=color)
        self._label.configure(fg=COLORS["text"] if hovering else self._fg)


# ------------------------------------------------------------------ 日期选择器


class CalendarPopup(tk.Toplevel):
    """轻量月历弹窗。"""

    WEEK_HEADERS = ("一", "二", "三", "四", "五", "六", "日")

    def __init__(
        self,
        master: tk.Misc,
        initial: date | None,
        on_pick: Callable[[date], None],
        *,
        anchor: tk.Misc | None = None,
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=COLORS["border_strong"])
        self.attributes("-topmost", True)
        self._on_pick = on_pick
        self._selected = initial or date.today()
        self._today = date.today()
        self._cursor = self._selected.replace(day=1)
        self._cells: list[tk.Label] = []

        outer = tk.Frame(self, bg=COLORS["surface"], padx=px(12), pady=px(10))
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Frame(outer, bg=COLORS["surface"])
        header.pack(fill="x", pady=(0, px(6)))
        self._prev = self._nav_button(header, "‹", lambda: self._shift_month(-1))
        self._prev.pack(side="left")
        self._title = tk.Label(
            header,
            text="",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=font(10, "bold"),
        )
        self._title.pack(side="left", expand=True)
        self._next = self._nav_button(header, "›", lambda: self._shift_month(1))
        self._next.pack(side="right")

        # 表头和日期放在同一个 grid 里，列宽用 uniform 绑定，保证上下严格对齐
        self._grid = tk.Frame(outer, bg=COLORS["surface"])
        self._grid.pack(fill="both", expand=True)
        for index in range(7):
            self._grid.grid_columnconfigure(index, minsize=px(36), weight=1, uniform="calendar")

        self._render()

        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<FocusOut>", lambda _e: self._maybe_close_focus())

        if anchor is not None:
            self.update_idletasks()
            x = anchor.winfo_rootx()
            y = anchor.winfo_rooty() + anchor.winfo_height() + px(6)
            width, height = self.winfo_reqwidth(), self.winfo_reqheight()
            x = min(x, self.winfo_screenwidth() - width - px(8))
            if y + height > self.winfo_screenheight() - px(48):
                y = anchor.winfo_rooty() - height - px(6)
            self.geometry(f"+{max(px(8), x)}+{max(px(8), y)}")
        self.deiconify()
        self.focus_force()

    def _nav_button(self, master: tk.Misc, text: str, command: Callable[[], None]) -> tk.Label:
        label = tk.Label(
            master,
            text=text,
            bg=COLORS["surface"],
            fg=COLORS["text_2"],
            font=font(12, "bold"),
            width=2,
            cursor="hand2",
        )
        label.bind("<Button-1>", lambda _e: command())
        label.bind("<Enter>", lambda _e: label.configure(bg=COLORS["surface_2"]))
        label.bind("<Leave>", lambda _e: label.configure(bg=COLORS["surface"]))
        return label

    def _shift_month(self, delta: int) -> None:
        month = self._cursor.month - 1 + delta
        year = self._cursor.year + month // 12
        month = month % 12 + 1
        self._cursor = date(year, month, 1)
        self._render()

    def _render(self) -> None:
        for child in self._grid.winfo_children():
            child.destroy()
        self._title.configure(text=f"{self._cursor.year} 年 {self._cursor.month} 月")

        for index, label in enumerate(self.WEEK_HEADERS):
            tk.Label(
                self._grid,
                text=label,
                bg=COLORS["surface"],
                fg=COLORS["text_3"],
                font=font(9),
            ).grid(row=0, column=index, sticky="nsew", pady=(0, px(4)))

        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self._cursor.year, self._cursor.month)
        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                label = tk.Label(
                    self._grid,
                    text=str(day.day),
                    bg=COLORS["surface"],
                    fg=COLORS["text"],
                    font=font(9, "bold" if day == self._selected else "normal"),
                    pady=px(5),
                    cursor="hand2",
                )
                if day.month != self._cursor.month:
                    label.configure(fg=COLORS["text_3"])
                if day == self._today:
                    label.configure(fg=COLORS["accent"])
                if day == self._selected:
                    label.configure(bg=COLORS["accent"], fg=COLORS["white"])
                label.grid(row=row, column=col, padx=px(1), pady=px(1), sticky="ew")
                label.bind("<Button-1>", lambda _e, picked=day: self._pick(picked))
                label.bind("<Enter>", lambda _e, widget=label, d=day: self._hover(widget, d, True))
                label.bind("<Leave>", lambda _e, widget=label, d=day: self._hover(widget, d, False))
                self._cells.append(label)

    def _hover(self, widget: tk.Label, day: date, entering: bool) -> None:
        if day == self._selected:
            return
        widget.configure(bg=COLORS["surface_2"] if entering else COLORS["surface"])

    def _pick(self, day: date) -> None:
        self._selected = day
        self.close()
        self._on_pick(day)

    def _maybe_close_focus(self) -> None:
        try:
            focused = self.focus_get()
        except (tk.TclError, KeyError):
            focused = None
        if focused is None or focused.winfo_toplevel() is not self:
            self.after(120, self._close_if_unfocused)

    def _close_if_unfocused(self) -> None:
        if not self.winfo_exists():
            return
        try:
            focused = self.focus_get()
        except (tk.TclError, KeyError):
            focused = None
        if focused is None or focused.winfo_toplevel() is not self:
            self.close()

    def close(self) -> None:
        if not self.winfo_exists():
            return
        self.destroy()
