"""判断「此刻该提醒哪些日程」。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from .model import Entry

DEFAULT_GRACE_MINUTES = 30
MAX_LATE_MINUTES = 24 * 60


@dataclass
class DueReminder:
    """一条已经到点的提醒。"""

    entry: Entry
    start: datetime
    end: datetime
    key: str
    late_minutes: int = 0
    advanced: bool = False
    snoozed: bool = False

    @property
    def heading(self) -> str:
        if self.snoozed:
            return "稍后提醒"
        if self.advanced and self.late_minutes <= 0:
            return "马上开始"
        if self.late_minutes >= 1:
            return f"已开始 {self.late_minutes} 分钟"
        return "现在开始"


def collect_due(
    entries: Iterable[Entry],
    now: datetime | None = None,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
) -> list[DueReminder]:
    """返回当前需要弹出提醒的日程（同一个日程每次发生只提醒一次）。"""
    now = now or datetime.now()
    grace = max(1, int(grace_minutes))
    due: list[DueReminder] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        if not entry.enabled:
            continue
        advance = max(0, int(entry.advance_minutes))
        for offset in (0, -1):  # 昨天用于处理跨夜日程
            day = (now + timedelta(days=offset)).date()
            occurrence = entry.occurrence(day)
            if occurrence is None:
                continue
            start_dt, end_dt = occurrence
            fire_at = start_dt - timedelta(minutes=advance)
            if now < fire_at:
                continue
            key = Entry.fire_key(day, entry.start_time)
            if entry.has_fired(key) or entry.has_done(key):
                continue
            deadline = max(end_dt, fire_at + timedelta(minutes=grace))
            if now > deadline:
                continue
            late = int((now - start_dt).total_seconds() // 60)
            if late > MAX_LATE_MINUTES:
                continue
            dedupe_key = (entry.id, key)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            due.append(
                DueReminder(
                    entry=entry,
                    start=start_dt,
                    end=end_dt,
                    key=key,
                    late_minutes=max(0, late),
                    advanced=advance > 0,
                )
            )

    due.sort(key=lambda item: (item.start, item.entry.title))
    return due


def next_reminder(
    entries: Iterable[Entry], now: datetime | None = None
) -> tuple[Entry, datetime] | None:
    """下一次会响的提醒（用于状态栏和托盘提示）。"""
    now = now or datetime.now()
    best: tuple[Entry, datetime] | None = None
    for entry in entries:
        if not entry.enabled:
            continue
        fire_at = entry.next_fire_time(now)
        if fire_at is None or fire_at < now:
            continue
        if best is None or fire_at < best[1]:
            best = (entry, fire_at)
    return best


def group_due(dues: Iterable[DueReminder]) -> list[list[DueReminder]]:
    """把开始时间相同的提醒合并成一组，界面上只用弹一张卡片。"""
    groups: dict[datetime, list[DueReminder]] = {}
    for item in dues:
        groups.setdefault(item.start, []).append(item)
    return [groups[key] for key in sorted(groups)]
