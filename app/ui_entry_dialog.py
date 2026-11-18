"""新建 / 编辑日程的对话框。"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from .model import (
    KIND_ONCE,
    KIND_WEEKLY,
    WEEKDAY_CN,
    WEEKDAY_ORDER,
    WEEKDAY_SHORT,
    Entry,
    fmt_hhmm,
    parse_hhmm,
)
from .theme import COLORS, font, px
from .widgets import CalendarPopup, Chip, RoundButton

TIME_OPTIONS = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 15, 30, 45)]

ADVANCE_OPTIONS = [
    ("准点提醒", 0),
    ("提前 5 分钟", 5),
    ("提前 10 分钟", 10),
    ("提前 15 分钟", 15),
    ("提前 30 分钟", 30),
    ("提前 1 小时", 60),
    ("提前 2 小时", 120),
]


class EntryDialog(tk.Toplevel):
    def __init__(self, app, entry: Entry | None = None) -> None:  # noqa: ANN001
        self.app = app
        self.original = entry
        super().__init__(app.main_window)
        self.withdraw()
        self.title("编辑日程" if entry else "新建日程")
        self.configure(bg=COLORS["surface"])
        self.resizable(False, False)
        if app.main_window.winfo_viewable():
            # 只有主窗口可见时才建立「附属窗口」关系；否则对话框会被一起隐藏。
            self.transient(app.main_window)

        now = datetime.now()
        default_start, default_date = self._default_slot(now)
        source = entry or Entry(
            kind=KIND_ONCE, date_str=default_date.isoformat(), weekdays=[], start=default_start
        )
        if entry is None:
            source.end = fmt_hhmm(self._plus_minutes(default_start, 60))
            if source.end <= source.start:
                source.start = "09:00"
                source.end = "10:00"
        self._kind = source.kind
        self._date = source.day or default_date
        self._weekdays = set(source.weekdays) or {self._date.isoweekday()}
        self._start_value = fmt_hhmm(source.start_time)
        self._end_value = fmt_hhmm(source.end_time)
        self._advance = int(source.advance_minutes)

        self._build(source)
        self._apply_kind(self._kind, initial=True)
        self._apply_point(self._point, initial=True)
        self._place_window()
        self.deiconify()
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.close())
        self.after(80, self.title_entry.focus_set)

    # ---------------------------------------------------------- 默认值

    @staticmethod
    def _default_slot(now: datetime) -> tuple[str, date]:
        minutes = now.hour * 60 + now.minute
        rounded = (minutes // 30 + 1) * 30
        day = now.date()
        if rounded >= 24 * 60:
            rounded = 9 * 60
            day = day + timedelta(days=1)
        return f"{rounded // 60:02d}:{rounded % 60:02d}", day

    @staticmethod
    def _plus_minutes(hhmm: str, minutes: int) -> datetime:
        base = datetime.combine(date.today(), parse_hhmm(hhmm))
        return base + timedelta(minutes=minutes)

    # ---------------------------------------------------------- 界面

    def _build(self, source: Entry) -> None:
        outer = tk.Frame(self, bg=COLORS["surface"])
        outer.pack(fill="both", expand=True, padx=px(26), pady=px(22))
        # 用一个细长占位控件固定对话框宽度
        tk.Frame(outer, bg=COLORS["surface"], width=px(440), height=1).pack()

        tk.Label(
            outer,
            text="编辑日程" if self.original else "新建日程",
            font=font(16, "bold"),
            fg=COLORS["text"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            outer,
            text="一次性选日期，固定安排选每周重复；同一时段可以添加多条，到点合并提醒。",
            font=font(9),
            fg=COLORS["text_3"],
            bg=COLORS["surface"],
            anchor="w",
            justify="left",
            wraplength=px(440),
        ).pack(fill="x", pady=(px(4), px(16)))

        self._section_label(outer, "类型")
        kind_row = tk.Frame(outer, bg=COLORS["surface"])
        kind_row.pack(fill="x", pady=(px(6), 0))
        self.kind_chips: dict[str, Chip] = {}
        for key, label in ((KIND_ONCE, "一次性"), (KIND_WEEKLY, "每周重复")):
            chip = Chip(
                kind_row,
                label,
                lambda k=key: self._apply_kind(k),
                height=34,
                pad_x=18,
                parent_bg=COLORS["surface"],
            )
            chip.pack(side="left", padx=(0, px(8)))
            self.kind_chips[key] = chip

        self.kind_body = tk.Frame(outer, bg=COLORS["surface"])
        self.kind_body.pack(fill="x", pady=(px(12), 0))
        self._build_once_box(self.kind_body)
        self._build_weekly_box(self.kind_body)

        time_header = tk.Frame(outer, bg=COLORS["surface"])
        time_header.pack(fill="x", pady=(px(16), 0))
        tk.Label(
            time_header,
            text="时间",
            font=font(9, "bold"),
            fg=COLORS["text_2"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(side="left")
        self.mode_chips: dict[str, Chip] = {}
        mode_box = tk.Frame(time_header, bg=COLORS["surface"])
        mode_box.pack(side="right")
        for key, label in (("range", "时间段"), ("point", "只提醒一次")):
            chip = Chip(
                mode_box,
                label,
                lambda k=key: self._apply_point(k == "point"),
                height=26,
                pad_x=10,
                font_size=8,
                parent_bg=COLORS["surface"],
                min_width=0,
            )
            chip.pack(side="left", padx=(px(6), 0))
            self.mode_chips[key] = chip

        time_row = tk.Frame(outer, bg=COLORS["surface"])
        time_row.pack(fill="x", pady=(px(6), 0))
        self.time_controls = tk.Frame(time_row, bg=COLORS["surface"])
        self.time_controls.pack(side="left")
        start_var = tk.StringVar(value=self._start_value)
        end_var = tk.StringVar(value=self._end_value)
        self.start_combo = self._time_combo(self.time_controls, start_var)
        self.start_combo.pack(side="left")
        self.time_sep = tk.Label(
            self.time_controls, text="至", font=font(10), fg=COLORS["text_3"], bg=COLORS["surface"]
        )
        self.time_sep.pack(side="left", padx=px(10))
        self.end_combo = self._time_combo(self.time_controls, end_var)
        self.end_combo.pack(side="left")
        self.time_hint = tk.Label(
            time_row,
            text="结束时间早于开始时间 = 跨夜",
            font=font(8),
            fg=COLORS["text_3"],
            bg=COLORS["surface"],
        )
        self.time_hint.pack(side="left", padx=(px(12), 0))
        self.start_var, self.end_var = start_var, end_var
        self._point = bool(source.point)

        self._section_label(outer, "提前提醒", top=14)
        advance_row = tk.Frame(outer, bg=COLORS["surface"])
        advance_row.pack(fill="x", pady=(px(6), 0))
        current = next((label for label, value in ADVANCE_OPTIONS if value == self._advance), ADVANCE_OPTIONS[0][0])
        self.advance_var = tk.StringVar(value=current)
        advance_combo = ttk.Combobox(
            advance_row,
            textvariable=self.advance_var,
            values=[label for label, _ in ADVANCE_OPTIONS],
            state="readonly",
            width=14,
            font=font(10),
        )
        advance_combo.pack(side="left")
        self._advance_combo = advance_combo

        self._section_label(outer, "要做什么", top=px(14))
        self.title_var = tk.StringVar(value=source.title)
        self.title_entry = tk.Entry(
            outer,
            textvariable=self.title_var,
            font=font(11),
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_strong"],
            highlightcolor=COLORS["accent"],
        )
        self.title_entry.pack(fill="x", pady=(px(6), 0), ipady=px(7))
        self.title_entry.bind("<Return>", lambda _e: self._save())

        self._section_label(outer, "备注（可选）", top=px(14))
        self.note_text = tk.Text(
            outer,
            height=3,
            font=font(9),
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_strong"],
            highlightcolor=COLORS["accent"],
            wrap="word",
            padx=px(8),
            pady=px(6),
        )
        self.note_text.pack(fill="x", pady=(px(6), 0))
        self.note_text.insert("1.0", source.note)
        tk.Label(
            outer,
            text="可以写地点、要带的东西、注意事项等，列表和提醒里都会显示。",
            font=font(8),
            fg=COLORS["text_3"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x", pady=(px(4), 0))

        self.error_label = tk.Label(
            outer,
            text="",
            font=font(9),
            fg=COLORS["red"],
            bg=COLORS["surface"],
            anchor="w",
            justify="left",
            wraplength=px(440),
        )
        self.error_label.pack(fill="x", pady=(px(10), 0))

        footer = tk.Frame(outer, bg=COLORS["surface"])
        footer.pack(fill="x", pady=(px(14), 0))
        if self.original is not None:
            RoundButton(
                footer,
                "删除",
                self._delete,
                kind="danger",
                height=36,
                pad_x=14,
                font_size=9,
                weight="normal",
                parent_bg=COLORS["surface"],
            ).pack(side="left")
        RoundButton(
            footer,
            "保存",
            self._save,
            kind="primary",
            height=38,
            pad_x=24,
            parent_bg=COLORS["surface"],
        ).pack(side="right")
        RoundButton(
            footer,
            "取消",
            self.close,
            kind="secondary",
            height=38,
            pad_x=20,
            parent_bg=COLORS["surface"],
        ).pack(side="right", padx=(0, px(10)))

    def _section_label(self, parent: tk.Misc, text: str, top: int = 16) -> None:
        tk.Label(
            parent,
            text=text,
            font=font(9, "bold"),
            fg=COLORS["text_2"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(fill="x", pady=(px(top), 0))

    def _time_combo(self, parent: tk.Misc, variable: tk.StringVar) -> ttk.Combobox:
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=TIME_OPTIONS,
            width=10,
            font=font(11, "bold"),
            justify="center",
            state="normal",
        )
        return combo

    def _build_once_box(self, parent: tk.Misc) -> None:
        self.once_box = tk.Frame(parent, bg=COLORS["surface"])
        self._section_label(self.once_box, "日期", top=0)
        row = tk.Frame(self.once_box, bg=COLORS["surface"])
        row.pack(fill="x", pady=(px(6), 0))
        self.date_button = RoundButton(
            row,
            self._date_text(),
            self._open_calendar,
            kind="secondary",
            height=36,
            pad_x=14,
            font_size=10,
            weight="normal",
            parent_bg=COLORS["surface"],
        )
        self.date_button.pack(side="left")
        self.quick_chips: dict[int, Chip] = {}
        for offset, label in ((0, "今天"), (1, "明天"), (2, "后天")):
            chip = Chip(
                row,
                label,
                lambda o=offset: self._set_date(date.today() + timedelta(days=o)),
                height=30,
                pad_x=12,
                font_size=9,
                parent_bg=COLORS["surface"],
            )
            chip.pack(side="left", padx=(px(8), 0))
            self.quick_chips[offset] = chip

    def _build_weekly_box(self, parent: tk.Misc) -> None:
        self.weekly_box = tk.Frame(parent, bg=COLORS["surface"])
        self._section_label(self.weekly_box, "星期（可多选）", top=0)
        row = tk.Frame(self.weekly_box, bg=COLORS["surface"])
        row.pack(fill="x", pady=(px(6), 0))
        self.weekday_chips: dict[int, Chip] = {}
        for day in WEEKDAY_ORDER:
            chip = Chip(
                row,
                WEEKDAY_SHORT[day],
                lambda d=day: self._toggle_weekday(d),
                selected=day in self._weekdays,
                height=34,
                pad_x=0,
                font_size=10,
                parent_bg=COLORS["surface"],
                min_width=42,
            )
            chip.pack(side="left", padx=(0, px(6)))
            self.weekday_chips[day] = chip

    # ---------------------------------------------------------- 状态

    def _date_text(self) -> str:
        return f"{self._date.year} 年 {self._date.month} 月 {self._date.day} 日 {WEEKDAY_CN[self._date.isoweekday()]}"

    def _set_date(self, day: date) -> None:
        self._date = day
        self.date_button.set_text(self._date_text())
        for offset, chip in self.quick_chips.items():
            chip.set_selected(day == date.today() + timedelta(days=offset))

    def _toggle_weekday(self, day: int) -> None:
        if day in self._weekdays:
            self._weekdays.discard(day)
        else:
            self._weekdays.add(day)
        chip = self.weekday_chips[day]
        chip.set_selected(day in self._weekdays)

    def _apply_kind(self, kind: str, initial: bool = False) -> None:
        self._kind = kind
        for key, chip in self.kind_chips.items():
            chip.set_selected(key == kind)
        self.once_box.pack_forget()
        self.weekly_box.pack_forget()
        if kind == KIND_ONCE:
            self.once_box.pack(fill="x")
            for offset, chip in self.quick_chips.items():
                chip.set_selected(self._date == date.today() + timedelta(days=offset))
        else:
            self.weekly_box.pack(fill="x")
            if not self._weekdays:
                self._weekdays.add(date.today().isoweekday())
            for day, chip in self.weekday_chips.items():
                chip.set_selected(day in self._weekdays)
        if not initial:
            self.error_label.configure(text="")

    def _apply_point(self, point: bool, initial: bool = False) -> None:
        self._point = bool(point)
        for key, chip in self.mode_chips.items():
            chip.set_selected(key == ("point" if point else "range"))
        if point:
            self.time_sep.pack_forget()
            self.end_combo.pack_forget()
            self.time_hint.configure(text="到点提醒一次，点「已完成」后就算完成")
        else:
            if not self.time_sep.winfo_manager():
                self.time_sep.pack(side="left", padx=px(10), after=self.start_combo)
            if not self.end_combo.winfo_manager():
                self.end_combo.pack(side="left", after=self.time_sep)
            self.time_hint.configure(text="结束时间早于开始时间 = 跨夜")
        if not initial:
            self.error_label.configure(text="")

    def _open_calendar(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        popup = CalendarPopup(self, self._date, self._set_date, anchor=self.date_button)

        def restore(event=None) -> None:  # noqa: ANN001
            if event is not None and getattr(event, "widget", None) is not popup:
                return
            try:
                if self.winfo_exists():
                    self.grab_set()
            except tk.TclError:
                pass

        popup.bind("<Destroy>", restore, add="+")

    # ---------------------------------------------------------- 保存

    def _collect(self) -> Entry:
        entry = self.original.clone() if self.original else Entry()
        entry.title = self.title_var.get().strip()
        entry.note = self.note_text.get("1.0", "end").strip()
        entry.kind = self._kind
        entry.point = self._point
        entry.start = self.start_var.get().strip()
        entry.end = entry.start if self._point else self.end_var.get().strip()
        if self._kind == KIND_ONCE:
            entry.date_str = self._date.isoformat()
            entry.weekdays = []
        else:
            entry.weekdays = sorted(self._weekdays)
        entry.advance_minutes = dict(
            (label, value) for label, value in ADVANCE_OPTIONS
        ).get(self.advance_var.get(), 0)
        if self.original is None:
            entry.enabled = True
        return entry

    def _save(self) -> None:
        entry = self._collect()
        errors = entry.validate()
        if errors:
            self.error_label.configure(text="；".join(errors))
            return
        self.app.save_entry(entry, is_new=self.original is None)
        self.close()

    def _delete(self) -> None:
        if self.original is None:
            self.close()
            return
        confirmed = messagebox.askyesno(
            "删除日程",
            f"确定要删除「{self.original.title}」吗？",
            parent=self,
        )
        if not confirmed:
            return
        self.close()
        self.app.delete_entry(self.original)

    # ---------------------------------------------------------- 收尾

    def _place_window(self) -> None:
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        master = self.app.main_window
        if master.winfo_viewable():
            base_x, base_y = master.winfo_rootx(), master.winfo_rooty()
            base_w, base_h = master.winfo_width(), master.winfo_height()
        else:
            base_x, base_y = 0, 0
            base_w, base_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = base_x + max(0, (base_w - width) // 2)
        y = base_y + max(px(20), (base_h - height) // 2)
        x = max(px(10), min(x, self.winfo_screenwidth() - width - px(10)))
        y = max(px(10), min(y, self.winfo_screenheight() - height - px(48)))
        self.geometry(f"+{x}+{y}")

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.app.on_dialog_closed(self)
        self.destroy()
