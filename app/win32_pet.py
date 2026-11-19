"""桌宠窗口：一个 Win32 分层窗口（Layered Window）。

和普通 Tk 窗口的区别：
- 逐像素透明，PNG 的柔和边缘不会在壁纸上留下色边；
- 完全透明的像素不接收鼠标，点在裙摆外面等于点在桌面上；
- 不抢焦点（WS_EX_NOACTIVATE），点她不会把别的窗口切走。

窗口跑在自己的线程里，Tk 那边只通过回调 + 事件队列和它打交道。
"""

from __future__ import annotations

import ctypes
import os
import random
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------- 常量

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_MOUSELEAVE = 0x02A3
WM_MOUSEACTIVATE = 0x0021
WM_SETCURSOR = 0x0020
WM_APP = 0x8000
WM_APP_TOPMOST = WM_APP + 1
WM_APP_BLINK = WM_APP + 2
WM_APP_PAUSED = WM_APP + 3
WM_APP_RESIZE = WM_APP + 4
TME_LEAVE = 0x00000002
MA_NOACTIVATE = 3
HTCLIENT = 1

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

IDC_HAND = 32649
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SPI_GETWORKAREA = 0x0030

DIB_RGB_COLORS = 0
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

BLINK_TIMER = 1
BLINK_MS = 120


# ---------------------------------------------------------------- 结构体


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("hwndTrack", wintypes.HWND),
        ("dwHoverTime", wintypes.DWORD),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
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
        ("hIconSm", wintypes.HICON),
    ]


# ---------------------------------------------------------------- API 签名

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetCapture.argtypes = [wintypes.HWND]
user32.SetCapture.restype = wintypes.HWND
user32.ReleaseCapture.argtypes = []
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND,
    wintypes.HDC,
    ctypes.POINTER(POINT),
    ctypes.POINTER(SIZE),
    wintypes.HDC,
    ctypes.POINTER(POINT),
    wintypes.COLORREF,
    ctypes.POINTER(BLENDFUNCTION),
    wintypes.DWORD,
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = ctypes.c_void_p
user32.SetCursor.argtypes = [ctypes.c_void_p]
user32.SetCursor.restype = ctypes.c_void_p
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
user32.SystemParametersInfoW.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]
user32.TrackMouseEvent.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]


def premultiply(image) -> tuple[int, int, bytes]:  # noqa: ANN001 - PIL.Image
    """RGBA -> Windows 需要的预乘 alpha BGRA。

    Pillow 的 "RGBa" 模式就是预乘 alpha，转一次比逐像素乘快两个数量级。
    """
    from PIL import Image

    image = image.convert("RGBA")
    premultiplied = image.convert("RGBa")
    red, green, blue, alpha = premultiplied.split()
    # 通道按 B,G,R,A 的顺序写出来，正好是 Windows 要的 BGRA 内存布局
    return image.width, image.height, Image.merge("RGBA", (blue, green, red, alpha)).tobytes()


