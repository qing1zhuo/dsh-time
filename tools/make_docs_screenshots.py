"""生成 README 里的界面截图（使用虚构的示例课程，不涉及任何真实课表）。

用法：python tools/make_docs_screenshots.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import model, theme  # noqa: E402
from app.model import Entry, monday_of  # noqa: E402
from app.store import Settings  # noqa: E402
from app.ui_main import MainWindow  # noqa: E402
from tools.capture_window import capture_hwnd  # noqa: E402
from tools.ui_preview import FakeApp  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs"


def demo_entries(today: date) -> list[Entry]:
    """一组虚构的课程 + 两条普通日程，用来演示界面。"""
    term_week = 11
    term_start = monday_of(today - timedelta(weeks=term_week - 1))

    def course(title, subject, teacher, room, period, weekdays, start, end, color_hint=""):
        return Entry(
            title=title,
            kind="weekly",
            weekdays=weekdays,
            start=start,
            end=end,
            weeks_from=1,
            weeks_to=16,
            term_limited=True,
            subject=subject,
            teacher=teacher,
            room=room,
            period=period,
            is_course=True,
        )

    return [
        course("高等数学", "高等数学", "张明", "教学楼A101", "1-2节", [1, 3], "08:00", "09:40"),
        course("大学英语听说", "大学英语", "李华", "外语楼B203", "3-4节", [2, 4], "10:10", "11:50"),
        course("程序设计基础", "程序设计", "王强", "计算机楼C305", "5-6节", [1], "14:20", "16:00"),
        course("数据结构", "数据结构", "赵敏", "计算机楼C305", "3-4节", [3], "10:10", "11:50"),
        course("大学物理", "大学物理", "陈晨", "理科楼D402", "5-6节", [2], "14:20", "16:00"),
        course("体育", "体育", "刘洋", "体育馆", "7-8节", [5], "15:00", "16:40"),
        course("大学物理实验", "物理实验", "周涛", "实验中心E101", "3-4节", [5], "10:10", "11:50"),
        course("音乐鉴赏", "音乐鉴赏", "吴芳", "艺术楼201", "7-8节", [4], "15:00", "16:40"),
        course("形势与政策", "形势与政策", "郑伟", "教学楼A203", "1-2节", [5], "08:00", "09:40"),
        course("学业辅导", "学业辅导", "辅导员", "学生中心", "7-8节", [7], "15:00", "16:40"),
        Entry(
            title="交实验报告",
            note="打印后交到实验中心前台",
            kind="once",
            date_str=(today + timedelta(days=2)).isoformat(),
            start="17:00",
            end="17:30",
            is_course=False,
        ),
        Entry(
            title="吃药",
            note="饭后半小时",
            kind="weekly",
            weekdays=[1, 2, 3, 4, 5, 6, 7],
            start="21:00",
            point=True,
            is_course=False,
        ),
    ], term_start


def main() -> int:
    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    theme.setup_ttk(root)

    today = date.today()
    entries, term_start = demo_entries(today)
    model.set_term(term_start, 16)

    app = FakeApp(root)
    app.settings = Settings(
        first_run=False,
        autostart_choice="on",
        term_start=term_start.isoformat(),
        term_weeks=16,
    )
    app.store.entries = entries

    win = MainWindow(app, show_now=True)
    win.refresh()
    for _ in range(4):
        root.update_idletasks()
        root.update()

    DOCS.mkdir(parents=True, exist_ok=True)
    print("main:", capture_hwnd(win.winfo_id(), DOCS / "screenshot-main.png"))

    win.set_filter("grid")
    for _ in range(6):
        root.update_idletasks()
        root.update()
    print("grid:", capture_hwnd(win.winfo_id(), DOCS / "screenshot-grid.png"))
    if getattr(win, "_grid_widget", None) is not None:
        widget = win._grid_widget
        root.update_idletasks()
        head_png = DOCS / "_grid-head.png"
        body_png = DOCS / "_grid-body.png"
        capture_hwnd(widget.head_canvas.winfo_id(), head_png)
        capture_hwnd(widget.canvas.winfo_id(), body_png)
        try:
            from PIL import Image

            with Image.open(head_png) as head, Image.open(body_png) as body:
                canvas = Image.new(
                    "RGB",
                    (max(head.width, body.width), head.height + body.height),
                    (243, 245, 250),
                )
                canvas.paste(head, (0, 0))
                canvas.paste(body, (0, head.height))
                canvas.save(DOCS / "screenshot-grid-detail.png")
        finally:
            head_png.unlink(missing_ok=True)
            body_png.unlink(missing_ok=True)
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
