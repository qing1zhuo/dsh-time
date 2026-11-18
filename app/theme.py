"""视觉主题：配色、字体、DPI 缩放、ttk 样式。"""

from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import font as tkfont, ttk

# ------------------------------------------------------------------ 配色

COLORS = {
    "bg": "#F3F5FA",
    "bg_alt": "#EAEEF7",
    "surface": "#FFFFFF",
    "surface_2": "#F7F9FD",
    "border": "#E7EBF3",
    "border_strong": "#D5DCEA",
    "text": "#161D2E",
    "text_2": "#5A6578",
    "text_3": "#98A2B3",
    "accent": "#3B6CF6",
    "accent_hover": "#2F5CE0",
    "accent_press": "#2448BC",
    "accent_soft": "#EBF1FF",
    "accent_ink": "#1F47B8",
    "green": "#0E9F6E",
    "green_soft": "#E4F6EF",
    "amber": "#C2740A",
    "amber_soft": "#FDF1E0",
    "red": "#DC2626",
    "red_soft": "#FDECEC",
    "purple": "#7C5CFA",
    "purple_soft": "#F0ECFF",
    "white": "#FFFFFF",
    "shadow": "#DCE2EE",
}

SCALE = 1.0
FAMILY = "Microsoft YaHei UI"
FAMILY_MONO = "Consolas"


def enable_dpi_awareness() -> None:
    """让 Tk 按物理像素绘制，避免在高分屏上变成模糊的位图放大。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def init(root: tk.Misc) -> None:
    """在创建 Tk 之后调用一次：测量 DPI、挑选中文字体。"""
    global SCALE, FAMILY
    try:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except Exception:
        SCALE = 1.0
    try:
        available = set(tkfont.families(root))
    except Exception:
        available = set()
    for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", "Arial"):
        if candidate in available:
            FAMILY = candidate
            break


def px(value: float) -> int:
    """把 96dpi 下的设计像素换算成当前 DPI 的像素。"""
    return int(round(value * SCALE))


def font(size: int = 10, weight: str = "normal", slant: str = "roman", family: str | None = None) -> tuple:
    return (family or FAMILY, size, weight, slant)


def round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, radius: float, **kwargs) -> int:
    """在 Canvas 上画圆角矩形（返回 item id）。"""
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


def setup_ttk(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "TCombobox",
        fieldbackground=COLORS["surface"],
        background=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border_strong"],
        lightcolor=COLORS["border_strong"],
        darkcolor=COLORS["border_strong"],
        arrowcolor=COLORS["text_2"],
        arrowsize=px(11),
        padding=(px(6), px(4)),
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["surface"])],
        bordercolor=[("focus", COLORS["accent"]), ("hover", COLORS["border_strong"])],
        arrowcolor=[("hover", COLORS["text"])],
    )
    style.configure(
        "TScrollbar",
        troughcolor=COLORS["bg"],
        background=COLORS["border_strong"],
        bordercolor=COLORS["bg"],
        arrowcolor=COLORS["text_3"],
        arrowsize=px(10),
        width=px(9),
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", COLORS["text_3"])])

    root.option_add("*TCombobox*Listbox.font", f"{{{FAMILY}}} 10")
    root.option_add("*TCombobox*Listbox.background", COLORS["surface"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["white"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
