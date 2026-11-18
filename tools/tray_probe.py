"""托盘自检：注册一个托盘图标，报告是否成功，然后移除。"""

from __future__ import annotations

import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import paths  # noqa: E402
from app.win32_tray import TrayIcon  # noqa: E402


def main() -> int:
    events: queue.Queue = queue.Queue()
    tray = TrayIcon(paths.ICON_PATH, events, lambda: [{"id": 1, "label": "自检"}], "时间表自检")
    tray.start()
    time.sleep(2.5)
    print(f"tray.added={tray.added} alive={tray.alive}")
    if tray.added:
        tray.notify("时间表自检", "如果你在右下角看到这个图标，说明托盘正常。")
        time.sleep(0.5)
    tray.stop()
    return 0 if tray.added else 3


if __name__ == "__main__":
    raise SystemExit(main())
