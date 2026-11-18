"""时间表 —— 常驻托盘的日程提醒。

双击本文件即可启动（.pyw 不会弹黑框）。程序会自动开启开机自启，
登录后在右下角托盘待命，到点弹出提醒卡片。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import paths  # noqa: E402
from app.logs import setup  # noqa: E402
from app.single_instance import InstanceGuard  # noqa: E402


def main() -> int:
    logger = setup(paths.LOG_PATH)
    start_hidden = "--tray" in sys.argv
    guard = InstanceGuard()
    if not guard.acquire():
        # 已经有实例在运行：把它唤到前台，自己安静退出。
        guard.notify_existing()
        logger.info("检测到已有实例，已请求它显示主窗口")
        return 0
    from app.application import Application

    application = Application(guard, start_hidden=start_hidden)
    application.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - 启动期异常必须留下痕迹
        detail = traceback.format_exc()
        try:
            setup(paths.LOG_PATH).error("启动失败\n%s", detail)
        except Exception:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("时间表启动失败", detail[-1500:])
            root.destroy()
        except Exception:
            pass
        raise
