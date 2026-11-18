"""生命周期自检：启动 → 关闭窗口（缩到托盘）→ 二次启动唤醒 → 退出。

用法：python tools/test_lifecycle.py
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.paths import entry_script, pythonw  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.c_void_p
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
WM_CLOSE = 0x0010

results: list[bool] = []


def check(condition: bool, message: str) -> None:
    results.append(bool(condition))
    print(("  ok   " if condition else "  FAIL ") + message)


def window_handle() -> int:
    return user32.FindWindowW(None, "时间表") or 0


def wait_for(predicate, timeout: float = 8.0, interval: float = 0.2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def spawn() -> subprocess.Popen:
    return subprocess.Popen(
        [pythonw(), str(entry_script())],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    print("启动第一个实例：")
    first = spawn()
    visible = wait_for(lambda: window_handle() and user32.IsWindowVisible(window_handle()))
    check(bool(visible), "主窗口出现")
    hwnd = window_handle()
    check(bool(hwnd), "能找到窗口句柄")

    print("关闭主窗口（应缩到托盘而不是退出）：")
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    hidden = wait_for(lambda: not user32.IsWindowVisible(hwnd), timeout=5)
    check(hidden, "窗口已隐藏")
    check(first.poll() is None, "进程仍在运行")

    print("再次双击（应唤醒已有窗口，而不是开第二个）：")
    second = spawn()
    shown = wait_for(lambda: user32.IsWindowVisible(hwnd), timeout=8)
    check(shown, "原窗口被唤醒")
    check(second.poll() is not None, "第二个实例已自行退出")

    print("清理：")
    if first.poll() is None:
        first.terminate()
        try:
            first.wait(timeout=5)
        except subprocess.TimeoutExpired:
            first.kill()
    check(first.poll() is not None, "第一个实例已退出")

    print()
    if all(results):
        print(f"全部通过（{len(results)} 项）")
        return 0
    print(f"失败 {results.count(False)} 项")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
