"""滚轮滚动性能自检：模拟滚轮事件，测量滚动距离与耗时。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from app import theme  # noqa: E402
from app.theme import COLORS, font, px  # noqa: E402
from app.widgets import ScrollFrame  # noqa: E402


def main() -> int:
    theme.enable_dpi_awareness()
    root = tk.Tk()
    root.geometry(f"{px(760)}x{px(560)}")
    theme.init(root)
    theme.setup_ttk(root)

    frame = ScrollFrame(root, bg=COLORS["bg"])
    frame.pack(fill="both", expand=True, padx=px(20), pady=px(20))

    for index in range(15):
        card = tk.Frame(
            frame.body,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        card.pack(fill="x", pady=(0, px(10)))
        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=px(16), pady=px(14))
        tk.Label(
            inner,
            text=f"第 {index + 1} 条日程",
            font=font(12, "bold"),
            bg=COLORS["surface"],
            fg=COLORS["text"],
        ).pack(anchor="w")
        for line in range(3):
            tk.Label(
                inner,
                text=f"备注第 {line + 1} 行，用来模拟真实卡片里的子控件",
                font=font(9),
                bg=COLORS["surface"],
                fg=COLORS["text_3"],
            ).pack(anchor="w")

    root.update_idletasks()
    root.update()

    target = frame.body.winfo_children()[0].winfo_children()[0].winfo_children()[0]
    total = float(frame.canvas.cget("scrollregion").split()[3])
    start = frame.canvas.yview()[0] * total
    started = time.perf_counter()
    for _ in range(30):
        target.event_generate("<MouseWheel>", delta=-120)
        root.update()
    elapsed = time.perf_counter() - started
    end = frame.canvas.yview()[0] * total

    print(f"15 张卡片，30 次向下滚轮：耗时 {elapsed * 1000:.1f} ms")
    print(f"滚动距离 {end - start:.0f} px，平均每个滚轮 {abs(end - start) / 30:.0f} px")
    print(f"平均每次事件 {elapsed * 1000 / 30:.2f} ms")
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
