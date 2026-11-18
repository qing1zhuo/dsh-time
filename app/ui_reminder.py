"""右下角提醒卡片：同一时段的多项事宜合并成一张卡片。"""

from __future__ import annotations

import tkinter as tk

from .scheduler import DueReminder
from .theme import COLORS, font, px, round_rect
from .widgets import RoundButton

TRANSPARENT_KEY = "#FF00FE"


class ReminderPopup(tk.Toplevel):
    WIDTH = 384
    MAX_ROWS = 4

    def __init__(
        self,
        app,  # noqa: ANN001
        dues: list[DueReminder],
        index: int = 0,
        heading: str | None = None,
    ) -> None:
        super().__init__(app.root)
        self.app = app
        self.dues = list(dues)
        if not self.dues:
            raise ValueError("提醒至少要有一条日程")
        self.reminder = self.dues[0]
        self.index = index
        self.withdraw()
        self.overrideredirect(True)
        self.title("时间表提醒")
        self.attributes("-topmost", True)
        try:
            self.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.configure(bg=TRANSPARENT_KEY)

        self._card_w = px(self.WIDTH)
        self._canvas = tk.Canvas(
            self,
            width=self._card_w,
            height=px(160),
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(fill="both", expand=True)

        self._content = tk.Frame(self, bg=COLORS["surface"])
        if len(self.dues) == 1:
            self._build_single(heading)
        else:
            self._build_group(heading)

        self._content.update_idletasks()
        content_height = self._content.winfo_reqheight()
        self._card_h = max(px(150), content_height + px(74))

        self._canvas.configure(width=self._card_w, height=self._card_h)
        round_rect(
            self._canvas,
            1,
            1,
            self._card_w - 1,
            self._card_h - 1,
            px(16),
            fill=COLORS["surface"],
            outline=COLORS["border_strong"],
            width=px(1),
        )
        self._content.place(x=px(20), y=px(16), width=self._card_w - px(44))
        self._build_buttons()
        self._show_animated()

    # ---------------------------------------------------------- 内容

    def _build_single(self, heading: str | None) -> None:
        content = self._content
        surface = COLORS["surface"]
        due = self.dues[0]
        entry = due.entry
        accent, heading_text = self._heading_style(heading)

        self._heading_row(content, accent, heading_text)

        title = tk.Label(
            content,
            text=entry.title or "（未命名）",
            font=font(12, "bold"),
            fg=COLORS["text"],
            bg=surface,
            anchor="w",
            justify="left",
            wraplength=self._card_w - px(58),
        )
        title.pack(fill="x", pady=(px(6), 0))

        meta_text = entry.time_label()
        if entry.kind == "weekly":
            meta_text += f" · {entry.weekday_label()}"
        else:
            meta_text += f" · {entry.date_label()}"
        meta = tk.Label(
            content,
            text=meta_text,
            font=font(9),
            fg=COLORS["text_2"],
            bg=surface,
            anchor="w",
        )
        meta.pack(fill="x", pady=(px(3), 0))

        detail = self._course_detail(entry)
        if detail:
            tk.Label(
                content,
                text=detail,
                font=font(9),
                fg=COLORS["text_2"],
                bg=surface,
                anchor="w",
                justify="left",
                wraplength=self._card_w - px(58),
            ).pack(fill="x", pady=(px(3), 0))

        if entry.note:
            note = entry.note.replace("\n", " ").strip()
            if len(note) > 90:
                note = note[:90] + "…"
            tk.Label(
                content,
                text=note,
                font=font(9),
                fg=COLORS["text_3"],
                bg=surface,
                anchor="w",
                justify="left",
                wraplength=self._card_w - px(58),
            ).pack(fill="x", pady=(px(4), 0))

        for widget in (title, meta):
            widget.bind("<Button-1>", lambda _e: self._open_main())
            widget.configure(cursor="hand2")

    def _build_group(self, heading: str | None) -> None:
        content = self._content
        surface = COLORS["surface"]
        accent, heading_text = self._heading_style(heading)
        self._heading_row(content, accent, heading_text)

        first = self.dues[0]
        same_slot = all(due.start == first.start and due.end == first.end for due in self.dues)
        meta_text = (
            f"{first.start:%H:%M} – {first.end:%H:%M}"
            if same_slot
            else f"{first.start:%H:%M} 起 · 同一时段"
        )
        tk.Label(
            content,
            text=meta_text,
            font=font(9),
            fg=COLORS["text_2"],
            bg=surface,
            anchor="w",
        ).pack(fill="x", pady=(px(3), 0))

        tk.Frame(content, bg=COLORS["border"], height=1).pack(fill="x", pady=(px(8), 0))

        for due in self.dues[: self.MAX_ROWS]:
            self._group_row(content, due, show_time=not same_slot)

        remaining = len(self.dues) - self.MAX_ROWS
        if remaining > 0:
            tk.Label(
                content,
                text=f"还有 {remaining} 项，打开主窗口查看",
                font=font(8),
                fg=COLORS["text_3"],
                bg=surface,
                anchor="w",
            ).pack(fill="x", pady=(px(6), 0))

    def _group_row(self, parent: tk.Misc, due: DueReminder, show_time: bool) -> None:
        surface = COLORS["surface"]
        entry = due.entry
        row = tk.Frame(parent, bg=surface)
        row.pack(fill="x", pady=(px(7), 0))
        tk.Label(
            row,
            text="•",
            font=font(9, "bold"),
            fg=COLORS["accent"],
            bg=surface,
            anchor="n",
        ).pack(side="left", anchor="n")
        box = tk.Frame(row, bg=surface)
        box.pack(side="left", fill="x", expand=True, padx=(px(6), 0))

        head = tk.Frame(box, bg=surface)
        head.pack(fill="x")
        title_text = entry.title or "（未命名）"
        if len(title_text) > 18:
            title_text = title_text[:18] + "…"
        tk.Label(
            head,
            text=title_text,
            font=font(10, "bold"),
            fg=COLORS["text"],
            bg=surface,
            anchor="w",
        ).pack(side="left")
        if show_time:
            tk.Label(
                head,
                text=f"{due.start:%H:%M}",
                font=font(8),
                fg=COLORS["text_3"],
                bg=surface,
            ).pack(side="right")

        secondary = self._course_detail(entry)
        if entry.note:
            note = entry.note.replace("\n", " ").strip()
            secondary = " · ".join(part for part in (secondary, note) if part)
        if secondary:
            if len(secondary) > 30:
                secondary = secondary[:30] + "…"
            tk.Label(
                box,
                text=secondary,
                font=font(8),
                fg=COLORS["text_3"],
                bg=surface,
                anchor="w",
            ).pack(fill="x")

    def _heading_row(self, parent: tk.Misc, accent: str, text: str) -> None:
        surface = COLORS["surface"]
        head = tk.Frame(parent, bg=surface)
        head.pack(fill="x")
        dot = tk.Canvas(head, width=px(8), height=px(8), bg=surface, highlightthickness=0, bd=0)
        dot.create_oval(0, 0, px(8), px(8), fill=accent, outline="")
        dot.pack(side="left", pady=(px(5), 0))
        tk.Label(
            head,
            text=text,
            font=font(9, "bold"),
            fg=accent,
            bg=surface,
            anchor="w",
        ).pack(side="left", padx=(px(6), 0))

    def _build_buttons(self) -> None:
        surface = COLORS["surface"]
        all_point = all(due.entry.point for due in self.dues)
        close = RoundButton(
            self,
            "×",
            self._dismiss,
            kind="ghost",
            height=26,
            pad_x=8,
            font_size=11,
            weight="normal",
            parent_bg=surface,
        )
        close.place(relx=1.0, x=-px(10), y=px(8), anchor="ne")

        buttons = tk.Frame(self, bg=surface)
        buttons.place(relx=1.0, rely=1.0, x=-px(18), y=-px(14), anchor="se")
        RoundButton(
            buttons,
            "已完成" if all_point else "知道了",
            self._complete if all_point else self._dismiss,
            kind="primary",
            height=32,
            pad_x=16,
            font_size=9,
            parent_bg=surface,
        ).pack(side="right")
        RoundButton(
            buttons,
            "稍后 15 分钟",
            lambda: self._snooze(15),
            kind="ghost",
            height=32,
            pad_x=10,
            font_size=9,
            weight="normal",
            parent_bg=surface,
        ).pack(side="right", padx=(0, px(6)))
        RoundButton(
            buttons,
            "稍后 5 分钟",
            lambda: self._snooze(5),
            kind="ghost",
            height=32,
            pad_x=10,
            font_size=9,
            weight="normal",
            parent_bg=surface,
        ).pack(side="right", padx=(0, px(6)))

    # ---------------------------------------------------------- 文案

    @staticmethod
    def _course_detail(entry) -> str:  # noqa: ANN001
        parts = [entry.room.strip(), entry.teacher.strip(), entry.period.strip()]
        return " · ".join(part for part in parts if part)

    def _heading_style(self, heading: str | None) -> tuple[str, str]:
        count = len(self.dues)
        suffix = f" · {count} 项" if count > 1 else ""
        all_point = all(due.entry.point for due in self.dues)
        if heading:
            return COLORS["accent"], heading + suffix
        if any(due.snoozed for due in self.dues):
            return COLORS["purple"], "稍后提醒" + suffix
        late = max((due.late_minutes for due in self.dues), default=0)
        if late >= 1:
            text = f"已经过了 {late} 分钟" if all_point else f"已开始 {late} 分钟"
            return COLORS["amber"], text + suffix
        if any(due.advanced for due in self.dues):
            return COLORS["accent"], "马上开始" + suffix
        return COLORS["green"], ("到点了" if all_point else "现在开始") + suffix

    # ---------------------------------------------------------- 行为

    def _dismiss(self) -> None:
        self.app.dismiss_reminder(self)

    def _complete(self) -> None:
        self.app.complete_reminder(self)

    def _snooze(self, minutes: int) -> None:
        self.app.snooze_reminder(self, minutes)

    def _open_main(self) -> None:
        self.app.show_main()

    def reposition(self, index: int) -> None:
        self.index = index
        x, y = self.app.reminder_position(index, self._card_h)
        self.geometry(f"+{x}+{y}")

    # ---------------------------------------------------------- 动画

    def _show_animated(self) -> None:
        self.update_idletasks()
        x, target_y = self.app.reminder_position(self.index, self._card_h)
        self._x, self._target_y = x, target_y
        self.geometry(f"{self._card_w}x{self._card_h}+{x}+{target_y + px(14)}")
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.deiconify()
        self.lift()
        self._animate(0, x)

    def _animate(self, step: int, x: int) -> None:
        if not self.winfo_exists():
            return
        steps = 9
        progress = min(1.0, (step + 1) / steps)
        eased = 1 - (1 - progress) ** 3
        try:
            self.attributes("-alpha", max(0.05, eased))
        except tk.TclError:
            pass
        y = self._target_y + int(px(14) * (1 - eased))
        self.geometry(f"{self._card_w}x{self._card_h}+{x}+{y}")
        if step + 1 < steps:
            self.after(14, lambda: self._animate(step + 1, x))
        else:
            self.geometry(f"{self._card_w}x{self._card_h}+{x}+{self._target_y}")
            try:
                self.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