class PetWindow:
    """一只站在桌面上的鲸鱼娘。

    frames: [(width, height, premultiplied BGRA bytes), ...]，第一帧为常态。
    """

    CLASS_NAME = f"TimetablePetWindow_{os.getpid()}"

    def __init__(self, frames, x: int, y: int, topmost: bool = True, on_event=None) -> None:  # noqa: ANN001
        if not frames:
            raise ValueError("桌宠至少需要一帧")
        self._frames = frames
        self._width, self._height = frames[0][0], frames[0][1]
        self._x = int(x)
        self._y = int(y)
        self._topmost = bool(topmost)
        self._on_event = on_event or (lambda kind, payload=None: None)

        self._hwnd: int | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._closing = False

        # 只在这一条线程里使用
        self._frame_index = 0
        self._paused = False
        self._tracking = False
        self._pending_frames = None
        self._next_blink = 0.0
        self._blink_until = 0.0
        self._double_blink = False
        self._dragging = False
        self._drag_moved = False
        self._drag_origin = (0, 0)
        self._window_origin = (self._x, self._y)
        self._screen_dc = None
        self._mem_dc = None
        self._dib = None
        self._bits = None
        self._old_bitmap = None
        self._cursor = None
        self._wndproc = None

    # ------------------------------------------------------------ 生命周期

    def start(self, timeout: float = 6.0) -> bool:
        self._thread = threading.Thread(target=self._run, name="pet-window", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("桌宠窗口创建超时")
        if self._error is not None:
            raise RuntimeError(f"桌宠窗口创建失败：{self._error}")
        return self._hwnd is not None

    def close(self) -> None:
        if self._hwnd:
            self._closing = True
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._hwnd = None

    def set_topmost(self, value: bool) -> None:
        self._topmost = bool(value)
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_APP_TOPMOST, 1 if value else 0, 0)

    def blink(self) -> None:
        """被戳一下时眨个眼。"""
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_APP_BLINK, 0, 0)

    def set_paused(self, value: bool) -> None:
        """暂停提醒时闭眼打盹，恢复后接着眨眼。"""
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_APP_PAUSED, 1 if value else 0, 0)

    def resize(self, frames, keep_bottom: bool = True) -> None:
        """换一组尺寸不同的帧；keep_bottom 让脚底位置不动。"""
        if not frames:
            return
        self._pending_frames = (frames, bool(keep_bottom))
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_APP_RESIZE, 0, 0)

    @property
    def position(self) -> tuple[int, int]:
        return self._x, self._y

    @property
    def size(self) -> tuple[int, int]:
        return self._width, self._height

    # ------------------------------------------------------------ 线程内部

    def _run(self) -> None:
        try:
            self._create_window()
        except BaseException as exc:  # noqa: BLE001
            self._error = exc
            self._ready.set()
            return
        self._ready.set()
        hwnd = self._hwnd
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self._cleanup(hwnd)

    def _create_window(self) -> None:
        class_name = self.CLASS_NAME
        self._wndproc = WNDPROC(self._window_proc)
        instance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = instance
        wc.hCursor = 0
        wc.lpszClassName = class_name
        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            error = ctypes.get_last_error()
            if error != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise OSError(0, f"RegisterClassExW 失败（{error}）")

        ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if self._topmost:
            ex_style |= WS_EX_TOPMOST
        self._x, self._y = self._clamp(self._x, self._y)
        hwnd = user32.CreateWindowExW(
            ex_style,
            class_name,
            "时间表小窗",
            WS_POPUP | WS_VISIBLE,
            self._x,
            self._y,
            self._width,
            self._height,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            raise OSError(0, f"CreateWindowExW 失败（{ctypes.get_last_error()}）")
        self._hwnd = hwnd

        self._prepare_surface()
        self._blit(self._frames[0][2])
        self._cursor = user32.LoadCursorW(None, IDC_HAND)
        user32.SetTimer(hwnd, BLINK_TIMER, 80, None)

        now = time.monotonic()
        self._next_blink = now + random.uniform(2.0, 5.0)

    def _prepare_surface(self) -> None:
        self._screen_dc = user32.GetDC(None)
        self._mem_dc = gdi32.CreateCompatibleDC(self._screen_dc)

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = self._width
        info.bmiHeader.biHeight = -self._height  # 负高度 = 从上往下的行序
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB

        bits = ctypes.c_void_p()
        self._dib = gdi32.CreateDIBSection(
            self._screen_dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not self._dib:
            raise OSError(0, f"CreateDIBSection 失败（{ctypes.get_last_error()}）")
        self._bits = bits
        self._old_bitmap = gdi32.SelectObject(self._mem_dc, self._dib)

    def _blit(self, data: bytes) -> None:
        ctypes.memmove(self._bits, data, len(data))
        destination = POINT(self._x, self._y)
        size = SIZE(self._width, self._height)
        source = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(
            self._hwnd,
            self._screen_dc,
            ctypes.byref(destination),
            ctypes.byref(size),
            self._mem_dc,
            ctypes.byref(source),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        if not ok:
            raise OSError(0, f"UpdateLayeredWindow 失败（{ctypes.get_last_error()}）")

    def _set_frame(self, index: int) -> None:
        if index == self._frame_index or index >= len(self._frames):
            return
        self._frame_index = index
        self._blit(self._frames[index][2])

    def _release_surface(self) -> None:
        if self._mem_dc and self._old_bitmap:
            gdi32.SelectObject(self._mem_dc, self._old_bitmap)
            self._old_bitmap = None
        if self._dib:
            gdi32.DeleteObject(self._dib)
            self._dib = None
        if self._mem_dc:
            gdi32.DeleteDC(self._mem_dc)
            self._mem_dc = None
        if self._screen_dc:
            user32.ReleaseDC(None, self._screen_dc)
            self._screen_dc = None

    def _apply_resize(self) -> None:
        pending = self._pending_frames
        if not pending:
            return
        self._pending_frames = None
        frames, keep_bottom = pending
        old_height = self._height
        self._frames = frames
        self._width, self._height = frames[0][0], frames[0][1]
        if keep_bottom:
            self._y += old_height - self._height
        self._frame_index = 1 if self._paused else 0
        self._release_surface()
        self._prepare_surface()
        self._x, self._y = self._clamp(self._x, self._y)
        self._blit(self._frames[self._frame_index][2])

    def _cleanup(self, hwnd=None) -> None:  # noqa: ANN001
        if hwnd:
            user32.KillTimer(hwnd, BLINK_TIMER)
        self._release_surface()

    # ------------------------------------------------------------ 窗口过程

    def _window_proc(self, hwnd, msg, wparam, lparam):  # noqa: ANN001
        try:
            if msg == WM_TIMER:
                self._on_timer()
                return 0
            if msg == WM_MOUSEACTIVATE:
                return MA_NOACTIVATE
            if msg == WM_SETCURSOR:
                if LOWORD(lparam) == HTCLIENT and self._cursor:
                    user32.SetCursor(self._cursor)
                    return 1
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
            if msg == WM_LBUTTONDOWN:
                self._begin_drag()
                return 0
            if msg == WM_MOUSEMOVE:
                if not self._tracking:
                    self._track_leave()
                    self._emit("enter", None)
                self._continue_drag()
                return 0
            if msg == WM_MOUSELEAVE:
                self._tracking = False
                self._emit("leave", None)
                return 0
            if msg == WM_LBUTTONUP:
                self._end_drag()
                return 0
            if msg == WM_RBUTTONUP:
                self._emit("menu", self._cursor_pos())
                return 0
            if msg == WM_MOUSEWHEEL:
                delta = ctypes.c_short((int(wparam) >> 16) & 0xFFFF).value
                self._emit("wheel", int(delta))
                return 0
            if msg == WM_APP_RESIZE:
                self._apply_resize()
                return 0
            if msg == WM_APP_TOPMOST:
                self._apply_topmost(bool(wparam))
                return 0
            if msg == WM_APP_BLINK:
                if not self._paused:
                    self._set_frame(1)
                    self._blink_until = time.monotonic() + BLINK_MS / 1000.0
                return 0
            if msg == WM_APP_PAUSED:
                self._apply_paused(bool(wparam))
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001 - 回调里不能抛异常
            self._emit("error", None)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _on_timer(self) -> None:
        if self._paused:
            return
        now = time.monotonic()
        if self._frame_index == 0:
            if now >= self._next_blink:
                self._set_frame(1)
                self._blink_until = now + BLINK_MS / 1000.0
        elif now >= self._blink_until:
            self._set_frame(0)
            if self._double_blink:
                self._double_blink = False
                self._next_blink = now + 0.16
            else:
                self._next_blink = now + random.uniform(2.2, 6.5)
                if random.random() < 0.18:
                    self._double_blink = True

    def _apply_paused(self, value: bool) -> None:
        self._paused = value
        if value:
            self._set_frame(1)
        else:
            self._set_frame(0)
            self._next_blink = time.monotonic() + random.uniform(1.5, 4.0)

    def _apply_topmost(self, value: bool) -> None:
        self._topmost = value
        if not self._hwnd:
            return
        user32.SetWindowPos(
            self._hwnd,
            HWND_TOPMOST if value else HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def _begin_drag(self) -> None:
        point = self._cursor_pos()
        self._drag_origin = point
        self._window_origin = (self._x, self._y)
        self._dragging = True
        self._drag_moved = False
        self._emit("dragstart", None)
        user32.SetCapture(self._hwnd)

    def _track_leave(self) -> None:
        """让系统在鼠标离开时发 WM_MOUSELEAVE，好收起信息卡。"""
        track = TRACKMOUSEEVENT()
        track.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
        track.dwFlags = TME_LEAVE
        track.hwndTrack = self._hwnd
        try:
            user32.TrackMouseEvent(ctypes.byref(track))
            self._tracking = True
        except Exception:  # noqa: BLE001
            self._tracking = False

    def _continue_drag(self) -> None:
        if not self._dragging:
            return
        point = self._cursor_pos()
        dx = point[0] - self._drag_origin[0]
        dy = point[1] - self._drag_origin[1]
        if not self._drag_moved and abs(dx) + abs(dy) >= 4:
            self._drag_moved = True
        if not self._drag_moved:
            return
        x, y = self._clamp(self._window_origin[0] + dx, self._window_origin[1] + dy)
        self._x, self._y = x, y
        user32.SetWindowPos(self._hwnd, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER)

    def _end_drag(self) -> None:
        if not self._dragging:
            return
        self._dragging = False
        user32.ReleaseCapture()
        if self._drag_moved:
            self._emit("moved", (self._x, self._y))
        else:
            self._emit("click", None)

    def _cursor_pos(self) -> tuple[int, int]:
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if width <= 0 or height <= 0:
            left, top = 0, 0
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        right = left + width
        bottom = top + height

        work = RECT()
        has_work = bool(
            user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0)
        )
        lower = bottom
        if has_work and x + self._width > work.left and x < work.right:
            lower = min(lower, work.bottom)
        x = max(left, min(int(x), right - self._width))
        y = max(top, min(int(y), lower - self._height))
        return x, y

    def _emit(self, kind: str, payload) -> None:  # noqa: ANN001
        try:
            self._on_event(kind, payload)
        except Exception:  # noqa: BLE001
            pass


def LOWORD(value: int) -> int:
    return int(value) & 0xFFFF
