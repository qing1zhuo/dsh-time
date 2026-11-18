"""应用控制器：把数据、托盘、窗口、提醒串起来。"""

from __future__ import annotations

import ctypes
import os
import queue
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox

from . import autostart, logs, paths, shortcuts, sound, theme
from .model import Entry, KIND_WEEKLY, humanize_delta, occurrences_on_day
from .scheduler import DueReminder, collect_due, group_due, next_reminder
from .single_instance import InstanceGuard
from .store import Store
from .ui_entry_dialog import EntryDialog
from .ui_desktop_pet import DesktopPet
from .ui_main import MainWindow
from .ui_reminder import ReminderPopup
from .win32_tray import TrayIcon

TRAY_OPEN = 1001
TRAY_NEW = 1002
TRAY_PAUSE = 1003
TRAY_AUTOSTART = 1004
TRAY_DATA = 1005
TRAY_HELP = 1006
TRAY_QUIT = 1007
TRAY_PET = 1008

MAX_POPUPS = 3
POPUP_WIDTH = 384
SPI_GETWORKAREA = 0x0030


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
user32.SystemParametersInfoW.restype = ctypes.c_int


class Application:
    def __init__(self, guard: InstanceGuard, start_hidden: bool = False) -> None:
        self.guard = guard
        self.log = logs.setup(paths.LOG_PATH)
        self.log.info("启动时间表（隐藏启动=%s）", start_hidden)
        self.log.info("启动命令：%s", paths.startup_command())
        self.log.info("数据目录：%s", paths.DATA_DIR)

        self._ensure_icons()
        theme.enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        theme.init(self.root)
        theme.setup_ttk(self.root)
        self.icon_image = None
        try:
            png = paths.ASSETS_DIR / "app-256.png"
            self.icon_image = tk.PhotoImage(file=str(png))
            self.root.iconphoto(True, self.icon_image)
        except (tk.TclError, OSError) as exc:
            self.log.warning("设置窗口图标失败：%s", exc)

        self.root.report_callback_exception = self._on_tk_error

        self.store = Store(paths.STORE_PATH)
        self.store.load()
        if self.store.last_error:
            self.log.warning(self.store.last_error)
        self.settings = self.store.settings

        self.paused = False
        self.popups: list[ReminderPopup] = []
        self.pending: list[list[DueReminder]] = []
        self._pending_keys: set[str] = set()
        self.snoozes: list[dict] = []
        self._dialog: EntryDialog | None = None
        self._quitting = False
        self._shown_once = False
        self._hide_notice_shown = False
        self._last_day = date.today()
        self._menu_lock = threading.Lock()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._bootstrap_settings()

        self.tray_icon = TrayIcon(paths.ICON_PATH, self.events, self.tray_menu)
        tray_ok = self.tray_icon.start()
        if not tray_ok:
            self.log.warning("托盘图标启动超时")

        self.main_window = MainWindow(self, show_now=not start_hidden)

        self.pet: DesktopPet | None = None
        if self.settings.pet_enabled:
            self._create_pet()

        self.root.after(150, self._poll_events)
        self.root.after(800, self._tick)
        self.root.after(1200, self._update_tray_tooltip)
        if start_hidden:
            self.root.after(2600, self._startup_balloon)
        else:
            self._shown_once = True

    # ---------------------------------------------------------- 初始化

    def _ensure_icons(self) -> None:
        try:
            if not paths.ICON_PATH.exists():
                from . import icons  # 只有缺图标时才需要 Pillow

                icons.make_ico(paths.ICON_PATH)
            png = paths.ASSETS_DIR / "app-256.png"
            if not png.exists():
                from . import icons

                icons.make_png(png)
        except Exception as exc:  # noqa: BLE001 - 图标失败不应该阻止启动
            self.log.warning("生成图标失败：%s", exc)

    def _bootstrap_settings(self) -> None:
        """默认帮用户打开开机自启；用户在界面上关掉后就不再自动打开。"""
        if self.settings.autostart_choice != "off" and not autostart.is_enabled():
            ok, message = autostart.enable()
            self.log.info("设置开机自启：%s / %s", ok, message)
            if ok:
                self.settings.autostart_choice = "on"
                self.store.save()
        elif autostart.current_command() and not autostart.matches_current_install():
            # 程序目录换过位置，自动修正注册表里的路径。
            autostart.enable()
            self.log.info("已更新开机自启路径")
        if self.settings.first_run:
            self.settings.first_run = False
            self.store.save()

    def _startup_balloon(self) -> None:
        self.tray_icon.notify("时间表已经在托盘里", "双击右下角的时钟图标，随时查看或添加安排。")

    # ---------------------------------------------------------- 主循环

    def run(self) -> None:
        self.root.mainloop()

    def _on_tk_error(self, exc_type, exc_value, exc_tb) -> None:  # noqa: ANN001
        self.log.error("界面回调异常", exc_info=(exc_type, exc_value, exc_tb))

    def _poll_events(self) -> None:
        if self._quitting:
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "activate":
                    self.show_main()
                elif kind == "command":
                    self._handle_tray_command(int(payload))
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _tick(self) -> None:
        if self._quitting:
            return
        try:
            now = datetime.now()
            if not self.paused:
                self._check_snoozes(now)
                due = collect_due(self.store.enabled_entries(), now, self.settings.grace_minutes)
                for group in group_due(due):
                    keys = {item.key for item in group}
                    if len(self.popups) >= MAX_POPUPS:
                        if not (keys & self._pending_keys):
                            self.pending.append(group)
                            self._pending_keys |= keys
                        continue
                    self._show_due_group(group)
            if now.date() != self._last_day:
                self._last_day = now.date()
                self.main_window.refresh()
            else:
                self.main_window.update_status()
            self._update_tray_tooltip()
        except Exception:  # noqa: BLE001 - 定时任务不能因为一次异常停摆
            self.log.exception("定时检查出错")
        finally:
            self.root.after(15000, self._tick)

    def _check_snoozes(self, now: datetime) -> None:
        remaining: list[dict] = []
        for item in self.snoozes:
            if now >= item["at"]:
                dues: list[DueReminder] = item["dues"]
                for due in dues:
                    due.snoozed = True
                    due.late_minutes = 0
                    due.advanced = False
                if len(self.popups) >= MAX_POPUPS:
                    item["at"] = now + timedelta(minutes=1)
                    remaining.append(item)
                else:
                    self._show_due_group(dues, persist=False)
            else:
                remaining.append(item)
        self.snoozes = remaining

    def _drain_pending(self) -> None:
        while self.pending and len(self.popups) < MAX_POPUPS:
            group = self.pending.pop(0)
            for item in group:
                self._pending_keys.discard(item.key)
            self._show_due_group(group)

    def _show_due_group(
        self,
        dues: list[DueReminder],
        heading: str | None = None,
        persist: bool = True,
    ) -> None:
        if not dues:
            return
        if persist:
            for due in dues:
                due.entry.mark_fired(due.key)
            self.store.save()
        titles = "、".join(due.entry.title for due in dues)
        self.log.info("弹出提醒：%s（%s）", titles, dues[0].key)
        try:
            popup = ReminderPopup(self, dues, index=len(self.popups), heading=heading)
        except Exception:  # noqa: BLE001
            self.log.exception("创建提醒弹窗失败")
            return
        self.popups.append(popup)
        if self.settings.sound_enabled:
            sound.play_reminder()

    # ---------------------------------------------------------- 提醒弹窗

    def dismiss_reminder(self, popup: ReminderPopup) -> None:
        if popup in self.popups:
            self.popups.remove(popup)
        try:
            popup.destroy()
        except tk.TclError:
            pass
        self._reposition_popups()
        self.root.after(80, self._drain_pending)

    def snooze_reminder(self, popup: ReminderPopup, minutes: int) -> None:
        self.snoozes.append(
            {"dues": list(popup.dues), "at": datetime.now() + timedelta(minutes=minutes)}
        )
        if popup in self.popups:
            self.popups.remove(popup)
        try:
            popup.destroy()
        except tk.TclError:
            pass
        self._reposition_popups()
        self.main_window.toast(f"好的，{minutes} 分钟后再提醒你")

    def complete_reminder(self, popup: ReminderPopup) -> None:
        """点击「已完成」：把这一组里的时间点提醒标记完成。"""
        dues = [due for due in popup.dues if due.entry.point]
        if not dues:
            self.dismiss_reminder(popup)
            return
        now = datetime.now()
        for due in dues:
            due.entry.mark_done(due.key, now)
            due.entry.mark_fired(due.key, now)
        self.store.save()
        titles = "、".join(due.entry.title for due in dues)
        self.log.info("标记完成：%s", titles)
        if popup in self.popups:
            self.popups.remove(popup)
        try:
            popup.destroy()
        except tk.TclError:
            pass
        self._reposition_popups()
        self.main_window.refresh()
        self.main_window.toast(f"已完成：{titles}")
        self.root.after(80, self._drain_pending)

    def toggle_entry_done(self, entry: Entry, day=None) -> None:  # noqa: ANN001
        """列表里手动打勾 / 取消完成；day 指定是哪一天的那一次。"""
        if day is None:
            key = entry.relevant_key(datetime.now())
        else:
            key = Entry.fire_key(day, entry.start_time)
        if not key:
            return
        if entry.has_done(key):
            entry.unmark_done(key)
            message = f"已取消完成：{entry.title}"
        else:
            entry.mark_done(key)
            message = f"已完成：{entry.title}"
        self.store.save()
        self.main_window.refresh()
        self.main_window.toast(message)
        self._update_tray_tooltip()

    def _reposition_popups(self) -> None:
        for index, popup in enumerate(self.popups):
            try:
                popup.reposition(index)
            except tk.TclError:
                pass

    def _close_all_popups(self) -> None:
        for popup in list(self.popups):
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self.popups.clear()
        self.pending.clear()
        self._pending_keys.clear()

    def reminder_position(self, index: int, height: int) -> tuple[int, int]:
        left, top, right, bottom = self._work_area()
        margin = theme.px(18)
        gap = theme.px(10)
        x = max(left + margin, right - margin - theme.px(POPUP_WIDTH))
        y = bottom - margin - height - index * (height + gap)
        if y < top + margin:
            y = top + margin
        return x, y

    def _work_area(self) -> tuple[int, int, int, int]:
        rect = RECT()
        try:
            ok = user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
            if ok and rect.right > rect.left and rect.bottom > rect.top:
                return rect.left, rect.top, rect.right, rect.bottom
        except OSError:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def work_area(self) -> tuple[int, int, int, int]:
        return self._work_area()

    def virtual_screen(self) -> tuple[int, int, int, int]:
        """所有显示器合起来的范围，用于把小窗拖动到副屏。"""
        try:
            left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            top = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except OSError:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    # ---------------------------------------------------------- 桌面小窗

    def _create_pet(self) -> None:
        try:
            self.pet = DesktopPet(self)
        except Exception:  # noqa: BLE001 - 小窗失败不影响主程序
            self.log.exception("创建桌面小窗失败")
            self.pet = None
            self.settings.pet_enabled = False

    def set_pet_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.settings.pet_enabled = enabled
        self.store.save()
        if enabled:
            if self.pet is None:
                self._create_pet()
        else:
            pet, self.pet = self.pet, None
            if pet is not None:
                try:
                    pet.close()
                except tk.TclError:
                    pass
        if getattr(self, "main_window", None):
            self.main_window.set_pet_toggle(enabled)

    # ---------------------------------------------------------- 窗口

    def show_main(self) -> None:
        self._shown_once = True
        self.main_window.show()

    def hide_main(self) -> None:
        self.main_window.withdraw()
        if not self._hide_notice_shown:
            self._hide_notice_shown = True
            self.tray_icon.notify("时间表仍在运行", "窗口已缩到托盘，右键图标可以查看菜单或退出。")

    def toast(self, message: str) -> None:
        if self.main_window.winfo_viewable():
            self.main_window.toast(message)

    # ---------------------------------------------------------- 日程操作

    def new_entry(self) -> None:
        self._open_dialog(None)

    def edit_entry(self, entry: Entry) -> None:
        self._open_dialog(entry)

    def _open_dialog(self, entry: Entry | None) -> None:
        if not self.main_window.winfo_viewable():
            self.show_main()
        if self._dialog is not None:
            try:
                self._dialog.close()
            except tk.TclError:
                pass
            self._dialog = None
        try:
            self._dialog = EntryDialog(self, entry.clone() if entry else None)
        except Exception:  # noqa: BLE001
            self.log.exception("打开日程对话框失败")
            messagebox.showerror("时间表", "打不开编辑窗口，详细信息记录在 data/app.log 里。", parent=self.main_window)

    def on_dialog_closed(self, dialog: EntryDialog) -> None:
        if self._dialog is dialog:
            self._dialog = None

    def save_entry(self, entry: Entry, is_new: bool) -> None:
        self.store.upsert(entry)
        if not self.store.save():
            messagebox.showerror("保存失败", self.store.last_error, parent=self.main_window)
            return
        self.main_window.refresh()
        self._update_tray_tooltip()
        self.main_window.toast("已保存" if is_new else "已更新")

    def delete_entry(self, entry: Entry, confirm: bool = True) -> None:
        if confirm:
            note = (
                "\n\n这是一条每周重复的日程，会删除整个系列（所有星期）。"
                if entry.kind == KIND_WEEKLY
                else ""
            )
            confirmed = messagebox.askyesno(
                "删除日程",
                f"确定要删除「{entry.title}」吗？{note}",
                parent=self.main_window,
            )
            if not confirmed:
                return
        self.store.delete(entry.id)
        self.store.save()
        self.main_window.refresh()
        self._update_tray_tooltip()
        self.main_window.toast("已删除")

    def set_entry_enabled(self, entry: Entry, enabled: bool) -> None:
        entry.enabled = bool(enabled)
        self.store.save()
        self.main_window.refresh()
        self._update_tray_tooltip()

    def set_sound_enabled(self, enabled: bool) -> None:
        self.settings.sound_enabled = bool(enabled)
        self.store.save()
        self.main_window.toast("提示音已开启" if enabled else "提示音已关闭")

    def set_autostart(self, enabled: bool) -> None:
        ok, message = autostart.set_enabled(bool(enabled))
        self.log.info("设置开机自启：%s / %s", enabled, message)
        self.main_window.toast(message)
        if ok:
            self.settings.autostart_choice = "on" if enabled else "off"
            self.store.save()
        else:
            self.main_window.autostart_toggle.set_value(autostart.is_enabled(), animate=False)

    def autostart_enabled(self) -> bool:
        return autostart.is_enabled()

    # ---------------------------------------------------------- 小工具

    def test_reminder(self) -> None:
        """弹一张示例卡片：同一个时间段里的两件事会合并展示。"""
        now = datetime.now()
        end = now + timedelta(minutes=30)
        samples = (
            ("这是一条测试提醒", "真实的安排到点时会像这样出现在屏幕右下角。"),
            ("同一时段可以放第二件事", "同一时间的多条安排会合并成一张卡片，逐条列出。"),
        )
        dues: list[DueReminder] = []
        for index, (title, note) in enumerate(samples):
            entry = Entry(
                title=title,
                note=note,
                kind="once",
                date_str=now.date().isoformat(),
                start=now.strftime("%H:%M"),
                end=end.strftime("%H:%M"),
            )
            dues.append(
                DueReminder(
                    entry=entry,
                    start=now,
                    end=end,
                    key=f"test|{now.isoformat()}|{index}",
                    late_minutes=0,
                    advanced=False,
                )
            )
        self._show_due_group(dues, heading="测试提醒", persist=False)

    def create_shortcut(self) -> None:
        ok, message = shortcuts.create_desktop_shortcut()
        self.log.info("创建快捷方式：%s", message)
        self.main_window.toast(message)
        if not ok:
            messagebox.showerror("创建快捷方式", message, parent=self.main_window)

    def open_data_dir(self) -> None:
        shortcuts.open_folder(paths.DATA_DIR)

    def open_help(self) -> None:
        readme = paths.APP_DIR / "README.md"
        try:
            if readme.exists():
                os.startfile(str(readme))  # noqa: S606
            else:
                self.open_data_dir()
        except OSError as exc:
            self.log.warning("打开使用说明失败：%s", exc)

    # ---------------------------------------------------------- 托盘

    def tray_alive(self) -> bool:
        tray = getattr(self, "tray_icon", None)
        return bool(tray and tray.alive and tray.added)

    def tray_menu(self) -> list[dict]:
        with self._menu_lock:
            today = date.today()
            # 用快照构造菜单，避免主线程正在增删日程时读到一半
            entries = [entry for entry in list(self.store.entries) if entry.enabled]
            rows = occurrences_on_day(entries, today)
            items: list[dict] = [
                {"id": TRAY_OPEN, "label": "打开时间表", "default": True},
                {"id": TRAY_NEW, "label": "新建日程"},
                {"kind": "sep"},
                {"id": 0, "label": f"今天 · {len(rows)} 项", "enabled": False},
            ]
            if rows:
                for entry, start_dt, _end_dt in rows[:7]:
                    title = entry.title if len(entry.title) <= 16 else entry.title[:16] + "…"
                    items.append(
                        {"id": 0, "label": f"    {start_dt:%H:%M}  {title}", "enabled": False}
                    )
                if len(rows) > 7:
                    items.append({"id": 0, "label": f"    还有 {len(rows) - 7} 项", "enabled": False})
            else:
                items.append({"id": 0, "label": "    今天没有安排", "enabled": False})
            items.extend(
                [
                    {"kind": "sep"},
                    {
                        "id": TRAY_PAUSE,
                        "label": "恢复提醒" if self.paused else "暂停提醒",
                        "checked": self.paused,
                    },
                    {
                        "id": TRAY_PET,
                        "label": "桌面小窗",
                        "checked": bool(self.settings.pet_enabled),
                    },
                    {
                        "id": TRAY_AUTOSTART,
                        "label": "开机自动启动",
                        "checked": autostart.is_enabled(),
                    },
                    {"kind": "sep"},
                    {"id": TRAY_DATA, "label": "打开数据文件夹"},
                    {"id": TRAY_HELP, "label": "使用说明"},
                    {"id": TRAY_QUIT, "label": "退出"},
                ]
            )
        return items

    def _handle_tray_command(self, command: int) -> None:
        if command == TRAY_OPEN:
            self.show_main()
        elif command == TRAY_NEW:
            self.show_main()
            self.new_entry()
        elif command == TRAY_PAUSE:
            self.toggle_pause()
        elif command == TRAY_PET:
            self.set_pet_enabled(not self.settings.pet_enabled)
        elif command == TRAY_AUTOSTART:
            self.set_autostart(not autostart.is_enabled())
        elif command == TRAY_DATA:
            self.open_data_dir()
        elif command == TRAY_HELP:
            self.open_help()
        elif command == TRAY_QUIT:
            self.quit_app()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self._close_all_popups()
            self.tray_icon.notify("提醒已暂停", "右键托盘图标，选「恢复提醒」即可继续。")
        else:
            self.tray_icon.notify("提醒已恢复", "到点会照常提醒你。")
        self.main_window.update_status()
        self._update_tray_tooltip()

    def _update_tray_tooltip(self) -> None:
        if not getattr(self, "tray_icon", None):
            return
        if self.paused:
            text = "时间表 · 提醒已暂停"
        else:
            now = datetime.now()
            upcoming = next_reminder(self.store.enabled_entries(), now)
            if upcoming:
                entry, fire_at = upcoming
                delta = (fire_at - now).total_seconds()
                text = f"时间表 · 下次 {fire_at:%H:%M} {entry.title}（{humanize_delta(delta)}）"
            else:
                text = "时间表 · 暂无安排"
        try:
            self.tray_icon.set_tooltip(text)
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------- 退出

    def quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.log.info("退出时间表")
        self.store.save()
        self._close_all_popups()
        if self.pet is not None:
            try:
                self.pet.close()
            except tk.TclError:
                pass
            self.pet = None
        try:
            self.tray_icon.stop()
        except Exception:  # noqa: BLE001
            self.log.exception("停止托盘失败")
        try:
            self.guard.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass
