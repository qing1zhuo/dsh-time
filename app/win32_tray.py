"""Windows 通知区域（托盘）图标：纯 ctypes 实现，无需 pywin32 / pystray。

托盘在独立线程里跑自己的消息循环，事件通过队列交给 Tk 主线程处理。
"""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable

log = logging.getLogger("timetable.tray")

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_APP = 0x8000
WM_TRAY = WM_APP + 20
WM_NULL = 0x0000
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
NIN_SELECT = 0x0400  # WM_USER + 0
NIN_KEYSELECT = 0x0401  # WM_USER + 1

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIM_SETVERSION = 4
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIF_SHOWTIP = 0x00000080
NIIF_INFO = 0x00000001
NIIF_NOSOUND = 0x00000010

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
SM_CXSMICON = 49
SM_CYSMICON = 50

MF_STRING = 0x00000000
MF_GRAYED = 0x00000001
MF_CHECKED = 0x00000008
MF_SEPARATOR = 0x00000800
TPM_LEFTALIGN = 0x0000
TPM_BOTTOMALIGN = 0x0020
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
IDI_APPLICATION = 32512

TRAY_UID = 1
WINDOW_CLASS = "TimetableTrayWindowV1"

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL
user32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.TrackPopupMenuEx.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.LPVOID
]
user32.TrackPopupMenuEx.restype = ctypes.c_int
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


