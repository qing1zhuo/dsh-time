"""主窗口：日程列表 + 今日概览 + 设置。"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import font as tkfont
from typing import Iterable

from .model import (
    KIND_ONCE,
    KIND_WEEKLY,
    WEEKDAY_CN,
    Entry,
    humanize_delta,
    occurrences_on_day,
)
from .scheduler import next_reminder
from .theme import COLORS, FAMILY, font, px
from .widgets import Badge, Card, Chip, Divider, MenuRow, RoundButton, ScrollFrame, Toggle

FILTERS = (
    ("all", "全部"),
    ("today", "今天"),
    ("once", "一次性"),
    ("weekly", "每周"),
)

FILTER_EMPTY = {
    "all": ("还没有任何安排", "点右上角「新建日程」，把要记住的事情放进来。"),
    "today": ("今天没有安排", "享受一下空闲，或者添加一条今天的日程。"),
    "once": ("没有一次性日程", "适合约会、考试、旅行这类只发生一次的事。"),
    "weekly": ("没有每周重复的日程", "适合晨会、健身课、每周复盘这类固定安排。"),
}


class MainWindow(tk.Toplevel):
    def __init__(self, app, show_now: bool = True) -> None:  # noqa: ANN001
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.title("时间表")
        self.configure(bg=COLORS["bg"])
        self.minsize(px(880), px(600))
        height = min(px(760), self.winfo_screenheight() - px(90))
        self.geometry(f"{px(1020)}x{height}")
        self._filter = "all"
        self._toast_job: str | None = None
        self.protocol("WM_DELETE_WINDOW", self.app.hide_main)
        self._build()
        self._place_window()
        self.refresh()
        if show_now:
            self.deiconify()

    # ---------------------------------------------------------- 构建界面

    def _build(self) -> None:
        self._build_header()
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=px(26), pady=(px(18), px(6)))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=px(304), weight=0)

        left = tk.Frame(body, bg=COLORS["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(20)))
        self._build_filters(left)
        self.list_scroll = ScrollFrame(left, bg=COLORS["bg"])
        self.list_scroll.pack(fill="both", expand=True, pady=(px(12), 0))

        self._build_sidebar(body)

        footer = tk.Frame(self, bg=COLORS["bg"])
        footer.pack(fill="x", padx=px(26), pady=(px(4), px(12)))
        self.status_label = tk.Label(
            footer, text="", font=font(9), fg=COLORS["text_2"], bg=COLORS["bg"], anchor="w"
        )
        self.status_label.pack(side="left")
        self.tray_label = tk.Label(
            footer,
            text="",
            font=font(9),
            fg=COLORS["green"],
            bg=COLORS["bg"],
            anchor="e",
        )
        self.tray_label.pack(side="right")

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=COLORS["surface"])
        header.pack(fill="x")
        inner = tk.Frame(header, bg=COLORS["surface"])
        inner.pack(fill="x", padx=px(26), pady=(px(18), px(14)))

        titles = tk.Frame(inner, bg=COLORS["surface"])
        titles.pack(side="left", anchor="w")
        tk.Label(
            titles, text="时间表", font=font(20, "bold"), fg=COLORS["text"], bg=COLORS["surface"]
        ).pack(anchor="w")
        self.subtitle = tk.Label(
            titles, text="", font=font(9), fg=COLORS["text_2"], bg=COLORS["surface"]
        )
        self.subtitle.pack(anchor="w", pady=(px(4), 0))

        self.new_button = RoundButton(
            inner,
            "＋  新建日程",
            self.app.new_entry,
            kind="primary",
            height=40,
            pad_x=20,
            font_size=10,
            parent_bg=COLORS["surface"],
        )
        self.new_button.pack(side="right")
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")

    def _build_filters(self, parent: tk.Misc) -> None:
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x")
        self.filter_chips: dict[str, Chip] = {}
        for key, label in FILTERS:
            chip = Chip(
                row,
                label,
                lambda k=key: self.set_filter(k),
                selected=(key == self._filter),
                height=32,
                pad_x=15,
                parent_bg=COLORS["bg"],
            )
            chip.pack(side="left", padx=(0, px(8)))
            self.filter_chips[key] = chip
        self.count_label = tk.Label(
            row, text="", font=font(9), fg=COLORS["text_3"], bg=COLORS["bg"]
        )
        self.count_label.pack(side="right", pady=(px(6), 0))

    def _build_sidebar(self, parent: tk.Misc) -> None:
        holder = tk.Frame(parent, bg=COLORS["bg"], width=px(304))
        holder.grid(row=0, column=1, sticky="nsew")
        holder.grid_propagate(False)
        scroll = ScrollFrame(holder, bg=COLORS["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.body

        today_card = Card(body, pad=px(16))
        today_card.pack(fill="x", pady=(0, px(12)))
        head = tk.Frame(today_card.content, bg=COLORS["surface"])
        head.pack(fill="x")
        tk.Label(
            head, text="今天", font=font(11, "bold"), fg=COLORS["text"], bg=COLORS["surface"]
        ).pack(side="left")
        self.today_date_label = tk.Label(
            head, text="", font=font(9), fg=COLORS["text_3"], bg=COLORS["surface"]
        )
        self.today_date_label.pack(side="right")
        self.today_rows = tk.Frame(today_card.content, bg=COLORS["surface"])
        self.today_rows.pack(fill="x", pady=(px(10), 0))

        settings_card = Card(body, pad=px(16))
        settings_card.pack(fill="x", pady=(0, px(12)))
        tk.Label(
            settings_card.content,
            text="提醒设置",
            font=font(11, "bold"),
            fg=COLORS["text"],
            bg=COLORS["surface"],
        ).pack(anchor="w")

        self.pet_toggle = self._setting_row(
            settings_card.content,
            "桌面小窗",
            "左下角常驻显示当前安排",
            self.app.settings.pet_enabled,
            self.app.set_pet_enabled,
        )
        self.sound_toggle = self._setting_row(
            settings_card.content,
            "提示音",
            "提醒时播放系统提示音",
            self.app.settings.sound_enabled,
            self.app.set_sound_enabled,
        )
        self.autostart_toggle = self._setting_row(
            settings_card.content,
            "开机自启",
            "登录 Windows 后自动启动",
            self.app.autostart_enabled(),
            self.app.set_autostart,
        )

        Divider(settings_card.content).pack(fill="x", pady=px(12))

        actions = (
            ("测试提醒", self.app.test_reminder),
            ("创建桌面快捷方式", self.app.create_shortcut),
            ("打开数据文件夹", self.app.open_data_dir),
        )
        for index, (label, callback) in enumerate(actions):
            row = MenuRow(settings_card.content, label, callback)
            row.pack(fill="x")
            if index < len(actions) - 1:
                Divider(settings_card.content).pack(fill="x")

        Divider(settings_card.content).pack(fill="x")
        MenuRow(
            settings_card.content,
            "退出时间表",
            self.app.quit_app,
            fg=COLORS["red"],
        ).pack(fill="x")

    def _setting_row(
        self,
        parent: tk.Misc,
        title: str,
        subtitle: str,
        value: bool,
        command,
    ) -> Toggle:
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill="x", pady=(px(12), 0))
        text_box = tk.Frame(row, bg=COLORS["surface"])
        text_box.pack(side="left", fill="x", expand=True)
        tk.Label(
            text_box, text=title, font=font(10), fg=COLORS["text"], bg=COLORS["surface"], anchor="w"
        ).pack(anchor="w")
        tk.Label(
            text_box,
            text=subtitle,
            font=font(8),
            fg=COLORS["text_3"],
            bg=COLORS["surface"],
            anchor="w",
        ).pack(anchor="w")
        toggle = Toggle(row, value, command, parent_bg=COLORS["surface"], width=44, height=24)
        toggle.pack(side="right", padx=(px(8), 0))
        return toggle

    # ---------------------------------------------------------- 数据视图

    def set_filter(self, key: str) -> None:
        if key == self._filter:
            return
        self._filter = key
        for filter_key, chip in self.filter_chips.items():
            chip.set_selected(filter_key == key)
        self._refresh_chips()
        self._refresh_list()

    def refresh(self) -> None:
        self._refresh_header()
        self._refresh_chips()
        self._refresh_list()
        self._refresh_sidebar()
        self.update_status()

    def _refresh_header(self) -> None:
        today = date.today()
        today_rows = occurrences_on_day(self.app.store.enabled_entries(), today)
        parts = [
            f"{today.year} 年 {today.month} 月 {today.day} 日",
            WEEKDAY_CN[today.isoweekday()],
        ]
        text = " · ".join(parts)
        if today_rows:
            text += f" · 今天 {len(today_rows)} 项安排"
            done_count = sum(
                1
                for entry, start_dt, _end in today_rows
                if entry.point and entry.has_done(Entry.fire_key(start_dt.date(), entry.start_time))
            )
            if done_count:
                text += f"（已完成 {done_count}）"
        else:
            text += " · 今天没有安排"
        self.subtitle.configure(text=text)
        self.today_date_label.configure(text=f"{today.month} 月 {today.day} 日")

    def _refresh_chips(self) -> None:
        entries = self.app.store.entries
        today = date.today()
        counts = {
            "all": len(entries),
            "today": len(occurrences_on_day(entries, today)),
            "once": len([entry for entry in entries if entry.kind == KIND_ONCE]),
            "weekly": len([entry for entry in entries if entry.kind == KIND_WEEKLY]),
        }
        for key, label in FILTERS:
            chip = self.filter_chips[key]
            chip.set_text(f"{label} {counts[key]}" if counts[key] else label)
        self.count_label.configure(text=f"共 {counts['all']} 条")

    def _occurrence_datetimes(
        self, entry: Entry, day: date
    ) -> tuple[datetime, datetime]:
        start_dt = datetime.combine(day, entry.start_time)
        return start_dt, start_dt + timedelta(minutes=entry.duration_minutes)

    def _refresh_list(self) -> None:
        try:
            position = self.list_scroll.canvas.yview()[0]
        except tk.TclError:
            position = 0.0
        self.list_scroll.clear()
        self.list_scroll.begin_bulk()
        today = date.today()
        entries = self.app.store.entries
        built = 0

        if self._filter == "today":
            rows = occurrences_on_day(entries, today)
            self.count_label.configure(text=f"今天 · 共 {len(rows)} 项")
            for entry, start_dt, end_dt in rows:
                self._build_card(entry, today, None, start_dt, end_dt)
            built = len(rows)

        elif self._filter == "all":
            self.count_label.configure(text=f"共 {len(entries)} 条")
            for entry in entries:
                occurrence = entry.occurrence(today) or entry.next_occurrence()
                if occurrence is not None:
                    start_dt, end_dt = occurrence
                    self._build_card(entry, start_dt.date(), None, start_dt, end_dt)
                else:
                    start_dt, end_dt = self._occurrence_datetimes(entry, entry.day or today)
                    self._build_card(entry, start_dt.date(), None, start_dt, end_dt)
                built += 1

        elif self._filter == "once":
            groups: dict[date, list[Entry]] = {}
            for entry in entries:
                if entry.kind != KIND_ONCE or entry.day is None:
                    continue
                groups.setdefault(entry.day, []).append(entry)
            self.count_label.configure(
                text=f"共 {len(groups)} 天 · {sum(len(items) for items in groups.values())} 条"
            )
            for day in sorted(groups):
                items = sorted(groups[day], key=lambda item: item.start_time)
                marker = ""
                if day == today:
                    marker = " · 今天"
                elif day == today + timedelta(days=1):
                    marker = " · 明天"
                self._build_group_header(
                    f"{day.year} 年 {day.month} 月 {day.day} 日",
                    f"{WEEKDAY_CN[day.isoweekday()]}{marker}",
                    len(items),
                )
                for index, entry in enumerate(items, start=1):
                    start_dt, end_dt = self._occurrence_datetimes(entry, day)
                    self._build_card(entry, day, index, start_dt, end_dt)
                    built += 1

        else:  # weekly：按周一~周日分组
            buckets: dict[int, list[Entry]] = {weekday: [] for weekday in range(1, 8)}
            for entry in entries:
                if entry.kind != KIND_WEEKLY:
                    continue
                for weekday in entry.weekdays:
                    if weekday in buckets:
                        buckets[weekday].append(entry)
            total = sum(len(items) for items in buckets.values())
            self.count_label.configure(text=f"每周 · 共 {total} 项")
            for weekday in range(1, 8):
                items = sorted(buckets[weekday], key=lambda item: item.start_time)
                if not items:
                    continue
                day = today + timedelta(days=(weekday - today.isoweekday()) % 7)
                self._build_group_header(WEEKDAY_CN[weekday], "", len(items))
                for entry in items:
                    start_dt, end_dt = self._occurrence_datetimes(entry, day)
                    self._build_card(entry, day, None, start_dt, end_dt)
                    built += 1

        self.list_scroll.end_bulk()

        if built == 0:
            self._build_empty_state()
            return

        if position > 0:
            # 刷新后回到原来的滚动位置，改完一条日程不会跳回顶部
            self.list_scroll.canvas.after_idle(
                lambda: self.list_scroll.canvas.yview_moveto(position)
            )

    def _build_group_header(self, title: str, subtitle: str, count: int) -> None:
        header = tk.Frame(self.list_scroll.body, bg=COLORS["bg"])
        header.pack(fill="x", pady=(px(10), px(8)))
        tk.Label(
            header, text=title, font=font(12, "bold"), fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(side="left")
        if subtitle:
            tk.Label(
                header, text=subtitle, font=font(9), fg=COLORS["text_3"], bg=COLORS["bg"]
            ).pack(side="left", padx=(px(8), 0), pady=(px(3), 0))
        tk.Label(
            header,
            text=f"{count} 项",
            font=font(9),
            fg=COLORS["text_3"],
            bg=COLORS["bg"],
        ).pack(side="right", pady=(px(3), 0))
        tk.Frame(self.list_scroll.body, bg=COLORS["border"], height=1).pack(
            fill="x", pady=(0, px(10))
        )

    def _build_empty_state(self) -> None:
        title, hint = FILTER_EMPTY[self._filter]
        box = tk.Frame(self.list_scroll.body, bg=COLORS["bg"])
        box.pack(fill="x", pady=(px(46), 0))
        try:
            from . import paths

            icon = tk.PhotoImage(file=str(paths.ASSETS_DIR / "app-256.png")).subsample(4)
            self._empty_icon = icon
            tk.Label(box, image=icon, bg=COLORS["bg"]).pack(anchor="center", pady=(0, px(16)))
        except (tk.TclError, OSError):
            pass
        tk.Label(
            box, text=title, font=font(13, "bold"), fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="center")
        tk.Label(
            box,
            text=hint,
            font=font(9),
            fg=COLORS["text_3"],
            bg=COLORS["bg"],
            wraplength=px(360),
            justify="center",
        ).pack(anchor="center", pady=(px(6), px(16)))
        RoundButton(
            box,
            "＋  新建日程",
            self.app.new_entry,
            kind="secondary",
            height=36,
            pad_x=16,
            parent_bg=COLORS["bg"],
        ).pack(anchor="center")

    def _build_card(
        self,
        entry: Entry,
        day: date,
        index: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> None:
        surface = COLORS["surface"]
        now = datetime.now()
        enabled = entry.enabled
        key = Entry.fire_key(day, entry.start_time) if entry.point else None
        done = bool(key and entry.has_done(key))
        title_color = COLORS["text_3"] if (not enabled or done) else COLORS["text"]
        time_color = COLORS["text_3"] if (not enabled or done) else COLORS["text"]
        meta_color = COLORS["text_3"] if (not enabled or done) else COLORS["text_2"]

        card = tk.Frame(
            self.list_scroll.body,
            bg=surface,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
            cursor="hand2",
        )
        card.pack(fill="x", pady=(0, px(8)))

        inner = tk.Frame(card, bg=surface)
        inner.pack(fill="x", padx=px(14), pady=px(12))

        if index is not None:
            number = tk.Label(
                inner,
                text=f"{index}.",
                font=font(9),
                fg=COLORS["text_3"],
                bg=surface,
                anchor="ne",
                width=3,
            )
            number.grid(row=0, column=0, sticky="nw", padx=(0, px(6)), pady=(px(4), 0))
            time_column, content_column, actions_column = 1, 2, 3
        else:
            number = None
            time_column, content_column, actions_column = 0, 1, 2
        inner.grid_columnconfigure(content_column, weight=1)

        time_box = tk.Frame(inner, bg=surface)
        time_box.grid(row=0, column=time_column, sticky="nw", padx=(0, px(10)))
        start_label = tk.Label(
            time_box,
            text=f"{start_dt:%H:%M}",
            font=font(14, "bold"),
            fg=time_color,
            bg=surface,
        )
        start_label.pack(anchor="w")
        if entry.point:
            end_text = "仅提醒"
        else:
            overnight = end_dt.date() != start_dt.date()
            end_text = f"至 {end_dt:%H:%M}" + (" 次日" if overnight else "")
        end_label = tk.Label(
            time_box,
            text=end_text,
            font=font(8),
            fg=COLORS["text_3"],
            bg=surface,
        )
        end_label.pack(anchor="w")

        content = tk.Frame(inner, bg=surface)
        content.grid(row=0, column=content_column, sticky="nsew", padx=(0, px(10)))
        title_row = tk.Frame(content, bg=surface)
        title_row.pack(fill="x")
        display_title = entry.title or "（未命名）"
        if len(display_title) > 60:
            display_title = display_title[:60] + "…"
        title_font = font(12, "bold")
        if done:
            title_font = tkfont.Font(family=FAMILY, size=12, weight="bold", overstrike=1)
        title_label = tk.Label(
            title_row,
            text=display_title,
            font=title_font,
            fg=title_color,
            bg=surface,
            anchor="w",
            justify="left",
        )
        title_label.pack(side="left")

        badge = self._status_badge(title_row, entry, day, start_dt, end_dt)
        if badge is not None:
            badge.pack(side="left", padx=(px(8), 0))

        meta_parts: list[str] = []
        if entry.kind == KIND_WEEKLY:
            meta_parts.append(entry.weekday_label())
        if entry.advance_minutes:
            meta_parts.append(entry.advance_label())
        meta_label = None
        if meta_parts:
            meta_label = tk.Label(
                content,
                text=" · ".join(meta_parts),
                font=font(9),
                fg=meta_color,
                bg=surface,
                anchor="w",
            )
            meta_label.pack(fill="x", pady=(px(4), 0))

        note_label = None
        if entry.note:
            note = entry.note.replace("\n", " ")
            if len(note) > 120:
                note = note[:120] + "…"
            note_label = tk.Label(
                content,
                text=note,
                font=font(9),
                fg=COLORS["text_3"],
                bg=surface,
                anchor="w",
                justify="left",
            )
            note_label.pack(fill="x", pady=(px(2), 0))

        # 按卡片实际宽度换行，窗口变窄或标题很长时也不会被截断
        self._bind_card_wrap(content, title_label, badge, note_label)

        actions = tk.Frame(inner, bg=surface)
        actions.grid(row=0, column=actions_column, sticky="e")
        toggle = Toggle(
            actions,
            enabled,
            lambda value, item=entry: self.app.set_entry_enabled(item, value),
            parent_bg=surface,
            width=42,
            height=24,
        )
        toggle.pack(side="left", padx=(0, px(10)))
        if entry.point:
            done_button = RoundButton(
                actions,
                "撤销" if done else "完成",
                lambda item=entry, d=day: self.app.toggle_entry_done(item, d),
                kind="ghost",
                height=28,
                pad_x=9,
                font_size=9,
                weight="normal",
                parent_bg=surface,
            )
            done_button.pack(side="left", padx=(0, px(2)))
        edit_button = RoundButton(
            actions,
            "编辑",
            lambda item=entry: self.app.edit_entry(item),
            kind="ghost",
            height=28,
            pad_x=9,
            font_size=9,
            weight="normal",
            parent_bg=surface,
        )
        edit_button.pack(side="left")
        delete_button = RoundButton(
            actions,
            "删除",
            lambda item=entry: self.app.delete_entry(item),
            kind="ghost",
            height=28,
            pad_x=9,
            font_size=9,
            weight="normal",
            parent_bg=surface,
        )
        delete_button.pack(side="left", padx=(px(2), 0))

        clickable = [card, inner, time_box, start_label, end_label, content, title_row, title_label]
        if number is not None:
            clickable.append(number)
        if meta_label is not None:
            clickable.append(meta_label)
        if note_label is not None:
            clickable.append(note_label)
        for widget in clickable:
            widget.bind("<Button-1>", lambda _e, item=entry: self.app.edit_entry(item))
            widget.bind("<Enter>", lambda _e, target=card: self._hover_card(target, True))
            widget.bind("<Leave>", lambda _e, target=card: self._hover_card(target, False))

    def _status_badge(
        self,
        parent: tk.Misc,
        entry: Entry,
        day: date,
        start_dt: datetime,
        end_dt: datetime,
    ) -> Badge | None:
        now = datetime.now()
        key = Entry.fire_key(day, entry.start_time) if entry.point else None
        if key and entry.has_done(key):
            return Badge(parent, "已完成", fg=COLORS["green"], bg=COLORS["green_soft"])
        if not entry.enabled:
            return Badge(parent, "已暂停", fg=COLORS["text_3"], bg=COLORS["bg_alt"])
        if day != now.date():
            return None
        if entry.point:
            if start_dt <= now:
                return Badge(parent, "待完成", fg=COLORS["amber"], bg=COLORS["amber_soft"])
            return None
        if start_dt <= now <= end_dt:
            return Badge(parent, "进行中", fg=COLORS["green"], bg=COLORS["green_soft"])
        return None

    def _hover_card(self, card: tk.Frame, entering: bool) -> None:
        if not card.winfo_exists():
            return
        if entering:
            card.configure(highlightbackground=COLORS["accent_soft"], highlightcolor=COLORS["accent_soft"])
        else:
            card.after(40, lambda: self._unhover(card))

    def _unhover(self, card: tk.Frame) -> None:
        if not card.winfo_exists():
            return
        x, y = card.winfo_pointerxy()
        widget = card.winfo_containing(x, y)
        current = widget
        while current is not None:
            if current is card:
                return
            current = getattr(current, "master", None)
        card.configure(highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])

    def _bind_card_wrap(
        self,
        content: tk.Frame,
        title_label: tk.Label,
        badge: tk.Label | None,
        note_label: tk.Label | None,
    ) -> None:
        """让标题和备注跟随卡片宽度自动换行。"""

        def apply(_event=None) -> None:
            width = content.winfo_width()
            if width <= 1:
                return
            badge_width = (badge.winfo_reqwidth() + px(10)) if badge is not None else 0
            title_wrap = max(px(110), width - badge_width)
            for label, wrap in ((title_label, title_wrap), (note_label, width)):
                if label is None:
                    continue
                try:
                    current = int(float(str(label.cget("wraplength"))))
                except (tk.TclError, ValueError, TypeError):
                    current = -1
                if current != wrap:
                    label.configure(wraplength=wrap)

        content.bind("<Configure>", apply, add="+")

    def _refresh_sidebar(self) -> None:
        for child in self.today_rows.winfo_children():
            child.destroy()
        today = date.today()
        rows = occurrences_on_day(self.app.store.enabled_entries(), today)
        self.today_date_label.configure(text=f"{today.month} 月 {today.day} 日")
        if not rows:
            tk.Label(
                self.today_rows,
                text="今天没有安排，放松一下。",
                font=font(9),
                fg=COLORS["text_3"],
                bg=COLORS["surface"],
                anchor="w",
            ).pack(fill="x")
        else:
            now = datetime.now()
            for entry, start_dt, end_dt in rows[:6]:
                row = tk.Frame(self.today_rows, bg=COLORS["surface"])
                row.pack(fill="x", pady=(0, px(7)))
                tk.Label(
                    row,
                    text=f"{start_dt:%H:%M}",
                    font=font(9, "bold"),
                    fg=COLORS["accent_ink"],
                    bg=COLORS["surface"],
                    width=6,
                    anchor="w",
                ).pack(side="left")
                active = start_dt <= now <= end_dt
                done_here = entry.point and entry.has_done(
                    Entry.fire_key(start_dt.date(), entry.start_time)
                )
                title = entry.title
                if len(title) > 12:
                    title = title[:12] + "…"
                tk.Label(
                    row,
                    text=title,
                    font=font(9),
                    fg=COLORS["text_3"] if done_here else (COLORS["green"] if active else COLORS["text_2"]),
                    bg=COLORS["surface"],
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)
                if done_here:
                    tk.Label(
                        row, text="✓", font=font(9, "bold"), fg=COLORS["green"], bg=COLORS["surface"]
                    ).pack(side="right")
                elif active:
                    tk.Label(
                        row, text="●", font=font(8), fg=COLORS["green"], bg=COLORS["surface"]
                    ).pack(side="right")
            if len(rows) > 6:
                tk.Label(
                    self.today_rows,
                    text=f"还有 {len(rows) - 6} 项",
                    font=font(8),
                    fg=COLORS["text_3"],
                    bg=COLORS["surface"],
                    anchor="w",
                ).pack(fill="x")

        self.sound_toggle.set_value(self.app.settings.sound_enabled, animate=False)
        self.pet_toggle.set_value(bool(self.app.settings.pet_enabled), animate=False)
        self.autostart_toggle.set_value(self.app.autostart_enabled(), animate=False)

    def set_pet_toggle(self, value: bool) -> None:
        toggle = getattr(self, "pet_toggle", None)
        if toggle is not None:
            toggle.set_value(bool(value), animate=False)

    def update_status(self) -> None:
        self.tray_label.configure(
            text="● 托盘运行中" if self.app.tray_alive() else "○ 托盘未运行",
            fg=COLORS["green"] if self.app.tray_alive() else COLORS["red"],
        )
        if self.app.paused:
            self.status_label.configure(
                text="提醒已暂停 · 右键托盘图标可以恢复", fg=COLORS["amber"]
            )
            return
        now = datetime.now()
        upcoming = next_reminder(self.app.store.enabled_entries(), now)
        if not upcoming:
            self.status_label.configure(text="暂无待提醒的安排", fg=COLORS["text_3"])
            return
        entry, fire_at = upcoming
        delta = (fire_at - now).total_seconds()
        when = humanize_delta(delta) if delta > 0 else "随时会提醒"
        self.status_label.configure(
            text=f"下次提醒：{fire_at:%H:%M}  {entry.title} · {when}", fg=COLORS["text_2"]
        )

    # ---------------------------------------------------------- 其他

    def _place_window(self) -> None:
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(px(20), (screen_w - width) // 2)
        y = max(px(20), (screen_h - height) // 2 - px(24))
        self.geometry(f"+{x}+{y}")

    def show(self) -> None:
        self.refresh()
        self.deiconify()
        # 从托盘唤醒时，Windows 可能不让后台进程抢焦点，短暂置顶可以确保窗口出现在最前面。
        try:
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.after(600, lambda: self._drop_topmost())
        except tk.TclError:
            pass

    def _drop_topmost(self) -> None:
        try:
            if self.winfo_exists():
                self.attributes("-topmost", False)
        except tk.TclError:
            pass

    def toast(self, message: str) -> None:
        if self._toast_job:
            try:
                self.after_cancel(self._toast_job)
            except tk.TclError:
                pass
            self._toast_job = None
        for child in self.winfo_children():
            if getattr(child, "_is_toast", False):
                child.destroy()
        label = tk.Label(
            self,
            text=message,
            font=font(9),
            bg="#1F2937",
            fg="#FFFFFF",
            padx=px(16),
            pady=px(9),
        )
        label._is_toast = True  # type: ignore[attr-defined]
        label.place(relx=0.5, rely=1.0, anchor="s", y=-px(54))
        label.lift()

        def hide() -> None:
            if label.winfo_exists():
                label.destroy()
            self._toast_job = None

        self._toast_job = self.after(2600, hide)
