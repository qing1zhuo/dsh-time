"""日程数据模型：一次性日程、每周重复日程、触发时间计算。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

WEEKDAY_CN = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
}
WEEKDAY_SHORT = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}
WEEKDAY_ORDER = (1, 2, 3, 4, 5, 6, 7)

KIND_ONCE = "once"
KIND_WEEKLY = "weekly"

# 每周日程的「生效周次」：默认跟随教学周，也可以只上单周或双周。
PARITY_ALL = "all"
PARITY_ODD = "odd"
PARITY_EVEN = "even"
PARITY_LABELS = {PARITY_ALL: "每周", PARITY_ODD: "单周", PARITY_EVEN: "双周"}
DEFAULT_TERM_WEEKS = 18


# ---------------------------------------------------------------- 教学周


def monday_of(day: date) -> date:
    """所在周的周一。"""
    return day - timedelta(days=day.isoweekday() - 1)


@dataclass
class Term:
    """学期上下文：第 1 周的周一 + 学期总周数。

    是一个进程内共享的轻量上下文（和 theme.SCALE 类似），由 Application 在
    启动和修改设置时写入；模型里的 occurs_on() 会读它来判断「这一周上不上课」。
    """

    start: date | None = None
    weeks: int = DEFAULT_TERM_WEEKS

    @property
    def active(self) -> bool:
        return self.start is not None

    def week_of(self, day: date) -> int | None:
        """day 是第几教学周；开学前返回 None。"""
        if self.start is None:
            return None
        offset = (day - self.start).days
        if offset < 0:
            return None
        return offset // 7 + 1

    def week_start(self, week: int) -> date:
        assert self.start is not None
        return self.start + timedelta(weeks=max(0, int(week) - 1))

    def is_teaching_week(self, week: int | None) -> bool:
        return week is not None and 1 <= week <= self.weeks

    def clamp_week(self, week: int) -> int:
        return max(1, min(int(week), max(1, self.weeks)))


TERM = Term()


def set_term(start: date | None = None, weeks: int | None = None) -> Term:
    """更新当前教学周上下文；start 会归一化到所在周的周一。"""
    global TERM
    if weeks is not None:
        TERM.weeks = max(1, min(52, int(weeks)))
    TERM.start = monday_of(start) if start else None
    return TERM


# ---------------------------------------------------------------- 时间工具


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_hhmm(value: str | time) -> time:
    """解析 "HH:MM"（兼容中文冒号、HH:MM:SS）。"""
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    text = str(value).strip().replace("：", ":").replace(".", ":")
    for fmt in ("%H:%M", "%H:%M:%S", "%H%M"):
        try:
            return datetime.strptime(text, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    raise ValueError(f"时间格式不正确：{value!r}（应为 09:30 这样的写法）")


def fmt_hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    return datetime.strptime(text, "%Y-%m-%d").date()


def minutes_of_day(value: time) -> int:
    return value.hour * 60 + value.minute


def humanize_delta(seconds: float) -> str:
    """把秒数变成「1 小时 23 分钟后」这样的说法。"""
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    minutes = seconds // 60
    if minutes < 1:
        return "不到 1 分钟后"
    if minutes < 60:
        return f"{minutes} 分钟后"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        if minutes == 0:
            return f"{hours} 小时后"
        return f"{hours} 小时 {minutes} 分钟后"
    days, hours = divmod(hours, 24)
    if hours == 0:
        return f"{days} 天后"
    return f"{days} 天 {hours} 小时后"


def describe_date_cn(day: date, today: date | None = None) -> str:
    today = today or date.today()
    delta = (day - today).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == 2:
        return "后天"
    if delta == -1:
        return "昨天"
    return f"{day.month} 月 {day.day} 日"


# ---------------------------------------------------------------- 课程标签
#
# 以前教室和老师只能写在备注里（「公共教学楼D203 李绿周」）。这里做一个
# 保守的拆分，给「从备注填入」和批量整理用；猜不出来就返回空字符串。

ROOM_HINTS = (
    "楼", "室", "中心", "馆", "厅", "场", "校园", "实验",
    "一教", "二教", "三教", "四教", "五教", "六教",
)
_NAME_RE = re.compile(r"^[\u4e00-\u9fff]{2,4}$")
_ROOM_CODE_RE = re.compile(r"[A-Za-z]?\d{2,4}")


def _looks_like_room(text: str) -> bool:
    text = (text or "").strip()
    if not text or len(text) > 28:
        return False
    return any(hint in text for hint in ROOM_HINTS) or bool(_ROOM_CODE_RE.search(text))


def split_course_note(note: str) -> tuple[str, str]:
    """从备注里猜 (教室, 老师)。

    支持「公共教学楼D203 李绿周」「实验中心D501 李博洋」这种一行写法，
    也支持「南校园二教」这种只有教室的一行。宁可不填，也不乱猜。
    """
    lines = [line.strip() for line in (note or "").splitlines() if line.strip()]
    if not lines:
        return "", ""
    room = teacher = ""
    first = lines[0].strip(" ，,。")
    parts = first.split()
    if len(parts) >= 2:
        head = " ".join(parts[:-1]).strip(" ，,。")
        tail = parts[-1].strip(" ，,。")
        if tail.endswith("老师"):
            tail = tail[:-2]
        if _looks_like_room(head) and _NAME_RE.match(tail):
            room, teacher = head, tail
        elif _looks_like_room(first):
            room = first
    elif _looks_like_room(first):
        room = first
    if not teacher:
        for line in lines:
            for token in line.replace("，", " ").replace(",", " ").split():
                candidate = token.strip(" ，,。")
                if candidate.endswith("老师") and _NAME_RE.match(candidate[:-2]):
                    teacher = candidate[:-2]
                    break
            if teacher:
                break
    return room, teacher


# ---------------------------------------------------------------- 日程


@dataclass
class Entry:
    """一条日程。

    kind = "once"   时用 date_str（YYYY-MM-DD）指定某一天；
    kind = "weekly" 时用 weekdays（1=周一 … 7=周日，可多选）表示每周重复。
    start / end 为 "HH:MM"；end 早于 start 表示跨夜（例如 22:00–01:00）。
    """

    title: str = ""
    note: str = ""
    kind: str = KIND_ONCE
    date_str: str = ""
    weekdays: list[int] = field(default_factory=list)
    start: str = "09:00"
    end: str = "10:00"
    advance_minutes: int = 0
    enabled: bool = True
    # 每周日程的生效范围：第 weeks_from 周到第 weeks_to 周（0 = 到学期末），
    # parity 可选 all / odd / even；term_limited=False 表示不管教学周、一直重复。
    weeks_from: int = 1
    weeks_to: int = 0
    parity: str = PARITY_ALL
    term_limited: bool = True
    # 课表标签（都可选）：科目、老师、教室、课次（例如「1-2节」）
    subject: str = ""
    teacher: str = ""
    room: str = ""
    period: str = ""
    # 是否计入课表：每周安排默认计入，一次性默认不计入（None 表示按类型推导）
    is_course: bool | None = None
    fired: dict[str, str] = field(default_factory=dict)
    point: bool = False
    done: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        # 时间点提醒没有结束时间，统一成开始时间，避免数据里出现无意义的 end
        if self.point and self.end != self.start:
            self.end = self.start
        # 旧数据没有 is_course 字段时，按「每周 = 课程、一次性 = 不是课程」处理
        if self.is_course is None:
            self.is_course = self.kind == KIND_WEEKLY

    # -- 基础属性 -----------------------------------------------------

    @property
    def start_time(self) -> time:
        return parse_hhmm(self.start)

    @property
    def end_time(self) -> time:
        return parse_hhmm(self.end)

    @property
    def day(self) -> date | None:
        if self.kind != KIND_ONCE or not self.date_str:
            return None
        try:
            return parse_date(self.date_str)
        except ValueError:
            return None

    @property
    def duration_minutes(self) -> int:
        if self.point:
            return 0
        delta = minutes_of_day(self.end_time) - minutes_of_day(self.start_time)
        if delta <= 0:
            delta += 24 * 60
        return delta

    @property
    def is_weekly(self) -> bool:
        return self.kind == KIND_WEEKLY

    # -- 文案 ---------------------------------------------------------

    def time_label(self) -> str:
        if self.point:
            return f"{fmt_hhmm(self.start_time)} 提醒"
        suffix = "（次日）" if self.duration_minutes >= 24 * 60 or minutes_of_day(self.end_time) <= minutes_of_day(self.start_time) else ""
        return f"{fmt_hhmm(self.start_time)} – {fmt_hhmm(self.end_time)}{suffix}"

    def weekday_label(self) -> str:
        days = [d for d in WEEKDAY_ORDER if d in set(self.weekdays)]
        if not days:
            return "每周（未选择星期）"
        if days == [1, 2, 3, 4, 5]:
            return "每周一至周五"
        if days == [6, 7]:
            return "每周末"
        if days == list(WEEKDAY_ORDER):
            return "每天"
        return "每周" + "、".join(WEEKDAY_SHORT[d] for d in days)

    def week_span_label(self) -> str:
        """「第 1–16 周 · 单周」这样的说明。"""
        if not self.term_limited:
            return "不限周次"
        start_week = max(1, int(self.weeks_from))
        end_week = self.weeks_to or TERM.weeks
        if end_week <= start_week:
            text = f"第 {start_week} 周"
        else:
            text = f"第 {start_week}–{end_week} 周"
        if self.parity == PARITY_ODD:
            text += " · 单周"
        elif self.parity == PARITY_EVEN:
            text += " · 双周"
        return text

    def week_number(self, day: date) -> int | None:
        return TERM.week_of(day)

    def date_label(self) -> str:
        day = self.day
        if not day:
            return "日期未设置"
        return f"{day.month} 月 {day.day} 日 {WEEKDAY_CN[day.isoweekday()]}"

    def schedule_label(self) -> str:
        if self.kind == KIND_WEEKLY:
            return self.weekday_label()
        return self.date_label()

    def advance_label(self) -> str:
        if self.advance_minutes <= 0:
            return "准点提醒"
        if self.advance_minutes % 60 == 0:
            return f"提前 {self.advance_minutes // 60} 小时"
        return f"提前 {self.advance_minutes} 分钟"

    # -- 触发计算 -----------------------------------------------------

    def occurs_on(self, day: date, term: Term | None = None) -> bool:
        if self.kind == KIND_ONCE:
            return self.day == day
        if day.isoweekday() not in set(self.weekdays):
            return False
        if not self.term_limited:
            return True
        term = term or TERM
        if not term.active:
            # 还没设置学期时不做限制，保持升级前的行为
            return True
        week = term.week_of(day)
        if week is None or week > term.weeks:
            return False
        if week < max(1, self.weeks_from):
            return False
        upper = self.weeks_to or term.weeks
        if week > upper:
            return False
        if self.parity == PARITY_ODD and week % 2 == 0:
            return False
        if self.parity == PARITY_EVEN and week % 2 == 1:
            return False
        return True

    def occurrence(self, day: date) -> tuple[datetime, datetime] | None:
        """返回 (开始, 结束) 的绝对时间；当天不触发则返回 None。"""
        if not self.occurs_on(day):
            return None
        start_dt = datetime.combine(day, self.start_time)
        end_dt = start_dt + timedelta(minutes=self.duration_minutes)
        return start_dt, end_dt

    @staticmethod
    def fire_key(day: date, start: time) -> str:
        return f"{day.isoformat()}|{fmt_hhmm(start)}"

    def has_fired(self, key: str) -> bool:
        return key in self.fired

    def mark_fired(self, key: str, when: datetime | None = None) -> None:
        when = when or datetime.now()
        self.fired[key] = when.isoformat(timespec="seconds")

    def has_done(self, key: str) -> bool:
        return key in self.done

    def mark_done(self, key: str, when: datetime | None = None) -> None:
        when = when or datetime.now()
        self.done[key] = when.isoformat(timespec="seconds")

    def unmark_done(self, key: str) -> None:
        self.done.pop(key, None)

    def prune_fired(self, keep_days: int = 90, now: datetime | None = None) -> None:
        """清理旧的触发/完成记录，避免文件无限增长。"""
        now = now or datetime.now()
        cutoff = now - timedelta(days=keep_days)
        for bucket in (self.fired, self.done):
            for key in list(bucket):
                try:
                    day = parse_date(key.split("|", 1)[0])
                except (ValueError, IndexError):
                    del bucket[key]
                    continue
                if datetime.combine(day, time.min) < cutoff:
                    del bucket[key]

    def next_occurrence(
        self, now: datetime | None = None, include_done: bool = False
    ) -> tuple[datetime, datetime] | None:
        """下一次（还没结束、且没被标记完成）的发生时间。"""
        now = now or datetime.now()
        today = now.date()
        if self.kind == KIND_ONCE:
            max_days = 400
        elif self.term_limited and TERM.active:
            # 学期已经结束就不用再找了
            term_end = TERM.week_start(TERM.weeks) + timedelta(days=6)
            if today > term_end:
                return None
            # 还没开学或课程从后面几周才开始时，要往前多找几周
            lead = max(0, (TERM.start - today).days)
            max_days = min(400, lead + TERM.weeks * 7 + 7)
        else:
            max_days = 8
        for offset in range(max_days):
            day = today + timedelta(days=offset)
            occ = self.occurrence(day)
            if not occ or occ[1] < now:
                continue
            if not include_done and self.has_done(self.fire_key(day, self.start_time)):
                continue
            return occ
        return None

    def relevant_key(self, now: datetime | None = None) -> str | None:
        """界面上「这一条算哪一次」：优先今天，其次下一次。"""
        now = now or datetime.now()
        today = now.date()
        if self.kind == KIND_ONCE:
            day = self.day
            return self.fire_key(day, self.start_time) if day else None
        if self.occurs_on(today):
            return self.fire_key(today, self.start_time)
        nxt = self.next_occurrence(now)
        if nxt:
            return self.fire_key(nxt[0].date(), self.start_time)
        return None

    def can_complete(self, now: datetime | None = None) -> bool:
        """只有「时间点提醒」可以打勾完成；每周项只在当天可完成。"""
        if not self.point:
            return False
        now = now or datetime.now()
        if self.kind == KIND_ONCE:
            return self.day is not None
        return self.occurs_on(now.date())

    def next_fire_time(self, now: datetime | None = None) -> datetime | None:
        occ = self.next_occurrence(now)
        if not occ:
            return None
        return occ[0] - timedelta(minutes=max(0, self.advance_minutes))

    def sort_key(self, now: datetime | None = None) -> tuple[int, datetime]:
        nxt = self.next_occurrence(now)
        return (0, nxt[0]) if nxt else (1, datetime.max)

    # -- 校验 / 序列化 ------------------------------------------------

    def validate(self, today: date | None = None) -> list[str]:
        today = today or date.today()
        errors: list[str] = []
        if not self.title.strip():
            errors.append("请填写要做什么")
        try:
            start_t, end_t = self.start_time, self.end_time
        except ValueError as exc:
            errors.append(str(exc))
            return errors
        if not self.point and start_t == end_t:
            errors.append("结束时间不能和开始时间相同")
        if self.kind == KIND_ONCE:
            day = self.day
            if day is None:
                errors.append("请选择日期")
            elif day < today:
                errors.append("日期不能早于今天")
        else:
            if not self.weekdays:
                errors.append("请至少选择一个星期")
            if self.weeks_from < 1:
                errors.append("开始周不能小于第 1 周")
            if self.weeks_to and self.weeks_to < self.weeks_from:
                errors.append("结束周不能早于开始周")
            if TERM.active and self.weeks_from > TERM.weeks:
                errors.append(f"开始周超出了学期总周数（共 {TERM.weeks} 周）")
            if self.parity not in PARITY_LABELS:
                errors.append("周次类型不正确")
        if self.advance_minutes < 0:
            errors.append("提前提醒时间不能为负")
        return errors

    def clone(self) -> "Entry":
        return Entry.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title.strip(),
            "note": self.note.strip(),
            "subject": self.subject.strip(),
            "teacher": self.teacher.strip(),
            "room": self.room.strip(),
            "period": self.period.strip(),
            "kind": self.kind,
            "is_course": bool(self.is_course),
            "date": self.date_str,
            "weekdays": [d for d in WEEKDAY_ORDER if d in set(self.weekdays)],
            "start": fmt_hhmm(self.start_time),
            "end": fmt_hhmm(self.end_time),
            "point": bool(self.point),
            "advance_minutes": int(self.advance_minutes),
            "enabled": bool(self.enabled),
            "weeks_from": max(1, int(self.weeks_from)),
            "weeks_to": max(0, int(self.weeks_to)),
            "parity": self.parity if self.parity in PARITY_LABELS else PARITY_ALL,
            "term_limited": bool(self.term_limited),
            "fired": dict(self.fired),
            "done": dict(self.done),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Entry":
        raw = raw or {}
        weekdays = []
        for value in raw.get("weekdays") or []:
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= number <= 7 and number not in weekdays:
                weekdays.append(number)
        weekdays.sort()
        start = str(raw.get("start") or "09:00")
        parity = str(raw.get("parity") or PARITY_ALL)
        if parity not in PARITY_LABELS:
            parity = PARITY_ALL
        return cls(
            title=str(raw.get("title") or ""),
            note=str(raw.get("note") or ""),
            subject=str(raw.get("subject") or ""),
            teacher=str(raw.get("teacher") or ""),
            room=str(raw.get("room") or ""),
            period=str(raw.get("period") or ""),
            is_course=(None if "is_course" not in raw else bool(raw.get("is_course"))),
            kind=KIND_WEEKLY if raw.get("kind") == KIND_WEEKLY else KIND_ONCE,
            date_str=str(raw.get("date") or ""),
            weekdays=weekdays,
            start=start,
            end=str(raw.get("end") or start),
            point=bool(raw.get("point", False)),
            advance_minutes=max(0, int(raw.get("advance_minutes") or 0)),
            enabled=bool(raw.get("enabled", True)),
            weeks_from=max(1, _as_int(raw.get("weeks_from"), 1)),
            weeks_to=max(0, _as_int(raw.get("weeks_to"), 0)),
            parity=parity,
            term_limited=bool(raw.get("term_limited", True)),
            fired={str(k): str(v) for k, v in dict(raw.get("fired") or {}).items()},
            done={str(k): str(v) for k, v in dict(raw.get("done") or {}).items()},
            id=str(raw.get("id") or uuid.uuid4().hex[:12]),
            created_at=str(raw.get("created_at") or datetime.now().isoformat(timespec="seconds")),
        )


# ---------------------------------------------------------------- 查询辅助


def occurrences_on_day(entries: Iterable[Entry], day: date) -> list[tuple[Entry, datetime, datetime]]:
    """某一天内（含跨夜延续到当天的）所有发生项，按开始时间排序。"""
    result: list[tuple[Entry, datetime, datetime]] = []
    for entry in entries:
        for offset in (0, -1):
            occ = entry.occurrence(day + timedelta(days=offset))
            if not occ:
                continue
            start_dt, end_dt = occ
            day_start = datetime.combine(day, time.min)
            day_end = day_start + timedelta(days=1)
            if start_dt < day_end and end_dt > day_start:
                result.append((entry, start_dt, end_dt))
    result.sort(key=lambda item: item[1])
    return result


def next_upcoming(entries: Iterable[Entry], now: datetime | None = None) -> list[tuple[Entry, datetime, datetime, datetime]]:
    """所有仍未结束的日程，按「下次提醒时间」升序。

    返回 (entry, 提醒时间, 开始, 结束)。
    """
    now = now or datetime.now()
    rows = []
    for entry in entries:
        if not entry.enabled:
            continue
        occ = entry.next_occurrence(now)
        if not occ:
            continue
        start_dt, end_dt = occ
        fire_at = start_dt - timedelta(minutes=max(0, entry.advance_minutes))
        rows.append((entry, fire_at, start_dt, end_dt))
    rows.sort(key=lambda row: row[1])
    return rows
