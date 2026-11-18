"""桌面快捷方式（通过系统自带的 WScript.Shell，不引入额外依赖）。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import paths

CREATE_NO_WINDOW = 0x08000000
SHORTCUT_NAME = "时间表.lnk"


def desktop_dir() -> Path:
    return Path.home() / "Desktop"


def shortcut_path() -> Path:
    return desktop_dir() / SHORTCUT_NAME


def startup_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path() -> Path:
    return startup_dir() / SHORTCUT_NAME


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_shortcut_at(link_path: Path, extra_args: str = "") -> tuple[bool, str]:
    """在指定位置创建快捷方式（内部用系统自带的 WScript.Shell）。"""
    target = paths.pythonw()
    script = str(paths.entry_script())
    arguments = f'"{script}"'
    if extra_args:
        arguments += f" {extra_args}"
    workdir = str(paths.APP_DIR)
    icon = str(paths.ICON_PATH)

    ps = f"""
$ErrorActionPreference = 'Stop'
$link = {_ps_quote(str(link_path))}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = {_ps_quote(target)}
$shortcut.Arguments = {_ps_quote(arguments)}
$shortcut.WorkingDirectory = {_ps_quote(workdir)}
$shortcut.IconLocation = {_ps_quote(icon + ',0')}
$shortcut.Description = '时间表 - 日程提醒'
$shortcut.Save()
if (Test-Path -LiteralPath $link) {{ Write-Output 'OK' }} else {{ Write-Output 'MISSING' }}
"""
    try:
        link_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"创建快捷方式失败：{exc}"
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip().splitlines()
        detail = message[-1] if message else f"退出码 {result.returncode}"
        return False, f"创建快捷方式失败：{detail}"
    if "OK" not in (result.stdout or ""):
        return False, "创建快捷方式失败：系统没有返回成功。"
    return True, f"已创建快捷方式「{link_path.name}」"


def create_desktop_shortcut() -> tuple[bool, str]:
    ok, message = create_shortcut_at(shortcut_path())
    if ok:
        message = f"已在桌面创建「{SHORTCUT_NAME}」"
    return ok, message


def create_startup_shortcut() -> tuple[bool, str]:
    """把快捷方式放进「启动」文件夹，实现开机自启。"""
    link = startup_shortcut_path()
    ok, message = create_shortcut_at(link, extra_args="--tray")
    if ok:
        message = "已加入开机启动（启动文件夹）"
    elif link.exists():
        # 某些环境里 Shell 的返回码不可靠，文件确实在就算成功
        return True, "已加入开机启动（启动文件夹）"
    return ok, message


def open_folder(path: Path) -> None:
    try:
        subprocess.Popen(["explorer.exe", str(path)], creationflags=CREATE_NO_WINDOW)
    except OSError:
        pass
