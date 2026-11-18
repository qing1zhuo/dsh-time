"""界面预览：单独打开某个对话框/弹窗，截图后退出（开发自检用）。

用法：python tools/ui_preview.py dialog|dialog-weekly|popup|popup-late|calendar [输出路径]
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.model import Entry  # noqa: E402
from app.scheduler import DueReminder  # noqa: E402
from app.store import Settings, Store  # noqa: E402
from app.ui_desktop_pet import DesktopPet  # noqa: E402
from app.ui_entry_dialog import EntryDialog  # noqa: E402
from app.ui_reminder import ReminderPopup  # noqa: E402
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


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dialog"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else f"build/preview-{mode}.png")

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
                title="健身",
                note="带好运动鞋和水",
                kind="weekly",
                weekdays=[1, 3, 5],
                start="19:00",
                end="20:00",
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
    elif mode.startswith("pet"):
        now = datetime.now()
        entries: list[Entry] = []
        if mode == "pet-current":
            entries = [
                Entry(
                    title="写本周周报",
                    kind="once",
                    date_str=date.today().isoformat(),
                    start=(now - timedelta(minutes=40)).strftime("%H:%M"),
                    end=(now + timedelta(minutes=20)).strftime("%H:%M"),
                ),
                Entry(
                    title="和设计对需求",
                    kind="once",
                    date_str=date.today().isoformat(),
                    start=(now + timedelta(minutes=10)).strftime("%H:%M"),
                    end=(now + timedelta(minutes=40)).strftime("%H:%M"),
                ),
            ]
        elif mode == "pet-point":
            entries = [
                Entry(
                    title="吃药",
                    kind="weekly",
                    weekdays=[now.isoweekday()],
                    start=(now - timedelta(minutes=25)).strftime("%H:%M"),
                    point=True,
                ),
                Entry(
                    title="交水电费",
                    kind="once",
                    date_str=date.today().isoformat(),
                    start=(now + timedelta(minutes=25)).strftime("%H:%M"),
                    point=True,
                ),
            ]
        app.store.entries = entries
        window = DesktopPet(app)
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
