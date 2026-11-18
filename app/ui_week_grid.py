"""周课表网格：周一~周日 × 时间轴，课程按名字着色。

只负责画图，不直接改数据：
- on_open(entry)               点色块 → 编辑
- on_pick_slot(day, start, end) 点空格子 → 用这个时间新建
- on_shift(delta_weeks)        上一周 / 下一周
- on_today()                   回到本周
"""

from __future__ import annotations

import re
import tkinter as tk
from datetime import date, datetime, time, timedelta
from tkinter import font as tkfont
from typing import Callable, Iterable

from . import model
from .model import WEEKDAY_CN, Entry, monday_of, occurrences_on_day
from .theme import COLORS, FAMILY, course_color as palette_color, font, px, round_rect
from .widgets import RoundButton

ROW_H = 42
HEADER_H = 52
GUTTER = 48
MIN_ROWS = 8


def course_color(entry: Entry) -> tuple[str, str]:
    """同一门课固定一种颜色：优先按科目，其次标题。"""
    return palette_color(entry.subject or entry.title or entry.id)


_ROOM_CODE_RE = re.compile(r"[A-Za-z]?\d{2,4}")


def _short_room(room: str) -> str:
    """「公共教学楼D203」→「D203」，「实验中心D501」→「D501」。"""
    parts = room.split()
    if len(parts) > 1:
        return parts[-1]
    match = _ROOM_CODE_RE.search(room)
    if match and match.start() > 0:
        return room[match.start():]
    return room