class TrayIcon:
    """通知区域图标。

    events: 事件队列，元素为 ("activate"|"command"|"menu", payload)
    menu_source: 返回菜单项列表的回调，在托盘线程中被调用，需自行加锁。
    """

    def __init__(
        self,
        icon_path: Path,
        events: "queue.Queue[tuple[str, object]]",
        menu_source: Callable[[], list[dict]],
        tooltip: str = "时间表",
    ) -> None:
        self._icon_path = Path(icon_path)
        self._events = events
        self._menu_source = menu_source
        self._tooltip = tooltip[:127]
        self._hwnd: int | None = None
        self._hicon = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._wndproc = WNDPROC(self._handle_message)
        self._taskbar_created = 0
        self._menu_lock = threading.Lock()
        self._tooltip_lock = threading.Lock()
        self._add_failures = 0
        self._stopping = False
        self.added = False

    # ---------------------------------------------------------- 生命周期

    def start(self, timeout: float = 6.0) -> bool:
        self._thread = threading.Thread(target=self._run, name="timetable-tray", daemon=True)
        self._thread.start()
        return self._ready.wait(timeout)

    def stop(self) -> None:
        self._stopping = True
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(3.0)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ---------------------------------------------------------- 线程内部

    def _run(self) -> None:
        try:
            self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
            self._register_class()
            self._create_window()
            self._load_icon()
            self._add_icon()
        except Exception:
            self._ready.set()
            return
        self._ready.set()

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        if self._hicon:
            user32.DestroyIcon(self._hicon)
            self._hicon = None

    def _register_class(self) -> None:
        instance = kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASSW()
        wndclass.style = 0
        wndclass.lpfnWndProc = self._wndproc
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hInstance = instance
        wndclass.hIcon = None
        wndclass.hCursor = None
        wndclass.hbrBackground = None
        wndclass.lpszMenuName = None
        wndclass.lpszClassName = WINDOW_CLASS
        user32.RegisterClassW(ctypes.byref(wndclass))
        # 已注册（例如上一个实例还没退干净）不算错误，继续即可。

    def _create_window(self) -> None:
        instance = kernel32.GetModuleHandleW(None)
        self._hwnd = user32.CreateWindowExW(
            0,
            WINDOW_CLASS,
            "TimetableTray",
            0x80000000,  # WS_POPUP
            0, 0, 0, 0,
            None, None, instance, None,
        )
        if not self._hwnd:
            raise OSError(f"CreateWindowExW failed: {ctypes.get_last_error()}")

    def _load_icon(self) -> None:
        size = user32.GetSystemMetrics(SM_CXSMICON) or 16
        handle = user32.LoadImageW(
            None, str(self._icon_path), IMAGE_ICON, size, size, LR_LOADFROMFILE
        )
        if not handle:
            handle = user32.LoadIconW(None, ctypes.c_wchar_p(IDI_APPLICATION))
        self._hicon = handle or None

    def _base_data(self) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = TRAY_UID
        return data

    def _add_icon(self) -> bool:
        data = self._base_data()
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self._hicon
        data.szTip = self._tooltip
        ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)))
        self.added = ok
        if ok:
            version = self._base_data()
            version.uVersion = 4
            shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(version))
            self._add_failures = 0
            log.info("托盘图标已添加")
        else:
            self._add_failures += 1
            log.warning("添加托盘图标失败（第 %s 次）", self._add_failures)
            if self._add_failures < 8 and not self._stopping:
                # 登录初期 Explorer 可能还没准备好，稍后重试。
                timer = threading.Timer(2.0, self._add_icon)
                timer.daemon = True
                timer.start()
        return ok

    def _delete_icon(self) -> None:
        if not self._hwnd:
            return
        data = self._base_data()
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))

    # ---------------------------------------------------------- 消息处理

    def _handle_message(self, hwnd, msg, wparam, lparam):  # noqa: ANN001
        if msg == WM_TRAY:
            event = int(lparam) & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, NIN_SELECT, NIN_KEYSELECT):
                self._emit("activate", None)
            elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._show_menu(hwnd)
            return 0
        if msg == self._taskbar_created and self._taskbar_created:
            log.info("Explorer 重新启动，重新挂上托盘图标")
            self._add_icon()
            return 0
        if msg == WM_CLOSE:
            self._delete_icon()
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _emit(self, kind: str, payload: object) -> None:
        try:
            self._events.put_nowait((kind, payload))
        except queue.Full:
            pass

    def _show_menu(self, hwnd) -> None:
        if not self._menu_lock.acquire(timeout=1.0):
            return
        try:
            items = self._menu_source() or []
            menu = user32.CreatePopupMenu()
            if not menu:
                return
            try:
                for item in items:
                    if item.get("kind") == "sep":
                        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                        continue
                    flags = MF_STRING
                    if not item.get("enabled", True):
                        flags |= MF_GRAYED
                    if item.get("checked"):
                        flags |= MF_CHECKED
                    command_id = int(item["id"])
                    user32.AppendMenuW(menu, flags, command_id, str(item.get("label", "")))
                    if item.get("default"):
                        user32.SetMenuDefaultItem(menu, command_id, 0)
                point = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(point))
                user32.SetForegroundWindow(hwnd)
                command = user32.TrackPopupMenuEx(
                    menu,
                    TPM_LEFTALIGN | TPM_BOTTOMALIGN | TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                    point.x,
                    point.y,
                    hwnd,
                    None,
                )
                user32.PostMessageW(hwnd, WM_NULL, 0, 0)
            finally:
                user32.DestroyMenu(menu)
            if command:
                self._emit("command", int(command))
        finally:
            self._menu_lock.release()

    # ---------------------------------------------------------- 对外操作

    def set_tooltip(self, text: str) -> None:
        self._tooltip = text[:127]
        if not self._hwnd:
            return
        data = self._base_data()
        data.uFlags = NIF_TIP | NIF_SHOWTIP
        data.szTip = self._tooltip
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def notify(self, title: str, message: str) -> None:
        if not self._hwnd:
            return
        data = self._base_data()
        data.uFlags = NIF_INFO | NIF_ICON
        data.hIcon = self._hicon
        data.szInfoTitle = title[:63]
        data.szInfo = message[:255]
        data.dwInfoFlags = NIIF_INFO | NIIF_NOSOUND
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def refresh_icon(self) -> None:
        """Explorer 重启后重新挂上图标。"""
        self._load_icon()
        self._add_icon()
