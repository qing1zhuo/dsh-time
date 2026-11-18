"""左下角常驻小窗：像桌宠一样一直待着。

分两块显示：
- 当前要做的事（没有就明确写「当前无事项」）
- 接下来要做的事
"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import font as tkfont

from .model import WEEKDAY_CN, humanize_delta, next_upcoming, occurrences_on_day
from .theme import COLORS, FAMILY, px, round_rect

TRANSPARENT_KEY = "#FF00FE"


class DesktopPet(tk.Toplevel):
    WIDTH = 276
    HEIGHT = 172
    MARGIN = 18

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.overrideredirect(True)
        self.title("时间表小窗")
        try:
            self.attributes("-topmost", bool(app.settings.pet_topmost))
        except tk.TclError:
            pass
        try:
            self.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.configure(bg=TRANSPARENT_KEY)

        self._pw, self._ph = px(self.WIDTH), px(self.HEIGHT)
        self.canvas = tk.Canvas(
            self,
            width=self._pw,
            height=self._ph,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        self._time_font = tkfont.Font(family=FAMILY, size=17, weight="bold")
        self._current_font = tkfont.Font(family=FAMILY, size=10, weight="bold")
        self._next_font = tkfont.Font(family=FAMILY, size=9)
        self._small_font = tkfont.Font(family=FAMILY, size=8)
        self._icon = self._load_icon()

        self._job: str | None = None
        self._pressed = (0, 0)
        self._start_pos = (0, 0)
        self._dragging = False

        self._draw_static()
        self._bind_events()
        self._restore_position()
        self._update()
        self.deiconify()
        self._schedule()

    # ---------------------------------------------------------- 外观

    def _load_icon(self):
        from . import paths

        try:
            image = tk.PhotoImage(file=str(paths.ASSETS_DIR / "app-256.png"))
            return image.subsample(6)
        except (tk.TclError, OSError):
            return None

    def _draw_static(self) -> None:
        w, h = self._pw, self._ph
        self._card = round_rect(
            self.canvas,
            1,
            1,
            w - 1,
            h - 1,
            px(16),
            fill=COLORS["surface"],
            outline=COLORS["border_strong"],
            width=px(1),
        )
        if self._icon is not None:
            self.canvas.create_image(px(16), px(14), image=self._icon, anchor="nw")
        else:
            round_rect(self.canvas, px(16), px(14), px(56), px(54), px(12), fill=COLORS["accent"])

        self._time_item = self.canvas.create_text(
            px(66), px(8), text="", anchor="nw", font=self._time_font, fill=COLORS["text"]
        )
        self._date_item = self.canvas.create_text(
            px(67), px(40), text="", anchor="nw", font=self._small_font, fill=COLORS["text_3"]
        )
        self.canvas.create_line(
            px(16), px(64), w - px(16), px(64), fill=COLORS["border"], width=px(1)
        )

        self.canvas.create_text(
            px(16),
            px(72),
            text="当前要做的事",
            anchor="nw",
            font=self._small_font,
            fill=COLORS["text_3"],
        )
        self._current_item = self.canvas.create_text(
            px(16), px(90), text="", anchor="nw", font=self._current_font, fill=COLORS["text"]
        )
        self._current_extra = self.canvas.create_text(
            w - px(16), px(92), text="", anchor="ne", font=self._small_font, fill=COLORS["text_3"]
        )

        self.canvas.create_text(
            px(16),
            px(128),
            text="接下来要做的事",
            anchor="nw",
            font=self._small_font,
            fill=COLORS["text_3"],
        )
        self._next_item = self.canvas.create_text(
            px(16), px(146), text="", anchor="nw", font=self._next_font, fill=COLORS["text_2"]
        )

    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_menu)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.itemconfigure(self._card, outline=COLORS["accent"]))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.itemconfigure(self._card, outline=COLORS["border_strong"]))
        self.canvas.bind("<Shift-Button-3>", self._on_menu)

    # ---------------------------------------------------------- 位置

    def _restore_position(self) -> None:
        x, y = self.app.settings.pet_x, self.app.settings.pet_y
        if x is None or y is None:
            left, _top, _right, bottom = self.app.work_area()
            x = left + px(self.MARGIN)
            y = bottom - px(self.MARGIN) - self._ph
        x, y = self._clamp(int(x), int(y))
        self.geometry(f"{self._pw}x{self._ph}+{x}+{y}")

    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = self.app.virtual_screen()
        work_left, _work_top, work_right, work_bottom = self.app.work_area()
        x = max(left, min(x, right - self._pw))
        lower = bottom
        # 落在主屏范围里时，别让小窗压住任务栏
        if x + self._pw > work_left and x < work_right:
            lower = min(lower, work_bottom)
        return x, max(top, min(y, lower - self._ph))

    def _save_position(self) -> None:
        self.app.settings.pet_x = self.winfo_x()
        self.app.settings.pet_y = self.winfo_y()
        self.app.store.save()

    # ---------------------------------------------------------- 交互

    def _on_press(self, event) -> None:  # noqa: ANN001
        self._pressed = (event.x_root, event.y_root)
        self._start_pos = (self.winfo_x(), self.winfo_y())
        self._dragging = False

    def _on_drag(self, event) -> None:  # noqa: ANN001
        dx = event.x_root - self._pressed[0]
        dy = event.y_root - self._pressed[1]
        if not self._dragging and abs(dx) + abs(dy) > 5:
            self._dragging = True
        if self._dragging:
            x, y = self._clamp(self._start_pos[0] + dx, self._start_pos[1] + dy)
            self.geometry(f"+{x}+{y}")

    def _on_release(self, event) -> None:  # noqa: ANN001
        if self._dragging:
            self._save_position()
            self._dragging = False
        else:
            self.app.show_main()

    def _on_menu(self, event) -> None:  # noqa: ANN001
        menu = tk.Menu(self, tearoff=0, font=(FAMILY, 9))
        menu.add_command(label="打开时间表", command=self.app.show_main)
        menu.add_command(
            label="新建日程",
            command=lambda: (self.app.show_main(), self.app.new_entry()),
        )
        menu.add_separator()
        menu.add_checkbutton(
            label="暂停提醒",
            onvalue=True,
            offvalue=False,
            variable=tk.BooleanVar(value=self.app.paused),
            command=self.app.toggle_pause,
        )
        menu.add_checkbutton(
            label="总在最前",
            onvalue=True,
            offvalue=False,
            variable=tk.BooleanVar(value=bool(self.app.settings.pet_topmost)),
            command=self._toggle_topmost,
        )
        menu.add_separator()
        menu.add_command(label="隐藏小窗", command=lambda: self.app.set_pet_enabled(False))
        menu.add_command(label="退出时间表", command=self.app.quit_app)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _toggle_topmost(self) -> None:
        value = not bool(self.app.settings.pet_topmost)
        self.app.settings.pet_topmost = value
        self.app.store.save()
        try:
            self.attributes("-topmost", value)
        except tk.TclError:
            pass

    # ---------------------------------------------------------- 内容

    def _schedule(self) -> None:
        self._job = self.after(1000, self._loop)

    def _loop(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self._update()
        finally:
            self._schedule()

    def _fit(self, text: str, font_obj: tkfont.Font, max_width: int) -> str:
        if font_obj.measure(text) <= max_width:
            return text
        while text and font_obj.measure(text + "…") > max_width:
            text = text[:-1]
        return text + "…"

    def _update(self) -> None:
        now = datetime.now()
        self.canvas.itemconfigure(self._time_item, text=now.strftime("%H:%M"))

        date_text = f"{now.month} 月 {now.day} 日 {WEEKDAY_CN[now.isoweekday()]}"
        if self.app.paused:
            date_text += " · 已暂停"
        self.canvas.itemconfigure(
            self._date_item,
            text=date_text,
            fill=COLORS["amber"] if self.app.paused else COLORS["text_3"],
        )

        entries = self.app.store.enabled_entries()
        rows = occurrences_on_day(entries, now.date())

        current_rows: list[tuple[object, datetime, datetime]] = []
        for entry, start_dt, end_dt in rows:
            if entry.point:
                key = entry.fire_key(start_dt.date(), entry.start_time)
                if start_dt <= now and not entry.has_done(key):
                    current_rows.append((entry, start_dt, end_dt))
            elif start_dt <= now <= end_dt:
                current_rows.append((entry, start_dt, end_dt))
        current_rows.sort(key=lambda row: row[1])

        if current_rows:
            entry, start_dt, end_dt = current_rows[0]
            extra = f" 等 {len(current_rows)} 项" if len(current_rows) > 1 else ""
            title = (entry.title or "未命名") + extra
            self.canvas.itemconfigure(
                self._current_item,
                text=self._fit(title, self._current_font, self._pw - px(32) - px(100)),
                fill=COLORS["text"],
            )
            if entry.point:
                overdue = max(0, int((now - start_dt).total_seconds() // 60))
                self.canvas.itemconfigure(
                    self._current_extra,
                    text="到点了" if overdue < 1 else f"已过 {overdue} 分钟",
                    fill=COLORS["amber"],
                )
                self._set_progress(None)
            else:
                remaining = max(0, int((end_dt - now).total_seconds() // 60))
                self.canvas.itemconfigure(
                    self._current_extra,
                    text=f"还剩 {remaining} 分钟",
                    fill=COLORS["green"],
                )
                total = max(1.0, (end_dt - start_dt).total_seconds())
                ratio = min(1.0, max(0.0, 1 - (end_dt - now).total_seconds() / total))
                self._set_progress(ratio, COLORS["green"])
        else:
            self.canvas.itemconfigure(
                self._current_item, text="当前无事项", fill=COLORS["text_3"]
            )
            self.canvas.itemconfigure(self._current_extra, text="")
            self._set_progress(None)

        upcoming = next_upcoming(entries, now)
        future = [row for row in upcoming if row[2] > now]
        if future:
            entry, _fire_at, start_dt, _end_dt = min(future, key=lambda row: row[2])
            if start_dt.date() == now.date():
                when = f"{start_dt:%H:%M}"
            elif start_dt.date() == now.date() + timedelta(days=1):
                when = f"明天 {start_dt:%H:%M}"
            else:
                when = f"{start_dt.month} 月 {start_dt.day} 日 {start_dt:%H:%M}"
            text = f"{when}  {entry.title or '未命名'} · {humanize_delta((start_dt - now).total_seconds())}"
            self.canvas.itemconfigure(
                self._next_item,
                text=self._fit(text, self._next_font, self._pw - px(32)),
                fill=COLORS["text_2"],
            )
        else:
            self.canvas.itemconfigure(self._next_item, text="接下来无事项", fill=COLORS["text_3"])

    def _set_progress(self, ratio: float | None, color: str = COLORS["green"]) -> None:
        self.canvas.delete("progress")
        if ratio is None:
            return
        x0, y0 = px(16), px(114)
        width = self._pw - px(32)
        round_rect(
            self.canvas, x0, y0, x0 + width, y0 + px(4), px(2),
            fill=COLORS["bg_alt"], outline="", tags="progress",
        )
        filled = max(px(3), width * max(0.0, min(1.0, ratio)))
        round_rect(
            self.canvas, x0, y0, x0 + filled, y0 + px(4), px(2),
            fill=color, outline="", tags="progress",
        )

    # ---------------------------------------------------------- 收尾

    def close(self) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self._save_position()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
