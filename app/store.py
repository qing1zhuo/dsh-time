"""本地 JSON 存储。"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .model import DEFAULT_TERM_WEEKS, Entry

SCHEMA_VERSION = 2


def _clamp_int(value: Any, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


@dataclass
class Settings:
    sound_enabled: bool = True
    start_minimized: bool = True
    grace_minutes: int = 30
    first_run: bool = True
    autostart_choice: str = "auto"
    pet_enabled: bool = True
    pet_topmost: bool = True
    pet_scale: float = 1.0
    pet_x: int | None = None
    pet_y: int | None = None
    # 教学周：term_start 是第 1 周的周一（ISO 日期），空字符串表示还没设置
    term_start: str = ""
    term_weeks: int = DEFAULT_TERM_WEEKS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Settings":
        raw = raw or {}
        choice = str(raw.get("autostart_choice") or "auto")
        if choice not in ("auto", "on", "off"):
            choice = "auto"

        def optional_int(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def pet_scale(value: Any) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return 1.0
            if number != number:  # NaN
                return 1.0
            return max(0.6, min(1.8, round(number, 2)))

        return cls(
            sound_enabled=bool(raw.get("sound_enabled", True)),
            start_minimized=bool(raw.get("start_minimized", True)),
            grace_minutes=_clamp_int(raw.get("grace_minutes"), default=30, minimum=1),
            first_run=bool(raw.get("first_run", True)),
            autostart_choice=choice,
            pet_enabled=bool(raw.get("pet_enabled", True)),
            pet_topmost=bool(raw.get("pet_topmost", True)),
            pet_scale=pet_scale(raw.get("pet_scale", 1.0)),
            pet_x=optional_int(raw.get("pet_x")),
            pet_y=optional_int(raw.get("pet_y")),
            term_start=str(raw.get("term_start") or ""),
            term_weeks=_clamp_int(
                raw.get("term_weeks"), default=DEFAULT_TERM_WEEKS, minimum=1, maximum=52
            ),
        )


@dataclass
class Store:
    path: Path
    entries: list[Entry] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    last_error: str = ""

    # -- 读写 ---------------------------------------------------------

    def load(self) -> None:
        self.entries = []
        self.settings = Settings()
        self.last_error = ""
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.last_error = f"读取数据失败：{exc}"
            self._backup_broken_file()
            return
        if not isinstance(raw, dict):
            self.last_error = "数据文件格式不对，已忽略。"
            return
        self.settings = Settings.from_dict(raw.get("settings"))
        for item in raw.get("entries") or []:
            if isinstance(item, dict):
                entry = Entry.from_dict(item)
                entry.prune_fired()
                self.entries.append(entry)
        self.sort_entries()

    def _backup_broken_file(self) -> None:
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.path, self.path.with_name(f"schedule.broken-{stamp}.json"))
        except OSError:
            pass

    def save(self) -> bool:
        payload = {
            "version": SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "settings": self.settings.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(self.path.parent), prefix=".schedule-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, self.path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            self.last_error = ""
            return True
        except OSError as exc:
            self.last_error = f"保存失败：{exc}"
            return False

    # -- 增删改 -------------------------------------------------------

    def get(self, entry_id: str) -> Entry | None:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def upsert(self, entry: Entry) -> None:
        for index, existing in enumerate(self.entries):
            if existing.id == entry.id:
                self.entries[index] = entry
                break
        else:
            self.entries.append(entry)
        self.sort_entries()

    def delete(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [entry for entry in self.entries if entry.id != entry_id]
        return len(self.entries) != before

    def sort_entries(self) -> None:
        now = datetime.now()
        self.entries.sort(key=lambda entry: (not entry.enabled, entry.sort_key(now), entry.title))

    def enabled_entries(self) -> list[Entry]:
        return [entry for entry in self.entries if entry.enabled]
