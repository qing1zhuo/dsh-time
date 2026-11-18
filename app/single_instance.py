"""单实例：第二次启动时把已经运行的窗口唤出来，而不是再开一个托盘图标。

用命名互斥体判断是否已有实例，比占用本地端口可靠——Windows 有时会保留
某些端口段，导致 bind 失败而被误判成「已经有一个实例在跑」。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

MUTEX_NAME = "Local\\TimetableReminder.SingleInstance"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL


class InstanceGuard:
    def __init__(self, window_title: str = "时间表") -> None:
        self.window_title = window_title
        self._mutex = None

    def acquire(self) -> bool:
        """抢占「唯一实例」；已有实例时返回 False。"""
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            # 创建失败就不拦着用户，宁可多开也不要打不开。
            return True
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._mutex = handle
        return True

    def notify_existing(self, timeout: float = 3.0) -> bool:
        """找到正在运行的主窗口并把它显示出来。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            hwnd = user32.FindWindowW(None, self.window_title)
            if hwnd:
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return True
            time.sleep(0.15)
        return False

    def listen(self, on_show) -> None:  # noqa: ANN001
        """兼容旧接口：现在不需要监听线程，唤醒由 notify_existing 完成。"""
        return None

    def close(self) -> None:
        if self._mutex:
            kernel32.CloseHandle(self._mutex)
            self._mutex = None
