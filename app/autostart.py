"""开机自启。

双重保险：
1. 「启动」文件夹里的快捷方式（%APPDATA%\\...\\Startup\\时间表.lnk）——最直观，
   在任务管理器的「启动应用」里能看到，也不受组策略限制 Run 键的影响；
2. 当前用户的 Run 注册表项（HKCU\\...\\Run\\TimetableReminder）——传统方式。

两者只要有一个成功就算开启；关闭时两个都会清掉。
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from . import paths, shortcuts

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TimetableReminder"


# ---------------------------------------------------------------- 注册表


def current_command() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value)
    except (FileNotFoundError, OSError):
        return None


def _enable_registry() -> tuple[bool, str]:
    command = paths.startup_command()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        return True, "已写入注册表启动项"
    except OSError as exc:
        return False, f"写入注册表失败：{exc}"


def _disable_registry() -> tuple[bool, str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        return True, "已删除注册表启动项"
    except FileNotFoundError:
        return True, "注册表启动项本来就不存在"
    except OSError as exc:
        return False, f"删除注册表启动项失败：{exc}"


# ---------------------------------------------------------------- 启动文件夹


def startup_shortcut() -> Path:
    return shortcuts.startup_shortcut_path()


# ---------------------------------------------------------------- 对外接口


def is_enabled() -> bool:
    if startup_shortcut().exists():
        return True
    return bool(current_command())


def matches_current_install() -> bool:
    """注册表里的命令是否指向当前这份程序（换过目录时需要修正）。"""
    command = current_command()
    if not command:
        return False
    return command.strip().lower() == paths.startup_command().strip().lower()


def enable() -> tuple[bool, str]:
    shortcut_ok, shortcut_message = shortcuts.create_startup_shortcut()
    registry_ok, registry_message = _enable_registry()
    if shortcut_ok or registry_ok:
        detail = "启动文件夹 + 注册表" if (shortcut_ok and registry_ok) else (
            "启动文件夹" if shortcut_ok else "注册表"
        )
        return True, f"已开启开机自启（{detail}）"
    return False, f"开启失败：{shortcut_message}；{registry_message}"


def disable() -> tuple[bool, str]:
    removed_shortcut = False
    path = startup_shortcut()
    try:
        if path.exists():
            path.unlink()
            removed_shortcut = True
    except OSError as exc:
        return False, f"删除启动文件夹快捷方式失败：{exc}"
    registry_ok, registry_message = _disable_registry()
    if removed_shortcut or registry_ok:
        return True, "已关闭开机自启"
    return False, registry_message


def set_enabled(enabled: bool) -> tuple[bool, str]:
    if enabled:
        return enable()
    return disable()


def python_is_console() -> bool:
    return sys.executable.lower().endswith("python.exe")
