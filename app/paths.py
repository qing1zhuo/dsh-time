"""统一管理运行期路径。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TimetableReminder"
APP_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = APP_DIR / "assets"
ICON_PATH = ASSETS_DIR / "app.ico"

_APPDATA_FALLBACK = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME


def _pick_data_dir() -> Path:
    """优先使用程序目录下的 data/，这样整个文件夹拷走即可带走数据。

    如果程序目录不可写（例如放进了 Program Files），退回 %APPDATA%。
    """
    candidate = APP_DIR / "data"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return candidate
    except OSError:
        pass
    try:
        _APPDATA_FALLBACK.mkdir(parents=True, exist_ok=True)
        return _APPDATA_FALLBACK
    except OSError:
        return Path(os.environ.get("TEMP", "."))


DATA_DIR = _pick_data_dir()
STORE_PATH = DATA_DIR / "schedule.json"
LOG_PATH = DATA_DIR / "app.log"


def entry_script() -> Path:
    """用于开机自启的入口脚本。"""
    return APP_DIR / "timetable.pyw"


def pythonw() -> str:
    """返回 pythonw.exe，避免开机自启时闪出黑色控制台窗口。"""
    exe = Path(sys.executable)
    name = exe.name.lower()
    if name == "pythonw.exe":
        return str(exe)
    if name in ("python.exe", "python3.exe", "pyw.exe", "py.exe"):
        candidate = exe.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
        candidate = Path(sys.exec_prefix) / "pythonw.exe"
        if candidate.exists():
            return str(candidate)
    return str(exe)


def startup_command() -> str:
    return f'"{pythonw()}" "{entry_script()}" --tray'
