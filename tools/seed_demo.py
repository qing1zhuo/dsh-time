"""生成一组演示数据，方便查看界面效果（仅用于开发预览）。"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.model import Entry  # noqa: E402
from app.paths import STORE_PATH  # noqa: E402
from app.store import Settings, Store  # noqa: E402


def build(popup: bool = False) -> Store:
    today = date.today()
    now = datetime.now()
    rows = [
        Entry(title="晨会同步", kind="once", date_str=today.isoformat(), start="08:30", end="09:00"),
        Entry(
            title="写周报",
            note="把本周的进度和下周计划整理进表格",
            kind="once",
            date_str=today.isoformat(),
            start=(now + timedelta(minutes=25)).strftime("%H:%M"),
            end=(now + timedelta(minutes=55)).strftime("%H:%M"),
            advance_minutes=10,
        ),
        Entry(
            title="健身",
            note="带好运动鞋和水",
            kind="weekly",
            weekdays=[1, 3, 5],
            start="19:00",
            end="20:00",
            advance_minutes=30,
        ),
        Entry(title="站会", kind="weekly", weekdays=[1, 2, 3, 4, 5], start="08:30", end="09:00", enabled=False),
        Entry(
            title="体检",
            kind="once",
            date_str=(today + timedelta(days=1)).isoformat(),
            start="14:00",
            end="15:30",
            advance_minutes=60,
        ),
        Entry(title="打扫房间", kind="weekly", weekdays=[6, 7], start="10:00", end="11:00"),
    ]
    if popup:
        rows.insert(
            0,
            Entry(
                title="项目复盘会",
                note="会议室 B，记得带上上周的数据",
                kind="once",
                date_str=today.isoformat(),
                start=(now - timedelta(minutes=1)).strftime("%H:%M"),
                end=(now + timedelta(minutes=40)).strftime("%H:%M"),
            ),
        )
    store = Store(STORE_PATH)
    store.entries = rows
    store.settings = Settings(first_run=False, autostart_choice="on")
    store.save()
    return store


if __name__ == "__main__":
    build(popup="--popup" in sys.argv)
    print(f"demo data -> {STORE_PATH}")
