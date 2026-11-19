"""界面预览：单独打开某个对话框/弹窗，截图后退出（开发自检用）。

用法：python tools/ui_preview.py dialog|dialog-weekly|main|main-list|grid|popup|calendar [输出路径]
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import model, theme  # noqa: E402
from app.model import KIND_WEEKLY, Entry, monday_of  # noqa: E402
from app.scheduler import DueReminder  # noqa: E402
from app.store import Settings, Store  # noqa: E402
from app.ui_entry_dialog import EntryDialog  # noqa: E402
from app.ui_main import MainWindow  # noqa: E402
from app.ui_reminder import ReminderPopup  # noqa: E402
from app.ui_week_grid import WeekGrid  # noqa: E402
from app.widgets import CalendarPopup  # noqa: E402
from tools.capture_window import capture_hwnd  # noqa: E402


class FakeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.main_window = tk.Toplevel(root)
        self.main_window.withdraw()
        self.settings = Settings()
        self.store = Store(None)
        self.saved: list[Entry] = []
        self.paused = False

    def work_area(self) -> tuple[int, int, int, int]:
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def virtual_screen(self) -> tuple[int, int, int, int]:
        return self.work_area()

    def set_pet_enabled(self, enabled: bool) -> None:
        self.settings.pet_enabled = bool(enabled)

    def __getattr__(self, name: str):
        # 预览用的假 app：未实现的方法一律当作空操作
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: None

    def save_entry(self, entry, is_new):  # noqa: ANN001
        self.saved.append(entry)

    def on_dialog_closed(self, dialog):  # noqa: ANN001
        pass

    def delete_entry(self, entry, confirm: bool = True):  # noqa: ANN001
        pass

    def reminder_position(self, index: int, height: int) -> tuple[int, int]:
        return 200, 200

    def dismiss_reminder(self, popup):  # noqa: ANN001
        pass

    def snooze_reminder(self, popup, minutes):  # noqa: ANN001
        pass

    def show_main(self) -> None:
        pass

    def tray_alive(self) -> bool:
        return True


def sample_due(late: bool = False) -> DueReminder:
    now = datetime.now()
    start = now - timedelta(minutes=8) if late else now
    end = start + timedelta(minutes=45)
    entry = Entry(
        title="项目复盘会",
        note="会议室 B，记得带上上周的数据",
        kind="weekly",
        weekdays=[1, 3, 5],
        start=start.strftime("%H:%M"),
        end=end.strftime("%H:%M"),
        advance_minutes=10,
    )
    return DueReminder(
        entry=entry,
        start=start,
        end=end,
        key="preview|1",
        late_minutes=8 if late else 0,
        advanced=False,
    )


def sample_point_due() -> DueReminder:
    now = datetime.now().replace(second=0, microsecond=0)
    entry = Entry(
        title="吃药",
        note="饭后半小时，两粒",
        kind="weekly",
        weekdays=[1, 2, 3, 4, 5, 6, 7],
        start=now.strftime("%H:%M"),
        point=True,
    )
    return DueReminder(
        entry=entry,
        start=now,
        end=now,
        key="preview|point",
        late_minutes=0,
        advanced=False,
    )


def sample_week_entries() -> list[Entry]:
    """预览用的一周课表（含时间重叠，用来看并排色块）。"""
    monday = monday_of(date.today())
    return [
        Entry(title="离散数学", subject="离散数学", teacher="李绿周", room="公共教学楼D203", period="1-2节", kind="weekly", weekdays=[2, 4], start="08:00", end="09:40"),
        Entry(title="概率论与数理统计", subject="概率论与数理统计", teacher="郑培嘉", room="公共教学楼D302", period="3-4节", kind="weekly", weekdays=[4], start="10:10", end="11:50"),
        Entry(title="数据结构与算法", subject="数据结构与算法", teacher="魏鹏旭", room="公共教学楼D402", period="3-4节", kind="weekly", weekdays=[3], start="10:10", end="11:50"),
        Entry(title="计算机组成原理", subject="计算机组成原理", teacher="李博洋", room="公共教学楼D203", period="5-6节", kind="weekly", weekdays=[1, 3], start="14:20", end="16:00"),
        Entry(title="定向越野", subject="定向越野", teacher="黄强", room="东田径场", period="5-6节", kind="weekly", weekdays=[2], start="14:20", end="16:00"),
        Entry(title="计组答疑", subject="计算机组成原理", room="实验中心D501", period="5-6节", kind="weekly", weekdays=[2], start="14:30", end="15:30"),
        Entry(title="计组实验", subject="计算机组成原理", teacher="李博洋", room="实验中心D501", period="9-11节", kind="weekly", weekdays=[3], start="19:00", end="21:35"),
        Entry(title="组合数学与数论", subject="组合数学与数论", teacher="卢伟", room="公共教学楼B301", period="9-11节", kind="weekly", weekdays=[2], start="19:00", end="21:35"),
        Entry(title="马克思主义原理", subject="马克思主义原理", teacher="刘勇", room="公共教学楼C401", period="5-7节", kind="weekly", weekdays=[5], start="14:20", end="17:15"),
        Entry(title="学业辅导", subject="学业辅导", teacher="", room="南校园二教", period="7-9节", kind="weekly", weekdays=[7], start="15:00", end="18:00", advance_minutes=60),
        Entry(title="概率论刷题", kind="once", date_str=(monday + timedelta(days=5)).isoformat(), start="10:00", end="12:30"),
    ]


SAMPLE_PET_INFO = {
    "clock": "14:32",
    "date": "11 月 19 日 周三",
    "paused": False,
    "current_title": "离散数学",
    "current_status": "还剩 25 分钟",
    "status_color": "green",
    "progress": 0.62,
    "next_text": "15:00  交作业 · 28 分钟后",
}


def capture_info_panel(target: Path) -> "Image.Image | None":
    """把悬停信息卡单独截出来，抠掉圆角外面的底，供合成预览图用。"""
    import time

    from PIL import Image, ImageDraw

    from app.ui_pet_info import PetInfoPanel

    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    theme.setup_ttk(root)
    panel = PetInfoPanel(root)
    panel.prepare(SAMPLE_PET_INFO)
    panel.show_at(80, 80)
    deadline = time.time() + 0.5
    while time.time() < deadline:
        root.update()
        time.sleep(0.02)
    ok = capture_hwnd(panel.winfo_id(), target)
    panel.destroy()
    root.destroy()
    if not ok or not target.exists():
        return None

    with Image.open(target) as raw:
        image = raw.convert("RGBA")
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1), radius=max(4, round(12 * theme.SCALE)), fill=255
    )
    image.putalpha(mask)
    return image


def render_pet_preview(out: Path, with_panel: bool = False) -> bool:
    """桌宠是原生分层窗口，PrintWindow 抓不到，这里直接按素材合成一张预览图。"""
    from PIL import Image, ImageDraw

    from app import paths

    frame_path = paths.ASSETS_DIR / "pet" / "whale-girl-open.png"
    if not frame_path.exists():
        print(f"缺少桌宠素材：{frame_path}")
        return False
    with Image.open(frame_path) as image:
        pet = image.convert("RGBA")
    pet.thumbnail((400, 400), Image.LANCZOS)

    panel = None
    if with_panel:
        import tempfile

        tmp = Path(tempfile.gettempdir()) / "timetable-pet-info-panel.png"
        panel = capture_info_panel(tmp)

    width = max(820, pet.width + 240, (panel.width + 120) if panel else 0)
    height = 40 + pet.height + 40 + ((panel.height + 16) if panel else 0)
    canvas = Image.new("RGB", (width, height), "#EEF2F8")
    top = (223, 232, 246)
    bottom = (247, 249, 253)
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        ratio = y / max(1, height - 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)),
        )

    pet_x = (width - pet.width) // 2
    pet_y = height - pet.height - 40
    canvas.paste(pet, (pet_x, pet_y), pet)

    if panel is not None:
        panel_x = max(12, pet_x + pet.width // 2 - panel.width // 2)
        panel_y = pet_y - panel.height - 16
        canvas.paste(panel, (panel_x, max(12, panel_y)), panel)

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return True


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dialog"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else f"build/preview-{mode}.png")

    if mode.startswith("pet"):
        ok = render_pet_preview(out, with_panel=mode == "pet-hover")
        print(f"captured={ok} -> {out}")
        return 0 if ok else 2

    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    theme.init(root)
    theme.setup_ttk(root)
    app = FakeApp(root)
    window: tk.Toplevel

    if mode in ("dialog", "dialog-weekly", "dialog-point"):
        entry = None
        if mode == "dialog-weekly":
            entry = Entry(
                title="离散数学",
                note="带教材和习题本",
                subject="离散数学",
                teacher="李绿周",
                room="公共教学楼D203",
                period="1-2节",
                kind="weekly",
                weekdays=[1, 3, 5],
                start="08:00",
                end="09:40",
                advance_minutes=30,
            )
        elif mode == "dialog-point":
            entry = Entry(
                title="吃药",
                note="饭后半小时，两粒",
                kind="weekly",
                weekdays=[1, 2, 3, 4, 5, 6, 7],
                start="15:00",
                point=True,
                advance_minutes=0,
            )
        window = EntryDialog(app, entry)
    elif mode in ("popup", "popup-late"):
        window = ReminderPopup(app, [sample_due(late=mode == "popup-late")], index=0)
    elif mode == "popup-point":
        window = ReminderPopup(app, [sample_point_due()], index=0)
    elif mode == "popup-group":
        base = sample_due(late=False)
        second = sample_due(late=False)
        second.entry.title = "回复客户邮件"
        second.entry.note = "把报价单和排期一起发过去"
        second.key = "preview|2"
        window = ReminderPopup(app, [base, second], index=0)
    elif mode == "grid":
        model.set_term(monday_of(date.today()) - timedelta(weeks=10), 16)
        host = tk.Toplevel(root)
        host.title("课表预览")
        host.configure(bg=theme.COLORS["bg"])
        width = min(1530, root.winfo_screenwidth() - 40)
        host.geometry(f"{width}x{min(1260, root.winfo_screenheight() - 60)}+40+20")
        courses = [entry for entry in sample_week_entries() if entry.kind == KIND_WEEKLY]
        grid = WeekGrid(host, courses, monday_of(date.today()), course_only=True)
        grid.pack(fill="both", expand=True, padx=theme.px(20), pady=theme.px(14))
        window = host
    elif mode in ("main", "main-list"):
        model.set_term(monday_of(date.today()) - timedelta(weeks=10), 16)
        app.settings.term_weeks = 16
        app.settings.term_start = model.TERM.start.isoformat()
        app.store.entries = sample_week_entries()
        window = MainWindow(app)
        window.set_filter("grid" if mode == "main" else "all")
    elif mode == "calendar":
        anchor_window = tk.Toplevel(root)
        anchor_window.geometry("420x120+240+240")
        label = tk.Label(anchor_window, text="日期", bg="#ffffff", font=("Microsoft YaHei UI", 10))
        label.pack(pady=30)
        anchor_window.update_idletasks()
        window = CalendarPopup(root, date.today(), lambda picked: None, anchor=label)
    else:
        print(f"unknown mode: {mode}")
        return 1

    def shot() -> None:
        root.update_idletasks()
        ok = capture_hwnd(window.winfo_id(), out)
        print(f"captured={ok} -> {out}")
        root.after(100, root.destroy)

    root.after(1500, shot)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
