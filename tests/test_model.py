"""核心逻辑单元测试（不依赖图形界面）。

运行：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.model import (  # noqa: E402
    DEFAULT_TERM_WEEKS,
    PARITY_EVEN,
    PARITY_ODD,
    TERM,
    Entry,
    fmt_hhmm,
    humanize_delta,
    monday_of,
    next_upcoming,
    occurrences_on_day,
    parse_date,
    parse_hhmm,
    set_term,
    split_course_note,
)
from app.scheduler import collect_due, group_due, next_reminder  # noqa: E402
from app.store import Settings, Store  # noqa: E402


class TimeParsingTests(unittest.TestCase):
    def test_parse_variants(self):
        self.assertEqual(parse_hhmm("09:30"), time(9, 30))
        self.assertEqual(parse_hhmm("9：5"), time(9, 5))
        self.assertEqual(parse_hhmm("23:00:00"), time(23, 0))
        self.assertEqual(parse_hhmm(time(7, 15)), time(7, 15))

    def test_parse_invalid(self):
        with self.assertRaises(ValueError):
            parse_hhmm("25:99")
        with self.assertRaises(ValueError):
            parse_hhmm("晚上八点")

    def test_parse_date(self):
        self.assertEqual(parse_date("2026年11月20日"), date(2026, 11, 20))
        self.assertEqual(parse_date("2026/11/20"), date(2026, 11, 20))

    def test_fmt(self):
        self.assertEqual(fmt_hhmm(time(7, 5)), "07:05")

    def test_humanize(self):
        self.assertEqual(humanize_delta(30), "不到 1 分钟后")
        self.assertEqual(humanize_delta(5 * 60), "5 分钟后")
        self.assertEqual(humanize_delta(3600 + 23 * 60), "1 小时 23 分钟后")
        self.assertEqual(humanize_delta(2 * 86400), "2 天后")


class OccurrenceTests(unittest.TestCase):
    def make_once(self, **kwargs):
        base = dict(title="交报告", kind="once", date_str="2026-11-18", start="09:00", end="10:30")
        base.update(kwargs)
        return Entry(**base)

    def test_once_occurrence(self):
        entry = self.make_once()
        start, end = entry.occurrence(date(2026, 11, 18))
        self.assertEqual(start, datetime(2026, 11, 18, 9, 0))
        self.assertEqual(end, datetime(2026, 11, 18, 10, 30))
        self.assertIsNone(entry.occurrence(date(2026, 11, 19)))

    def test_overnight(self):
        entry = self.make_once(start="22:00", end="01:30")
        self.assertEqual(entry.duration_minutes, 210)
        start, end = entry.occurrence(date(2026, 11, 18))
        self.assertEqual(end, datetime(2026, 11, 19, 1, 30))
        self.assertIn("次日", entry.time_label())

    def test_weekly_multiple_days(self):
        entry = Entry(title="健身", kind="weekly", weekdays=[1, 3, 5], start="19:00", end="20:00")
        self.assertTrue(entry.occurs_on(date(2026, 11, 18)))  # 周三
        self.assertFalse(entry.occurs_on(date(2026, 11, 19)))  # 周四
        self.assertEqual(entry.weekday_label(), "每周一、三、五")

    def test_weekday_labels(self):
        weekdays = Entry(kind="weekly", weekdays=[1, 2, 3, 4, 5])
        self.assertEqual(weekdays.weekday_label(), "每周一至周五")
        weekend = Entry(kind="weekly", weekdays=[6, 7])
        self.assertEqual(weekend.weekday_label(), "每周末")
        everyday = Entry(kind="weekly", weekdays=[1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(everyday.weekday_label(), "每天")

    def test_next_occurrence_weekly_rollover(self):
        entry = Entry(title="周会", kind="weekly", weekdays=[1], start="10:00", end="11:00")
        now = datetime(2026, 11, 18, 12, 0)  # 周三中午
        start, _ = entry.next_occurrence(now)
        self.assertEqual(start, datetime(2026, 11, 23, 10, 0))

    def test_next_fire_time_with_advance(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00", advance_minutes=15)
        fire = entry.next_fire_time(datetime(2026, 11, 18, 9, 0))
        self.assertEqual(fire, datetime(2026, 11, 18, 14, 45))

    def test_duration_zero_end_equals_start(self):
        entry = Entry(start="09:00", end="09:00")
        self.assertEqual(entry.duration_minutes, 24 * 60)

    def test_occurrences_on_day_includes_overnight(self):
        night = Entry(title="夜班", kind="weekly", weekdays=[2], start="22:00", end="02:00")
        rows = occurrences_on_day([night], date(2026, 11, 18))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], datetime(2026, 11, 17, 22, 0))

    def test_next_upcoming_sorted(self):
        a = Entry(title="B", kind="once", date_str="2026-11-19", start="09:00", end="10:00")
        b = Entry(title="A", kind="once", date_str="2026-11-18", start="18:00", end="19:00")
        now = datetime(2026, 11, 18, 12, 0)
        rows = next_upcoming([a, b], now)
        self.assertEqual([row[0].title for row in rows], ["A", "B"])

    def test_validation(self):
        self.assertTrue(Entry(title="", kind="once", date_str="2026-11-18").validate(date(2026, 11, 18)))
        self.assertIn(
            "日期不能早于今天",
            Entry(title="x", kind="once", date_str="2026-11-17").validate(date(2026, 11, 18)),
        )
        self.assertIn(
            "请至少选择一个星期",
            Entry(title="x", kind="weekly").validate(date(2026, 11, 18)),
        )
        self.assertEqual(Entry(title="ok", kind="weekly", weekdays=[1]).validate(date(2026, 11, 18)), [])

    def test_roundtrip_dict(self):
        entry = Entry(
            title=" 读书 ",
            note=" 第二章 ",
            kind="weekly",
            weekdays=[7, 1, 1],
            start="8:05",
            end="9:00",
            advance_minutes=5,
        )
        data = entry.to_dict()
        self.assertEqual(data["weekdays"], [1, 7])
        self.assertEqual(data["start"], "08:05")
        restored = Entry.from_dict(data)
        self.assertEqual(restored.title, "读书")
        self.assertEqual(restored.note, "第二章")
        self.assertEqual(restored.weekdays, [1, 7])
        self.assertEqual(restored.start_time, time(8, 5))

    def test_prune_fired(self):
        entry = Entry(title="x")
        entry.mark_fired("2026-01-01|09:00", datetime(2026, 1, 1, 9, 0))
        entry.mark_fired("2026-11-18|09:00", datetime(2026, 11, 18, 9, 0))
        entry.prune_fired(30, datetime(2026, 11, 18, 12, 0))
        self.assertNotIn("2026-01-01|09:00", entry.fired)
        self.assertIn("2026-11-18|09:00", entry.fired)


class SchedulerTests(unittest.TestCase):
    def test_fires_at_start(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        now = datetime(2026, 11, 18, 15, 0, 10)
        due = collect_due([entry], now)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].late_minutes, 0)
        self.assertEqual(due[0].heading, "现在开始")

    def test_no_fire_before_start(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        self.assertEqual(collect_due([entry], datetime(2026, 11, 18, 14, 59)), [])

    def test_fire_late_within_grace(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        due = collect_due([entry], datetime(2026, 11, 18, 15, 12))
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].late_minutes, 12)
        self.assertEqual(due[0].heading, "已开始 12 分钟")

    def test_no_fire_after_grace(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="09:00", end="10:00")
        self.assertEqual(collect_due([entry], datetime(2026, 11, 18, 11, 0)), [])

    def test_fire_during_long_event_after_grace(self):
        entry = Entry(title="工作坊", kind="once", date_str="2026-11-18", start="09:00", end="12:00")
        due = collect_due([entry], datetime(2026, 11, 18, 11, 30))
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].late_minutes, 150)

    def test_advance_reminder(self):
        entry = Entry(
            title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00", advance_minutes=30
        )
        due = collect_due([entry], datetime(2026, 11, 18, 14, 30, 5))
        self.assertEqual(len(due), 1)
        self.assertTrue(due[0].advanced)
        self.assertEqual(due[0].heading, "马上开始")

    def test_dedupe_after_mark_fired(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        now = datetime(2026, 11, 18, 15, 1)
        first = collect_due([entry], now)
        self.assertEqual(len(first), 1)
        entry.mark_fired(first[0].key, now)
        self.assertEqual(collect_due([entry], now + timedelta(minutes=2)), [])

    def test_weekly_fires_next_week_again(self):
        entry = Entry(title="例会", kind="weekly", weekdays=[3], start="09:00", end="10:00")
        first_day = datetime(2026, 11, 18, 9, 0)
        due = collect_due([entry], first_day)
        self.assertEqual(len(due), 1)
        entry.mark_fired(due[0].key, first_day)
        next_week = datetime(2026, 11, 25, 9, 0)
        due2 = collect_due([entry], next_week)
        self.assertEqual(len(due2), 1)
        self.assertNotEqual(due2[0].key, due[0].key)

    def test_disabled_skipped(self):
        entry = Entry(title="开会", kind="once", date_str="2026-11-18", start="15:00", end="16:00", enabled=False)
        self.assertEqual(collect_due([entry], datetime(2026, 11, 18, 15, 1)), [])

    def test_overnight_yesterday(self):
        entry = Entry(title="夜班", kind="weekly", weekdays=[2], start="22:00", end="02:00")
        due = collect_due([entry], datetime(2026, 11, 18, 1, 0))  # 周三凌晨，属于周二晚
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].start, datetime(2026, 11, 17, 22, 0))

    def test_next_reminder(self):
        a = Entry(title="远", kind="once", date_str="2026-11-20", start="09:00", end="10:00")
        b = Entry(title="近", kind="once", date_str="2026-11-18", start="18:00", end="19:00")
        found = next_reminder([a, b], datetime(2026, 11, 18, 12, 0))
        self.assertEqual(found[0].title, "近")

    def test_same_slot_entries_all_due(self):
        first = Entry(title="写周报", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        second = Entry(title="回邮件", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        due = collect_due([first, second], datetime(2026, 11, 18, 15, 0, 30))
        self.assertEqual(len(due), 2)
        self.assertEqual({item.entry.title for item in due}, {"写周报", "回邮件"})

    def test_group_due_merges_same_start(self):
        early_a = Entry(title="A", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        early_b = Entry(title="B", kind="once", date_str="2026-11-18", start="15:00", end="17:00")
        later = Entry(title="C", kind="once", date_str="2026-11-18", start="16:00", end="17:00")
        now = datetime(2026, 11, 18, 15, 1)
        groups = group_due(collect_due([early_a, early_b, later], now))
        self.assertEqual([len(group) for group in groups], [2])
        self.assertEqual({item.entry.title for item in groups[0]}, {"A", "B"})

    def test_group_due_keeps_different_starts_separate(self):
        first = Entry(title="A", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        second = Entry(title="B", kind="once", date_str="2026-11-18", start="15:30", end="16:30")
        now = datetime(2026, 11, 18, 15, 31)
        groups = group_due(collect_due([first, second], now))
        self.assertEqual([len(group) for group in groups], [1, 1])


class PointAndDoneTests(unittest.TestCase):
    def test_point_entry_has_no_duration(self):
        entry = Entry(title="吃药", kind="once", date_str="2026-11-18", start="15:00", end="15:00", point=True)
        self.assertEqual(entry.duration_minutes, 0)
        start, end = entry.occurrence(date(2026, 11, 18))
        self.assertEqual(start, end)
        self.assertEqual(entry.time_label(), "15:00 提醒")

    def test_point_entry_reminds_at_time(self):
        entry = Entry(title="吃药", kind="once", date_str="2026-11-18", start="15:00", end="15:00", point=True)
        due = collect_due([entry], datetime(2026, 11, 18, 15, 0, 5))
        self.assertEqual(len(due), 1)

    def test_done_suppresses_reminder(self):
        entry = Entry(title="吃药", kind="once", date_str="2026-11-18", start="15:00", end="15:00", point=True)
        key = Entry.fire_key(date(2026, 11, 18), time(15, 0))
        entry.mark_done(key)
        self.assertEqual(collect_due([entry], datetime(2026, 11, 18, 15, 0, 5)), [])

    def test_weekly_done_only_for_that_day(self):
        entry = Entry(title="打卡", kind="weekly", weekdays=[3], start="15:00", end="15:00", point=True)
        today_key = Entry.fire_key(date(2026, 11, 18), time(15, 0))
        entry.mark_done(today_key)
        nxt = entry.next_occurrence(datetime(2026, 11, 18, 14, 0))
        self.assertEqual(nxt[0], datetime(2026, 11, 25, 15, 0))

    def test_can_complete(self):
        point_once = Entry(title="x", kind="once", date_str="2026-11-18", start="15:00", point=True)
        point_weekly = Entry(title="y", kind="weekly", weekdays=[3], start="15:00", point=True)
        ranged = Entry(title="z", kind="once", date_str="2026-11-18", start="15:00", end="16:00")
        now = datetime(2026, 11, 18, 12, 0)
        self.assertTrue(point_once.can_complete(now))
        self.assertTrue(point_weekly.can_complete(now))
        self.assertFalse(point_weekly.can_complete(datetime(2026, 11, 19, 12, 0)))
        self.assertFalse(ranged.can_complete(now))

    def test_point_roundtrip(self):
        entry = Entry(title="吃药", kind="once", date_str="2026-11-18", start="15:00", point=True)
        entry.mark_done(Entry.fire_key(date(2026, 11, 18), time(15, 0)))
        restored = Entry.from_dict(entry.to_dict())
        self.assertTrue(restored.point)
        self.assertTrue(restored.done)
        self.assertEqual(restored.end, "15:00")
        self.assertEqual(restored.duration_minutes, 0)


class TermWeekTests(unittest.TestCase):
    """教学周：学期开始、周次范围、单双周。"""

    def setUp(self):
        # 2026-09-07 是周一，第 1 周
        set_term(date(2026, 9, 7), 16)

    def tearDown(self):
        set_term(None, DEFAULT_TERM_WEEKS)

    def test_term_start_normalized_to_monday(self):
        self.assertEqual(TERM.start, date(2026, 9, 7))
        set_term(date(2026, 9, 9))  # 周三
        self.assertEqual(TERM.start, date(2026, 9, 7))
        self.assertEqual(monday_of(date(2026, 11, 18)), date(2026, 11, 16))

    def test_week_numbering(self):
        self.assertEqual(TERM.week_of(date(2026, 9, 7)), 1)
        self.assertEqual(TERM.week_of(date(2026, 9, 13)), 1)  # 周日仍属第 1 周
        self.assertEqual(TERM.week_of(date(2026, 9, 14)), 2)
        self.assertIsNone(TERM.week_of(date(2026, 9, 6)))  # 开学前
        self.assertEqual(TERM.week_of(date(2026, 11, 18)), 11)

    def test_weekly_limited_to_term(self):
        entry = Entry(title="离散数学", kind="weekly", weekdays=[3], start="10:10", end="11:50")
        self.assertTrue(entry.occurs_on(date(2026, 11, 18)))  # 第 11 周
        self.assertFalse(entry.occurs_on(date(2026, 9, 2)))  # 开学前
        self.assertTrue(entry.occurs_on(date(2026, 12, 23)))  # 第 16 周最后一周
        self.assertFalse(entry.occurs_on(date(2026, 12, 30)))  # 第 17 周，超出 16
        self.assertFalse(entry.occurs_on(date(2027, 3, 3)))

    def test_term_limited_off_ignores_weeks(self):
        entry = Entry(
            title="常驻", kind="weekly", weekdays=[3], start="10:00", end="11:00", term_limited=False
        )
        self.assertTrue(entry.occurs_on(date(2026, 9, 2)))
        self.assertTrue(entry.occurs_on(date(2027, 3, 3)))

    def test_without_term_is_legacy_behavior(self):
        set_term(None)
        entry = Entry(title="常驻", kind="weekly", weekdays=[3], start="10:00", end="11:00")
        self.assertTrue(entry.occurs_on(date(2026, 11, 18)))
        self.assertTrue(entry.occurs_on(date(2027, 3, 3)))

    def test_odd_even_weeks(self):
        odd = Entry(
            title="单周课", kind="weekly", weekdays=[3], start="10:00", end="11:00", parity=PARITY_ODD
        )
        even = Entry(
            title="双周课", kind="weekly", weekdays=[3], start="10:00", end="11:00", parity=PARITY_EVEN
        )
        self.assertTrue(odd.occurs_on(date(2026, 11, 18)))  # 第 11 周
        self.assertFalse(even.occurs_on(date(2026, 11, 18)))
        self.assertTrue(even.occurs_on(date(2026, 11, 25)))  # 第 12 周
        self.assertFalse(odd.occurs_on(date(2026, 11, 25)))

    def test_custom_week_range(self):
        entry = Entry(
            title="后半学期", kind="weekly", weekdays=[3], start="10:00", end="11:00",
            weeks_from=2, weeks_to=4,
        )
        self.assertFalse(entry.occurs_on(date(2026, 9, 9)))  # 第 1 周
        self.assertTrue(entry.occurs_on(date(2026, 9, 16)))  # 第 2 周
        self.assertTrue(entry.occurs_on(date(2026, 9, 30)))  # 第 4 周
        self.assertFalse(entry.occurs_on(date(2026, 10, 7)))  # 第 5 周

    def test_weeks_to_zero_means_end_of_term(self):
        entry = Entry(
            title="到期末", kind="weekly", weekdays=[3], start="10:00", end="11:00", weeks_from=10
        )
        self.assertFalse(entry.occurs_on(date(2026, 11, 4)))  # 第 9 周
        self.assertTrue(entry.occurs_on(date(2026, 11, 11)))  # 第 10 周
        self.assertTrue(entry.occurs_on(date(2026, 12, 23)))  # 第 16 周

    def test_next_occurrence_respects_week_range(self):
        entry = Entry(
            title="第三周开始", kind="weekly", weekdays=[3], start="10:00", end="11:00",
            weeks_from=3, weeks_to=3,
        )
        found = entry.next_occurrence(datetime(2026, 9, 7, 8, 0))
        self.assertIsNotNone(found)
        self.assertEqual(found[0].date(), date(2026, 9, 23))
        self.assertIsNone(entry.next_occurrence(datetime(2026, 9, 30, 0, 0)))

    def test_scheduler_respects_term(self):
        entry = Entry(title="课", kind="weekly", weekdays=[3], start="10:00", end="11:00")
        self.assertEqual(collect_due([entry], datetime(2026, 9, 2, 10, 0)), [])
        self.assertEqual(len(collect_due([entry], datetime(2026, 11, 18, 10, 0))), 1)

    def test_week_span_label(self):
        entry = Entry(
            title="x", kind="weekly", weekdays=[1], weeks_from=3, weeks_to=9, parity=PARITY_EVEN
        )
        self.assertEqual(entry.week_span_label(), "第 3–9 周 · 双周")
        full = Entry(title="y", kind="weekly", weekdays=[1])
        self.assertEqual(full.week_span_label(), f"第 1–{TERM.weeks} 周")
        always = Entry(title="z", kind="weekly", weekdays=[1], term_limited=False)
        self.assertEqual(always.week_span_label(), "不限周次")

    def test_week_fields_roundtrip(self):
        entry = Entry(
            title="单双周", kind="weekly", weekdays=[1, 3], weeks_from=3, weeks_to=9,
            parity=PARITY_ODD, term_limited=False,
        )
        restored = Entry.from_dict(entry.to_dict())
        self.assertEqual(restored.weeks_from, 3)
        self.assertEqual(restored.weeks_to, 9)
        self.assertEqual(restored.parity, PARITY_ODD)
        self.assertFalse(restored.term_limited)
        # 旧数据没有这些字段，按「整学期、每周」处理
        legacy = Entry.from_dict({"title": "老数据", "kind": "weekly", "weekdays": [2]})
        self.assertEqual(legacy.weeks_from, 1)
        self.assertEqual(legacy.weeks_to, 0)
        self.assertEqual(legacy.parity, "all")
        self.assertTrue(legacy.term_limited)

    def test_validate_week_range(self):
        entry = Entry(title="x", kind="weekly", weekdays=[1], weeks_from=5, weeks_to=3)
        errors = entry.validate(date(2026, 9, 7))
        self.assertTrue(any("结束周" in error for error in errors))
        too_late = Entry(title="x", kind="weekly", weekdays=[1], weeks_from=20)
        self.assertTrue(any("学期总周数" in error for error in too_late.validate(date(2026, 9, 7))))


class CourseTagTests(unittest.TestCase):
    """备注里的教室 / 老师拆分，以及课程标签的存取。"""

    def test_split_common_notes(self):
        self.assertEqual(split_course_note("公共教学楼D203 李绿周"), ("公共教学楼D203", "李绿周"))
        self.assertEqual(split_course_note("实验中心D501 李博洋"), ("实验中心D501", "李博洋"))
        self.assertEqual(split_course_note("公共教学楼D302 郑培嘉"), ("公共教学楼D302", "郑培嘉"))
        self.assertEqual(split_course_note("南校园二教"), ("南校园二教", ""))
        self.assertEqual(split_course_note("HCP 具身\n王可泽老师"), ("", "王可泽"))
        self.assertEqual(split_course_note("记得提交证明！！！！"), ("", ""))
        self.assertEqual(split_course_note(""), ("", ""))

    def test_split_ignores_extra_lines(self):
        room, teacher = split_course_note("公共教学楼D203 李绿周\n记得带教材")
        self.assertEqual((room, teacher), ("公共教学楼D203", "李绿周"))

    def test_course_fields_roundtrip(self):
        entry = Entry(
            title="离散数学",
            subject="离散数学",
            teacher="李绿周",
            room="公共教学楼D203",
            period="1-2节",
            kind="weekly",
            weekdays=[4],
        )
        restored = Entry.from_dict(entry.to_dict())
        self.assertEqual(restored.subject, "离散数学")
        self.assertEqual(restored.teacher, "李绿周")
        self.assertEqual(restored.room, "公共教学楼D203")
        self.assertEqual(restored.period, "1-2节")

    def test_legacy_entry_has_empty_tags(self):
        legacy = Entry.from_dict({"title": "老数据", "kind": "weekly", "weekdays": [2]})
        self.assertEqual(
            (legacy.subject, legacy.teacher, legacy.room, legacy.period), ("", "", "", "")
        )

    def test_course_flag_defaults_by_kind(self):
        self.assertTrue(Entry(title="课", kind="weekly", weekdays=[1]).is_course)
        self.assertFalse(Entry(title="跑腿", kind="once", date_str="2026-11-19").is_course)
        # 一次性也可以手动标记成课程（比如考试）
        self.assertTrue(
            Entry(title="小测", kind="once", date_str="2026-11-19", is_course=True).is_course
        )

    def test_course_flag_roundtrip_and_legacy(self):
        weekly_off = Entry(title="每周打扫", kind="weekly", weekdays=[6], is_course=False)
        data = weekly_off.to_dict()
        self.assertFalse(data["is_course"])
        self.assertFalse(Entry.from_dict(data).is_course)

        legacy_weekly = Entry.from_dict({"title": "课", "kind": "weekly", "weekdays": [1]})
        self.assertTrue(legacy_weekly.is_course)
        legacy_once = Entry.from_dict(
            {"title": "取快递", "kind": "once", "date": "2026-11-19"}
        )
        self.assertFalse(legacy_once.is_course)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "schedule.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip(self):
        store = Store(self.path)
        store.load()
        entry = Entry(title="写周报", kind="weekly", weekdays=[5], start="17:00", end="18:00")
        store.upsert(entry)
        store.settings.sound_enabled = False
        self.assertTrue(store.save())
        self.assertTrue(self.path.exists())

        other = Store(self.path)
        other.load()
        self.assertEqual(len(other.entries), 1)
        self.assertEqual(other.entries[0].title, "写周报")
        self.assertFalse(other.settings.sound_enabled)

    def test_term_settings_roundtrip(self):
        store = Store(self.path)
        store.load()
        store.settings.term_start = "2026-09-07"
        store.settings.term_weeks = 16
        self.assertTrue(store.save())
        other = Store(self.path)
        other.load()
        self.assertEqual(other.settings.term_start, "2026-09-07")
        self.assertEqual(other.settings.term_weeks, 16)

    def test_corrupt_file_is_backed_up(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        store = Store(self.path)
        store.load()
        self.assertEqual(store.entries, [])
        self.assertTrue(store.last_error)
        backups = list(self.path.parent.glob("schedule.broken-*.json"))
        self.assertEqual(len(backups), 1)

    def test_delete_and_sort(self):
        store = Store(self.path)
        late = Entry(title="晚", kind="once", date_str="2026-11-20", start="09:00", end="10:00")
        early = Entry(title="早", kind="once", date_str="2026-11-19", start="09:00", end="10:00")
        disabled = Entry(title="停", kind="once", date_str="2026-11-18", start="09:00", end="10:00", enabled=False)
        for item in (late, early, disabled):
            store.upsert(item)
        self.assertEqual([entry.title for entry in store.entries], ["早", "晚", "停"])
        self.assertTrue(store.delete(early.id))
        self.assertFalse(store.delete("nope"))
        self.assertEqual(len(store.entries), 2)

    def test_missing_file_creates_defaults(self):
        store = Store(self.path)
        store.load()
        self.assertEqual(store.entries, [])
        self.assertTrue(store.settings.sound_enabled)

    def test_settings_from_bad_dict(self):
        settings = Settings.from_dict({"grace_minutes": 0, "sound_enabled": False})
        self.assertEqual(settings.grace_minutes, 1)
        self.assertFalse(settings.sound_enabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