class WeekGrid(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        entries: Iterable[Entry],
        anchor: date | None = None,
        *,
        on_open: Callable[[Entry], None] | None = None,
        on_pick_slot: Callable[[date, str, str], None] | None = None,
        on_shift: Callable[[int], None] | None = None,
        on_today: Callable[[], None] | None = None,
        course_only: bool = False,
    ) -> None:
        super().__init__(master, bg=COLORS["bg"])
        self.entries = list(entries)
        self.anchor = monday_of(anchor or date.today())
        self.on_open = on_open
        self.on_pick_slot = on_pick_slot
        self.on_shift = on_shift
        self.on_today = on_today
        self.course_only = course_only
        self._by_id = {entry.id: entry for entry in self.entries}
        self._start_hour, self._end_hour = self._hour_range()
        self._width = 0
        self._tip: tk.Toplevel | None = None
        self._tip_job: str | None = None
        self._tip_entry: str | None = None
        self._title_font = tkfont.Font(family=FAMILY, size=9, weight="bold")
        self._title_small_font = tkfont.Font(family=FAMILY, size=8, weight="bold")
        self._title_tiny_font = tkfont.Font(family=FAMILY, size=7, weight="bold")
        self._meta_font = tkfont.Font(family=FAMILY, size=8)
        self._tiny_font = tkfont.Font(family=FAMILY, size=7)
        self._hour_font = tkfont.Font(family=FAMILY, size=8)
        self._day_font = tkfont.Font(family=FAMILY, size=9, weight="bold")
        self._build()
        self.bind("<Configure>", self._on_configure)
        self.after_idle(self.paint)

    # ---------------------------------------------------------- 结构

    def _build(self) -> None:
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x")
        self.prev_button = RoundButton(
            header,
            "‹",
            lambda: self._shift(-1),
            kind="secondary",
            height=30,
            pad_x=12,
            font_size=12,
            weight="bold",
            parent_bg=COLORS["bg"],
            tooltip="上一周",
        )
        self.prev_button.pack(side="left")
        self.next_button = RoundButton(
            header,
            "›",
            lambda: self._shift(1),
            kind="secondary",
            height=30,
            pad_x=12,
            font_size=12,
            weight="bold",
            parent_bg=COLORS["bg"],
            tooltip="下一周",
        )
        self.next_button.pack(side="left", padx=(px(6), 0))

        self.title_label = tk.Label(
            header, text="", font=font(12, "bold"), fg=COLORS["text"], bg=COLORS["bg"], anchor="w"
        )
        self.title_label.pack(side="left", padx=(px(12), 0))
        self.count_label = tk.Label(
            header, text="", font=font(9), fg=COLORS["text_3"], bg=COLORS["bg"]
        )
        self.count_label.pack(side="left", padx=(px(10), 0), pady=(px(3), 0))

        self.today_button = RoundButton(
            header,
            "本周",
            self._go_today,
            kind="soft",
            height=30,
            pad_x=14,
            font_size=9,
            weight="normal",
            parent_bg=COLORS["bg"],
        )
        self.today_button.pack(side="right")

        self.head_canvas = tk.Canvas(
            self,
            height=px(HEADER_H),
            bg=COLORS["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.head_canvas.pack(fill="x", pady=(px(10), 0))

        body_height = px(ROW_H) * (self._end_hour - self._start_hour)
        self.canvas = tk.Canvas(
            self,
            height=body_height,
            bg=COLORS["bg"],
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.canvas.pack(fill="x")
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._hide_tip())

    # ---------------------------------------------------------- 尺寸

    def _col_width(self) -> float:
        return max(1.0, (self._width - px(GUTTER)) / 7.0)

    def _x(self, column: int) -> float:
        return px(GUTTER) + column * self._col_width()

    def _y(self, hour: float) -> float:
        return (hour - self._start_hour) * px(ROW_H)

    def _hour_range(self) -> tuple[int, int]:
        spans: list[tuple[int, int]] = []
        for entry in self.entries:
            spans.append(self._entry_hours(entry))
        if not spans:
            return 7, 23
        start = min(span[0] for span in spans) - 1
        end = max(span[1] for span in spans) + 1
        start = max(0, start)
        end = min(24, max(end, start + MIN_ROWS))
        if end - start < MIN_ROWS:
            start = max(0, end - MIN_ROWS)
        return start, end

    @staticmethod
    def _entry_hours(entry: Entry) -> tuple[int, int]:
        start = entry.start_time.hour
        if entry.point:
            return start, min(24, start + 1)
        if entry.duration_minutes >= 24 * 60 or entry.end_time <= entry.start_time:
            return start, 24
        end = entry.end_time.hour + (1 if entry.end_time.minute else 0)
        return start, min(24, max(start + 1, end))

    def _on_configure(self, event) -> None:  # noqa: ANN001
        width = event.width
        if width != self._width and width > 1:
            self._width = width
            self.paint()

    # ---------------------------------------------------------- 绘制

    def paint(self) -> None:
        width = self.canvas.winfo_width()
        if width <= 1:
            width = self.winfo_width()
        if width <= 1:
            return
        self._width = width
        self._paint_header()
        self._paint_body()
        self._paint_titles()

    def _paint_titles(self) -> None:
        title, dates = self._week_labels()
        self.title_label.configure(text=f"{title} · {dates}")
        rows = self._week_occurrences()
        if not rows:
            text = "这一周没有课程" if self.course_only else "这一周没有安排"
        else:
            text = f"{len(rows)} 项课程" if self.course_only else f"{len(rows)} 项安排"
        self.count_label.configure(text=text)
        self.today_button.set_enabled(self.anchor != monday_of(date.today()))

    def _week_labels(self) -> tuple[str, str]:
        first, last = self.anchor, self.anchor + timedelta(days=6)
        dates = f"{first.month} 月 {first.day} 日 – {last.month} 月 {last.day} 日"
        term = model.TERM
        if term.active:
            week = term.week_of(self.anchor + timedelta(days=3))
            if week is None:
                return "开学前", dates
            if week > term.weeks:
                return f"第 {week} 周（学期已结束）", dates
            return f"第 {week} 周", dates
        return "课表", dates

    def _week_occurrences(self) -> list[tuple[Entry, datetime, datetime]]:
        rows: list[tuple[Entry, datetime, datetime]] = []
        for offset in range(7):
            rows.extend(occurrences_on_day(self.entries, self.anchor + timedelta(days=offset)))
        return rows

    def _is_current_week(self) -> bool:
        return self.anchor == monday_of(date.today())

    def _paint_header(self) -> None:
        canvas = self.head_canvas
        canvas.delete("all")
        width = self._width
        today = date.today()
        for column in range(7):
            day = self.anchor + timedelta(days=column)
            x0, x1 = self._x(column), self._x(column + 1)
            if day == today:
                canvas.create_rectangle(
                    x0 + 1, 0, x1 - 1, px(HEADER_H),
                    fill=COLORS["accent_soft"], outline="",
                )
            fg = COLORS["accent_ink"] if day == today else COLORS["text_2"]
            canvas.create_text(
                (x0 + x1) / 2, px(18), text=WEEKDAY_CN[day.isoweekday()],
                font=self._day_font, fill=fg, anchor="center",
            )
            canvas.create_text(
                (x0 + x1) / 2, px(36), text=f"{day.month}/{day.day}",
                font=self._meta_font,
                fill=COLORS["accent_ink"] if day == today else COLORS["text_3"],
                anchor="center",
            )
        canvas.create_line(px(GUTTER), px(HEADER_H) - 1, width, px(HEADER_H) - 1, fill=COLORS["border"])
        for column in range(8):
            x = min(self._x(column), width - 1)
            canvas.create_line(x, 0, x, px(HEADER_H), fill=COLORS["border"])

    def _paint_body(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = self._width
        gutter = px(GUTTER)
        bottom = self._y(self._end_hour)
        today = date.today()

        # 今天所在列加一层很淡的底色
        if self.anchor <= today <= self.anchor + timedelta(days=6):
            column = (today - self.anchor).days
            canvas.create_rectangle(
                self._x(column) + 1, 0, self._x(column + 1) - 1, bottom,
                fill=COLORS["surface_2"], outline="",
            )

        # 横向小时线 + 左侧时间刻度
        for hour in range(self._start_hour, self._end_hour + 1):
            y = self._y(hour)
            canvas.create_line(gutter, y, width, y, fill=COLORS["border"])
            if hour < self._end_hour:
                canvas.create_text(
                    gutter - px(7), y + px(3), text=f"{hour:02d}:00",
                    font=self._hour_font, fill=COLORS["text_3"], anchor="ne",
                )
        # 纵向星期分隔线
        for column in range(8):
            x = min(self._x(column), width - 1)
            canvas.create_line(x, 0, x, bottom, fill=COLORS["border"])

        self._paint_blocks()
        self._paint_now_line()
        if not self._week_occurrences():
            self._paint_empty()

    def _paint_blocks(self) -> None:
        canvas = self.canvas
        gutter = px(GUTTER)
        for column in range(7):
            day = self.anchor + timedelta(days=column)
            rows = self._layout_day(day)
            for row in rows:
                entry = row["entry"]
                column_left = gutter + column * self._col_width()
                if row["point"]:
                    # 时间点提醒：一条小胶囊贴在列的右侧，压在课程块上面
                    y0 = self._clip_y(row["start_hour"])
                    y1 = min(y0 + px(17), self._y(self._end_hour))
                    title = self._fit(
                        entry.title or "（未命名）",
                        self._title_tiny_font,
                        self._col_width() - px(16),
                    )
                    chip_w = min(
                        self._col_width() - px(4),
                        self._title_tiny_font.measure(title) + px(14),
                    )
                    x1 = column_left + self._col_width() - px(2)
                    x0 = x1 - chip_w
                    fill, ink = course_color(entry)
                    round_rect(
                        canvas, x0, y0, x1, y1, px(4), fill=fill, outline=fill,
                        tags=("block", f"entry:{entry.id}"),
                    )
                    canvas.create_line(
                        x0 + px(1.5), y0 + px(3), x0 + px(1.5), y1 - px(3),
                        fill=ink, width=px(2), capstyle="round",
                        tags=("block", f"entry:{entry.id}"),
                    )
                    canvas.create_text(
                        x0 + px(7), (y0 + y1) / 2, text=title, anchor="w",
                        font=self._title_tiny_font, fill=ink,
                        tags=("block", f"entry:{entry.id}"),
                    )
                    continue
                # 时间重叠的课程并排放，各占 1/lanes 列宽
                x0 = column_left + row["lane"] * self._col_width() / row["lanes"] + px(2)
                x1 = column_left + (row["lane"] + 1) * self._col_width() / row["lanes"] - px(2)
                y0 = self._clip_y(row["start_hour"])
                y1 = self._clip_y(row["end_hour"])
                if y1 - y0 < px(22):
                    y1 = y0 + px(22)
                fill, ink = course_color(entry)
                block_w = x1 - x0
                if block_w < px(60):
                    title_font = self._title_tiny_font
                elif block_w < px(84):
                    title_font = self._title_small_font
                else:
                    title_font = self._title_font
                round_rect(canvas, x0, y0, x1, y1, px(6), fill=fill, outline=fill, tags=("block", f"entry:{entry.id}"))
                canvas.create_line(
                    x0 + px(1.5), y0 + px(6), x0 + px(1.5), max(y0 + px(6), y1 - px(6)),
                    fill=ink, width=px(3), capstyle="round", tags=("block", f"entry:{entry.id}"),
                )
                title = self._fit(entry.title or "（未命名）", title_font, block_w - px(12))
                canvas.create_text(
                    x0 + px(8), y0 + px(5), text=title, anchor="nw",
                    font=title_font, fill=ink,
                    tags=("block", f"entry:{entry.id}"),
                )
                detail = entry.period.strip()
                if not detail:
                    detail = entry.time_label() if not entry.point else f"{entry.start_time:%H:%M}"
                detail = self._fit(detail, self._tiny_font, block_w - px(10))
                if block_w >= px(58) and y1 - y0 >= px(34):
                    canvas.create_text(
                        x0 + px(8), y1 - px(4), text=detail, anchor="sw",
                        font=self._tiny_font, fill=ink,
                        tags=("block", f"entry:{entry.id}"),
                    )
                info_line = self._info_text(entry, block_w - px(8))
                if info_line and block_w >= px(76) and y1 - y0 >= px(56):
                    canvas.create_text(
                        x0 + px(8), y0 + px(22), text=info_line,
                        anchor="nw",
                        font=self._tiny_font, fill=ink,
                        tags=("block", f"entry:{entry.id}"),
                    )

    def _layout_day(self, day: date) -> list[dict]:
        day_start = datetime.combine(day, time.min)
        range_start = day_start + timedelta(hours=self._start_hour)
        range_end = day_start + timedelta(hours=self._end_hour)
        timed: list[dict] = []
        points: list[dict] = []
        for entry, start_dt, end_dt in occurrences_on_day(self.entries, day):
            if entry.point:
                # 时间点提醒画成一条细标记，不参与并排，免得把课程挤成一条缝
                if not (range_start <= start_dt < range_end):
                    continue
                points.append(
                    {
                        "entry": entry,
                        "start": start_dt,
                        "end": start_dt + timedelta(minutes=1),
                        "start_hour": (start_dt - day_start).total_seconds() / 3600,
                        "end_hour": (start_dt - day_start).total_seconds() / 3600,
                        "point": True,
                    }
                )
                continue
            start = max(start_dt, range_start)
            end = min(end_dt, range_end)
            if start >= range_end or end <= range_start:
                continue
            timed.append(
                {
                    "entry": entry,
                    "start": start,
                    "end": end,
                    "start_hour": (start - day_start).total_seconds() / 3600,
                    "end_hour": (end - day_start).total_seconds() / 3600,
                    "point": False,
                }
            )
        timed.sort(key=lambda item: (item["start"], item["end"]))
        # 重叠的课程并排放，各占 1/lanes 列宽
        clusters: list[list[dict]] = []
        current: list[dict] = []
        cluster_end: datetime | None = None
        for item in timed:
            if cluster_end is not None and item["start"] >= cluster_end:
                clusters.append(current)
                current = []
                cluster_end = None
            current.append(item)
            cluster_end = item["end"] if cluster_end is None else max(cluster_end, item["end"])
        if current:
            clusters.append(current)
        for cluster in clusters:
            lane_ends: list[datetime] = []
            for item in cluster:
                for index, end in enumerate(lane_ends):
                    if end <= item["start"]:
                        lane_ends[index] = item["end"]
                        item["lane"] = index
                        break
                else:
                    item["lane"] = len(lane_ends)
                    lane_ends.append(item["end"])
            for item in cluster:
                item["lanes"] = len(lane_ends)
        return timed + points

    def _paint_now_line(self) -> None:
        if not self._is_current_week():
            return
        now = datetime.now()
        hour = now.hour + now.minute / 60 + now.second / 3600
        if not (self._start_hour <= hour < self._end_hour):
            return
        y = self._y(hour)
        gutter = px(GUTTER)
        self.canvas.create_line(gutter, y, self._width, y, fill=COLORS["red"], width=px(1.4))
        self.canvas.create_oval(
            gutter - px(3), y - px(3), gutter + px(3), y + px(3),
            fill=COLORS["red"], outline="",
        )

    def _paint_empty(self) -> None:
        y = px(ROW_H) * min(4, self._end_hour - self._start_hour)
        text = (
            "这一周没有课程 · 点空白格子添加一门课"
            if self.course_only
            else "这一周没有安排 · 点空白格子可以新建"
        )
        self.canvas.create_text(
            self._width / 2, y,
            text=text,
            font=self._meta_font, fill=COLORS["text_3"],
        )

    # ---------------------------------------------------------- 文案

    def _fit(self, text: str, font_obj: tkfont.Font, max_width: float) -> str:
        text = text.strip()
        if font_obj.measure(text) <= max_width:
            return text
        while text and font_obj.measure(text + "…") > max_width:
            text = text[:-1]
        return (text + "…") if text else ""

    def _info_text(self, entry: Entry, max_width: float) -> str:
        """教室 + 老师；放不下就用短教室名，再不行只写教室/老师，最后退回备注首行。"""
        room, teacher = entry.room.strip(), entry.teacher.strip()
        candidates: list[str] = []
        if room and teacher:
            candidates.append(f"{room} · {teacher}")
            short = _short_room(room)
            if short != room:
                candidates.append(f"{short} · {teacher}")
        if room:
            candidates.append(room)
            short = _short_room(room)
            if short != room:
                candidates.append(short)
        if teacher:
            candidates.append(teacher)
        for candidate in candidates:
            if self._tiny_font.measure(candidate) <= max_width:
                return candidate
        if candidates:
            return self._fit(candidates[0], self._tiny_font, max_width)
        note = self._note_line(entry)
        return self._fit(note, self._tiny_font, max_width) if note else ""

    @staticmethod
    def _note_line(entry: Entry) -> str:
        if not entry.note:
            return ""
        for line in entry.note.splitlines():
            line = line.strip()
            if line:
                return line
        return ""

    def _clip_y(self, hour: float) -> float:
        if hour <= self._start_hour:
            return 0
        if hour >= self._end_hour:
            return self._y(self._end_hour)
        return self._y(hour)

    # ---------------------------------------------------------- 交互

    def _on_click(self, event) -> None:  # noqa: ANN001
        self._hide_tip()
        current = self.canvas.find_withtag("current")
        if current:
            for tag in self.canvas.gettags(current[0]):
                if tag.startswith("entry:"):
                    entry = self._by_id.get(tag.split(":", 1)[1])
                    if entry is not None and self.on_open:
                        self.on_open(entry)
                    return
        if not self.on_pick_slot:
            return
        gut = px(GUTTER)
        if event.x < gut or event.y < 0:
            return
        column = int((event.x - gut) // self._col_width())
        column = max(0, min(6, column))
        hour = self._start_hour + int(event.y // px(ROW_H))
        hour = max(self._start_hour, min(self._end_hour - 1, hour))
        day = self.anchor + timedelta(days=column)
        start = f"{hour:02d}:00"
        end = f"{hour + 1:02d}:00" if hour < 23 else "23:30"
        self.on_pick_slot(day, start, end)

    def _on_motion(self, event) -> None:  # noqa: ANN001
        hovering = bool(self.canvas.find_withtag("current"))
        cursor = "hand2" if hovering else "arrow"
        if self.canvas.cget("cursor") != cursor:
            self.canvas.configure(cursor=cursor)
        self._schedule_tip(self._entry_at(event))

    def _entry_at(self, event) -> Entry | None:  # noqa: ANN001
        current = self.canvas.find_withtag("current")
        if not current:
            return None
        for tag in self.canvas.gettags(current[0]):
            if tag.startswith("entry:"):
                return self._by_id.get(tag.split(":", 1)[1])
        return None

    # -- 悬停提示 -----------------------------------------------------

    def _schedule_tip(self, entry: Entry | None) -> None:
        target = entry.id if entry is not None else None
        if target == self._tip_entry:
            return
        if self._tip_job:
            try:
                self.after_cancel(self._tip_job)
            except tk.TclError:
                pass
            self._tip_job = None
        self._hide_tip()
        if entry is None:
            return
        self._tip_entry = target
        self._tip_job = self.after(320, lambda: self._show_tip(entry))

    def _show_tip(self, entry: Entry) -> None:
        self._tip_job = None
        if not self.winfo_exists():
            return
        self._hide_tip()
        lines = [entry.title or "（未命名）"]
        when = f"{entry.start_time:%H:%M}" + (
            "" if entry.point else f" – {entry.end_time:%H:%M}"
        )
        lines.append(" · ".join(part for part in (when, entry.period.strip()) if part))
        people = " · ".join(
            part for part in (entry.room.strip(), entry.teacher.strip()) if part
        )
        if people:
            lines.append(people)
        if entry.note.strip():
            first = entry.note.strip().splitlines()[0].strip()
            if first and first not in lines:
                lines.append(first if len(first) <= 40 else first[:40] + "…")

        tip = tk.Toplevel(self)
        tip.withdraw()
        tip.overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(
            tip,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border_strong"],
        )
        frame.pack(fill="both", expand=True)
        for index, line in enumerate(lines):
            tk.Label(
                frame,
                text=line,
                bg=COLORS["surface"],
                fg=COLORS["text"] if index == 0 else COLORS["text_2"],
                font=font(9, "bold") if index == 0 else font(8),
                anchor="w",
                justify="left",
            ).pack(
                fill="x",
                padx=px(10),
                pady=(px(6) if index == 0 else px(1), px(6) if index == len(lines) - 1 else 0),
            )
        tip.update_idletasks()
        width, height = tip.winfo_reqwidth(), tip.winfo_reqheight()
        x = min(self.winfo_pointerx() + px(14), self.winfo_screenwidth() - width - px(8))
        y = min(self.winfo_pointery() + px(18), self.winfo_screenheight() - height - px(8))
        tip.geometry(f"+{max(px(4), x)}+{max(px(4), y)}")
        tip.deiconify()
        self._tip = tip
        self._tip_entry = entry.id

    def _hide_tip(self) -> None:
        if self._tip_job:
            try:
                self.after_cancel(self._tip_job)
            except tk.TclError:
                pass
            self._tip_job = None
        self._tip_entry = None
        tip, self._tip = self._tip, None
        if tip is not None:
            try:
                tip.destroy()
            except tk.TclError:
                pass

    def _shift(self, delta: int) -> None:
        if self.on_shift:
            self.on_shift(delta)

    def _go_today(self) -> None:
        if self.on_today:
            self.on_today()
