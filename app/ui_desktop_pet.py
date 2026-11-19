"""桌面上的鲸鱼娘小窗。

- 逐像素透明的分层窗口，PNG 的柔和边缘不会在壁纸上留下色边；
- 会自己眨眼（偶尔连眨两下），被点一下也会眨；暂停提醒时闭眼打盹；
- 鼠标滚轮在她身上滚动可以放大 / 缩小，大小会记住；
- 鼠标停在她身上浮出一张信息卡：现在做什么、接下来做什么；
- 单击打开主窗口，按住拖动可以放到任意位置，右键是小窗菜单。

角色素材来自 YunYueSama/codex-deepseek-pet（见 assets/pet/NOTICE.md）。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from . import paths
from .model import WEEKDAY_CN, humanize_delta, next_upcoming, occurrences_on_day
from .theme import px
from .ui_pet_info import PetInfoPanel
from .ui_pet_menu import PetMenu
from .win32_pet import PetWindow, premultiply

ASSET_OPEN = "whale-girl-open.png"
ASSET_BLINK = "whale-girl-blink.png"


class DesktopPet:
    """小窗本体：持有原生窗口、悬停卡片，并把鼠标事件转成应用层事件。"""

    HEIGHT = 210        # 96dpi 下的角色高度
    MARGIN = 18         # 离屏幕边缘的距离
    MIN_SCALE = 0.6
    MAX_SCALE = 1.8
    SCALE_STEP = 0.08   # 滚轮一格
    HOVER_HIDE_MS = 140

    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app
        self._menu: PetMenu | None = None
        self._panel: PetInfoPanel | None = None
        self._hide_job: str | None = None
        self._enter_job: str | None = None
        self._resize_job: str | None = None
        self._refresh_job: str | None = None

        self._scale = self._clamp_scale(self.app.settings.pet_scale)
        self._source = self._load_source()
        self._suppress_hover_until = 0.0
        frames = self._build_frames(self._scale)
        x, y = self._initial_position(frames[0][1])
        self._window = PetWindow(
            frames,
            x,
            y,
            topmost=bool(app.settings.pet_topmost),
            on_event=self._on_native_event,
        )
        self._window.start()

        try:
            self._panel = PetInfoPanel(app.root)
        except Exception:  # noqa: BLE001 - 信息卡失败不影响桌宠本身
            self.app.log.exception("创建悬停信息卡失败")
            self._panel = None

    # ---------------------------------------------------------- 素材

    def _load_source(self) -> list:
        from PIL import Image

        images = []
        for name in (ASSET_OPEN, ASSET_BLINK):
            path = paths.ASSETS_DIR / "pet" / name
            if not path.exists():
                raise FileNotFoundError(f"缺少桌宠素材：{path}")
            with Image.open(path) as image:
                images.append(image.convert("RGBA"))
        return images

    def _build_frames(self, scale: float) -> list[tuple[int, int, bytes]]:
        from PIL import Image

        target_height = max(48, px(self.HEIGHT * scale))
        frames: list[tuple[int, int, bytes]] = []
        for image in self._source:
            width = max(1, round(image.width * target_height / image.height))
            scaled = image.resize((width, target_height), Image.LANCZOS)
            frames.append(premultiply(scaled))
        return frames

    def _initial_position(self, height: int) -> tuple[int, int]:
        x, y = self.app.settings.pet_x, self.app.settings.pet_y
        if x is None or y is None:
            left, _top, _right, bottom = self.app.work_area()
            return left + px(self.MARGIN), bottom - px(self.MARGIN) - height
        return int(x), int(y)

    # ---------------------------------------------------------- 缩放

    @classmethod
    def _clamp_scale(cls, value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 1.0
        if number != number:
            return 1.0
        return round(max(cls.MIN_SCALE, min(cls.MAX_SCALE, number)), 2)

    @property
    def scale(self) -> float:
        return self._scale

    def zoom_in(self) -> None:
        self._set_scale(self._scale + self.SCALE_STEP)

    def zoom_out(self) -> None:
        self._set_scale(self._scale - self.SCALE_STEP)

    def reset_zoom(self) -> None:
        self._set_scale(1.0)

    def on_wheel(self, delta: int) -> None:
        steps = float(delta) / 120.0
        if not steps:
            return
        self._set_scale(self._scale + steps * self.SCALE_STEP)

    def _set_scale(self, value: float) -> None:
        scale = self._clamp_scale(value)
        if abs(scale - self._scale) < 0.001:
            return
        self._scale = scale
        self.app.settings.pet_scale = scale
        self.app.store.save()
        self._schedule_resize()

    def _schedule_resize(self) -> None:
        """滚轮会连发，等停一下再重建位图，免得一路卡。"""
        if self._resize_job is not None:
            try:
                self.app.root.after_cancel(self._resize_job)
            except Exception:  # noqa: BLE001
                pass
        self._resize_job = self.app.root.after(70, self._apply_resize)

    def _apply_resize(self) -> None:
        self._resize_job = None
        window = getattr(self, "_window", None)
        if window is None:
            return
        try:
            window.resize(self._build_frames(self._scale), keep_bottom=True)
        except Exception:  # noqa: BLE001
            self.app.log.exception("调整桌宠大小失败")
            return
        # 脚底不动，意味着左上角变了；等一下把新位置也存回去
        self.app.root.after(80, self._persist_position)
        if self._panel is not None and self._panel.visible:
            # 等原生窗口把那帧换上再重排，不然卡片会按旧尺寸站位
            self.app.root.after(50, self._refresh_panel_if_visible)

    def _persist_position(self) -> None:
        window = getattr(self, "_window", None)
        if window is None:
            return
        x, y = window.position
        if (x, y) == (self.app.settings.pet_x, self.app.settings.pet_y):
            return
        self.app.settings.pet_x = int(x)
        self.app.settings.pet_y = int(y)
        self.app.store.save()

    def _refresh_panel_if_visible(self) -> None:
        if self._panel is not None and self._panel.visible:
            self._show_panel()

    # ---------------------------------------------------------- 悬停信息

    def on_hover_enter(self) -> None:
        if self._menu is not None or time.monotonic() < self._suppress_hover_until:
            return
        self._cancel_hide()
        self._cancel_enter()
        # 停一下再弹，鼠标只是路过时就不会闪出一张卡
        self._enter_job = self.app.root.after(200, self._show_panel)

    def on_hover_leave(self) -> None:
        self._cancel_enter()
        self._schedule_hide()

    def on_drag_start(self) -> None:
        self._cancel_enter()
        self._hide_panel()
        self._suppress_hover_until = time.monotonic() + 0.8

    def _cancel_enter(self) -> None:
        if self._enter_job is not None:
            try:
                self.app.root.after_cancel(self._enter_job)
            except Exception:  # noqa: BLE001
                pass
            self._enter_job = None

    def _schedule_hide(self) -> None:
        self._cancel_hide()
        self._hide_job = self.app.root.after(self.HOVER_HIDE_MS, self._hide_panel)

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            try:
                self.app.root.after_cancel(self._hide_job)
            except Exception:  # noqa: BLE001
                pass
            self._hide_job = None

    def _hide_panel(self) -> None:
        self._hide_job = None
        if self._refresh_job is not None:
            try:
                self.app.root.after_cancel(self._refresh_job)
            except Exception:  # noqa: BLE001
                pass
            self._refresh_job = None
        if self._panel is not None:
            self._panel.hide()

    def _schedule_refresh(self) -> None:
        if self._refresh_job is not None:
            try:
                self.app.root.after_cancel(self._refresh_job)
            except Exception:  # noqa: BLE001
                pass
        self._refresh_job = self.app.root.after(15000, self._on_refresh)

    def _on_refresh(self) -> None:
        self._refresh_job = None
        if self._panel is not None and self._panel.visible:
            self._show_panel()

    def _show_panel(self) -> None:
        self._enter_job = None
        if self._panel is None:
            return
        try:
            data = self._info_data()
            width, height = self._panel.prepare(data)
            x, y = self._panel_position(width, height)
            self._panel.show_at(x, y)
            self._schedule_refresh()
        except Exception:  # noqa: BLE001
            self.app.log.exception("显示悬停信息卡失败")

    def _panel_position(self, width: int, height: int) -> tuple[int, int]:
        wx, wy = self._window.position
        ww, wh = self._window.size
        x = wx + ww // 2 - width // 2
        y = wy - height - px(8)
        left, top, right, bottom = self.app.virtual_screen()
        work_left, work_top, work_right, work_bottom = self.app.work_area()
        gap = px(6)
        if y < top + gap:
            y = wy + wh + px(8)
        low = min(bottom, work_bottom) if wx < work_right and wx + ww > work_left else bottom
        x = max(left + gap, min(x, right - width - gap))
        y = max(top + gap, min(y, low - height - gap))
        return int(x), int(y)

    def _info_data(self) -> dict:
        now = datetime.now()
        entries = self.app.store.enabled_entries()
        rows = occurrences_on_day(entries, now.date())

        current: list[tuple[object, datetime, datetime]] = []
        for entry, start_dt, end_dt in rows:
            if entry.point:
                key = entry.fire_key(start_dt.date(), entry.start_time)
                if start_dt <= now and not entry.has_done(key):
                    current.append((entry, start_dt, end_dt))
            elif start_dt <= now <= end_dt:
                current.append((entry, start_dt, end_dt))
        current.sort(key=lambda row: row[1])

        data: dict = {
            "clock": now.strftime("%H:%M"),
            "date": f"{now.month} 月 {now.day} 日 {WEEKDAY_CN[now.isoweekday()]}",
            "paused": bool(self.app.paused),
            "current_title": "",
            "current_status": "",
            "status_color": "text_2",
            "progress": None,
            "next_text": "",
        }

        if current:
            entry, start_dt, end_dt = current[0]
            extra = f" 等 {len(current)} 项" if len(current) > 1 else ""
            data["current_title"] = (entry.title or "未命名") + extra
            if entry.point:
                overdue = max(0, int((now - start_dt).total_seconds() // 60))
                data["current_status"] = "到点了" if overdue < 1 else f"已过 {overdue} 分钟"
                data["status_color"] = "amber"
            else:
                remaining = max(0, int((end_dt - now).total_seconds() // 60))
                data["current_status"] = f"还剩 {remaining} 分钟"
                data["status_color"] = "green"
                total = max(1.0, (end_dt - start_dt).total_seconds())
                data["progress"] = min(1.0, max(0.0, 1 - (end_dt - now).total_seconds() / total))
        else:
            data["current_title"] = "当前无事项"

        upcoming = [row for row in next_upcoming(entries, now) if row[2] > now]
        if upcoming:
            entry, _fire_at, start_dt, _end_dt = min(upcoming, key=lambda row: row[2])
            if start_dt.date() == now.date():
                when = f"{start_dt:%H:%M}"
            elif start_dt.date() == now.date() + timedelta(days=1):
                when = f"明天 {start_dt:%H:%M}"
            else:
                when = f"{start_dt.month} 月 {start_dt.day} 日 {start_dt:%H:%M}"
            data["next_text"] = (
                f"{when}  {entry.title or '未命名'} · {humanize_delta((start_dt - now).total_seconds())}"
            )
        else:
            data["next_text"] = "接下来无事项"

        return data

    # ---------------------------------------------------------- 原生事件

    def _on_native_event(self, kind: str, payload) -> None:  # noqa: ANN001
        # 原生窗口在自己的线程里跑，所有事件都排队交给 Tk 线程处理。
        self.app.events.put((f"pet_{kind}", payload))

    def on_click(self) -> None:
        self.close_menu()
        self._hide_panel()
        self._window.blink()
        self.app.show_main()

    def on_moved(self, x: int, y: int) -> None:
        self.app.settings.pet_x = int(x)
        self.app.settings.pet_y = int(y)
        self.app.store.save()
        self._suppress_hover_until = time.monotonic() + 0.5

    def set_paused(self, value: bool) -> None:
        """暂停提醒时她闭眼打盹。"""
        window = getattr(self, "_window", None)
        if window is not None:
            window.set_paused(bool(value))
        if self._panel is not None and self._panel.visible:
            self._show_panel()

    # ---------------------------------------------------------- 菜单

    def show_menu(self, x: int, y: int) -> None:
        self.close_menu()
        self._hide_panel()
        items = [
            ("command", "打开时间表", self.app.show_main),
            ("command", "新建日程", lambda: (self.app.show_main(), self.app.new_entry())),
            ("sep",),
            ("check", "暂停提醒", self.app.paused, self.app.toggle_pause),
            ("check", "总在最前", bool(self.app.settings.pet_topmost), self.toggle_topmost),
            ("sep",),
            ("command", "放大一点（滚轮）", self.zoom_in),
            ("command", "缩小一点（滚轮）", self.zoom_out),
            ("command", f"大小 {int(round(self._scale * 100))}% · 恢复默认", self.reset_zoom),
            ("sep",),
            ("command", "隐藏小窗", lambda: self.app.set_pet_enabled(False)),
            ("command", "退出时间表", self.app.quit_app),
        ]
        self._menu = PetMenu(self.app.root, items, on_close=self._on_menu_closed)
        self._menu.post(x, y, bounds=self.app.virtual_screen())

    def _on_menu_closed(self) -> None:
        self._menu = None

    def close_menu(self) -> None:
        menu, self._menu = self._menu, None
        if menu is not None:
            menu.close()

    def toggle_topmost(self) -> None:
        value = not bool(self.app.settings.pet_topmost)
        self.app.settings.pet_topmost = value
        self.app.store.save()
        self._window.set_topmost(value)

    # ---------------------------------------------------------- 收尾

    def close(self) -> None:
        self.close_menu()
        self._cancel_enter()
        self._cancel_hide()
        self._hide_panel()
        if self._resize_job is not None:
            try:
                self.app.root.after_cancel(self._resize_job)
            except Exception:  # noqa: BLE001
                pass
            self._resize_job = None
        if self._panel is not None:
            try:
                self._panel.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._panel = None
        window, self._window = getattr(self, "_window", None), None
        if window is not None:
            window.close()

    @property
    def position(self) -> tuple[int, int]:
        window = getattr(self, "_window", None)
        return window.position if window is not None else (0, 0)
