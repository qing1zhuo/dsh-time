"""界面冒烟测试：不开主循环，直接驱动对话框完成一次保存。

用法：python tools/smoke_ui.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import model, theme  # noqa: E402
from app.model import KIND_WEEKLY, Entry  # noqa: E402
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
    dialog.subject_var.set("离散数学")
    dialog.teacher_var.set("李绿周")
    dialog.room_var.set("公共教学楼D203")
    dialog.period_var.set("1-2节")
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
        check(entry.subject == "离散数学", "科目标签保存")
        check(entry.teacher == "李绿周", "老师标签保存")
        check(entry.room == "公共教学楼D203", "教室标签保存")
        check(entry.period == "1-2节", "课次标签保存")
        check(entry.weeks_from == 1 and entry.weeks_to == 0, "默认覆盖整个学期")
        check(entry.parity == "all" and entry.term_limited, "默认每周、按教学周")
        check(entry.is_course, "每周日程默认计入课表")

    print("计入课表开关：")
    dialog_course = EntryDialog(app, None)
    root.update_idletasks()
    check(dialog_course._is_course is False, "一次性默认不计入课表")
    dialog_course._apply_kind(KIND_WEEKLY)
    check(dialog_course._is_course is True, "新建每周默认计入课表")
    dialog_course.title_var.set("每周打扫")
    dialog_course.start_var.set("20:00")
    dialog_course.end_var.set("20:30")
    dialog_course.course_toggle.set_value(False, notify=True)
    check(dialog_course._is_course is False, "开关关掉后不再计入")
    dialog_course._save()
    root.update_idletasks()
    check(app.saved[-1].is_course is False, "保存为不计入课表")

    print("从备注填入教室和老师：")
    dialog_note = EntryDialog(app, None)
    root.update_idletasks()
    dialog_note.note_text.insert("1.0", "实验中心D501 李博洋")
    dialog_note._extract_from_note()
    check(dialog_note.room_var.get() == "实验中心D501", "从备注识别出教室")
    check(dialog_note.teacher_var.get() == "李博洋", "从备注识别出老师")
    check("已填入" in dialog_note.error_label.cget("text"), "给出了填入提示")
    dialog_note.close()

    print("从课表空格子新建（预填星期和时间）：")
    target_day = date.today() + timedelta(days=2)
    template = Entry(
        kind=KIND_WEEKLY,
        date_str=target_day.isoformat(),
        weekdays=[target_day.isoweekday()],
        start="13:00",
        end="14:00",
    )
    dialog_t = EntryDialog(app, None, template=template)
    root.update_idletasks()
    check(dialog_t._kind == KIND_WEEKLY, "默认新建每周课程")
    check(dialog_t._weekdays == {target_day.isoweekday()}, "星期已预填")
    check(dialog_t._date == target_day, "切回一次性时日期已预填")
    check(dialog_t.start_var.get() == "13:00", "开始时间已预填")
    check(dialog_t.end_var.get() == "14:00", "结束时间已预填")
    check(dialog_t.title_var.get() == "", "标题留空")
    dialog_t.close()

    print("教学周与单双周：")
    model.set_term(date.today() - timedelta(weeks=10), 16)
    dialog_term = EntryDialog(app, None)
    root.update_idletasks()
    dialog_term.title_var.set("单周实验")
    dialog_term._apply_kind(KIND_WEEKLY)
    for day in list(dialog_term._weekdays):
        dialog_term._toggle_weekday(day)
    dialog_term._toggle_weekday(3)
    dialog_term.start_var.set("14:00")
    dialog_term.end_var.set("15:00")
    check(dialog_term._term_limited, "默认勾选「按教学周」")
    check("第 11 周" in dialog_term.term_hint.cget("text"), "提示里显示了当前教学周")
    dialog_term.weeks_from_var.set("3")
    dialog_term.weeks_to_var.set("9")
    dialog_term._read_weeks()
    dialog_term._set_parity("odd")
    dialog_term._save()
    root.update_idletasks()
    term_entry = app.saved[-1]
    check(term_entry.weeks_from == 3 and term_entry.weeks_to == 9, "周次范围保存为第 3–9 周")
    check(term_entry.parity == "odd", "保存为单周")
    check(term_entry.term_limited, "保存按教学周限制")

    print("关掉「按教学周」：")
    dialog_free = EntryDialog(app, None)
    root.update_idletasks()
    dialog_free.title_var.set("全年晨跑")
    dialog_free._apply_kind(KIND_WEEKLY)
    dialog_free._toggle_term_limited()
    dialog_free.start_var.set("07:00")
    dialog_free.end_var.set("07:40")
    check("不管教学周" in dialog_free.term_hint.cget("text"), "提示说明了关闭后的效果")
    dialog_free._save()
    root.update_idletasks()
    free_entry = app.saved[-1]
    check(not free_entry.term_limited, "保存为不受教学周限制")
    model.set_term(None)

    print("空标题应当被拦下：")
    saved_before = len(app.saved)
    dialog2 = EntryDialog(app, None)
    root.update_idletasks()
    dialog2.title_var.set("")
    dialog2._save()
    root.update_idletasks()
    check(len(app.saved) == saved_before, "没有保存空标题的日程")
    check("请填写要做什么" in dialog2.error_label.cget("text"), "给出了错误提示")
    dialog2.close()

    print("选择日期与跨夜提示：")
    dialog3 = EntryDialog(app, None)
    root.update_idletasks()
    tomorrow = date.today() + timedelta(days=1)
    dialog3._set_date(tomorrow)
    check(dialog3._date == tomorrow, "日期被更新为明天")
    check(f"{tomorrow.month} 月 {tomorrow.day} 日" in dialog3.date_button._text, "日期按钮文字已刷新")
    dialog3.start_var.set("22:00")
    dialog3.end_var.set("01:30")
    check(dialog3._collect().duration_minutes == 210, "跨夜时长计算正确")
    dialog3.close()

    print("时间点提醒（只提醒一次，可完成）：")
    saved_before = len(app.saved)
    dialog4 = EntryDialog(app, None)
    root.update_idletasks()
    dialog4._apply_point(True)
    root.update_idletasks()
    check(dialog4.time_sep.winfo_manager() == "", "时间点模式下隐藏了结束时间")
    dialog4.title_var.set("吃药")
    dialog4.start_var.set("15:00")
    dialog4._save()
    root.update_idletasks()
    check(len(app.saved) == saved_before + 1, "保存了第二条日程")
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
