"""界面冒烟测试：不开主循环，直接驱动对话框完成一次保存。

用法：python tools/smoke_ui.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.model import KIND_WEEKLY  # noqa: E402
from app.store import Settings  # noqa: E402
from app.ui_entry_dialog import EntryDialog  # noqa: E402
from app.widgets import CalendarPopup  # noqa: E402
from tools.ui_preview import FakeApp  # noqa: E402

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  ok   {message}")
    else:
        failures.append(message)
        print(f"  FAIL {message}")


def main() -> int:
    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    theme.setup_ttk(root)
    app = FakeApp(root)
    app.settings = Settings()

    print("新建每周日程并保存：")
    dialog = EntryDialog(app, None)
    root.update_idletasks()
    dialog.title_var.set("每周复盘")
    dialog._apply_kind(KIND_WEEKLY)
    # 切换成每周重复时默认勾选今天，先全部取消再选周三、周五
    for day in list(dialog._weekdays):
        dialog._toggle_weekday(day)
    dialog._toggle_weekday(3)
    dialog._toggle_weekday(5)
    dialog.start_var.set("18:30")
    dialog.end_var.set("19:45")
    dialog.advance_var.set("提前 15 分钟")
    dialog.note_text.insert("1.0", "带上笔记本")
    dialog._save()
    root.update_idletasks()

    check(len(app.saved) == 1, "保存了一条日程")
    if app.saved:
        entry = app.saved[0]
        check(entry.title == "每周复盘", "标题正确")
        check(entry.kind == KIND_WEEKLY, "类型为每周重复")
        check(entry.weekdays == [3, 5], "星期为周三、周五")
        check(entry.start == "18:30" and entry.end == "19:45", "时间正确")
        check(entry.advance_minutes == 15, "提前 15 分钟")
        check(entry.note == "带上笔记本", "备注正确")

    print("空标题应当被拦下：")
    dialog2 = EntryDialog(app, None)
    root.update_idletasks()
    dialog2.title_var.set("")
    dialog2._save()
    root.update_idletasks()
    check(len(app.saved) == 1, "没有保存空标题的日程")
    check("请填写要做什么" in dialog2.error_label.cget("text"), "给出了错误提示")
    dialog2.close()

    print("选择日期与跨夜提示：")
    dialog3 = EntryDialog(app, None)
    root.update_idletasks()
    tomorrow = date.today() + timedelta(days=1)
    dialog3._set_date(tomorrow)
    check(dialog3._date == tomorrow, "日期被更新为明天")
    check("11 月 19 日" in dialog3.date_button._text, "日期按钮文字已刷新")
    dialog3.start_var.set("22:00")
    dialog3.end_var.set("01:30")
    check(dialog3._collect().duration_minutes == 210, "跨夜时长计算正确")
    dialog3.close()

    print("时间点提醒（只提醒一次，可完成）：")
    dialog4 = EntryDialog(app, None)
    root.update_idletasks()
    dialog4._apply_point(True)
    root.update_idletasks()
    check(dialog4.time_sep.winfo_manager() == "", "时间点模式下隐藏了结束时间")
    dialog4.title_var.set("吃药")
    dialog4.start_var.set("15:00")
    dialog4._save()
    root.update_idletasks()
    check(len(app.saved) == 2, "保存了第二条日程")
    point_entry = app.saved[-1]
    check(point_entry.point, "类型标记为时间点提醒")
    check(point_entry.duration_minutes == 0, "没有时长")
    check(point_entry.end == point_entry.start, "结束时间与开始时间一致")

    print("日历表头与日期列对齐：")
    calendar_popup = CalendarPopup(root, date.today(), lambda picked: None)
    root.update_idletasks()
    root.update()
    cells = calendar_popup._grid.winfo_children()  # noqa: SLF001
    headers = cells[:7]
    first_week = cells[7:14]
    for index, (header, day_cell) in enumerate(zip(headers, first_week)):
        header_center = header.winfo_x() + header.winfo_width() / 2
        day_center = day_cell.winfo_x() + day_cell.winfo_width() / 2
        check(abs(header_center - day_center) <= 1.0, f"第 {index + 1} 列上下居中对齐")
    calendar_popup.close()

    root.destroy()
    print()
    if failures:
        print(f"失败 {len(failures)} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
