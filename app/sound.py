"""提示音。"""

from __future__ import annotations

import winsound


def play_reminder() -> None:
    """播放系统提示音，不阻塞界面。"""
    try:
        winsound.PlaySound(
            "SystemExclamation",
            winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
        return
    except RuntimeError:
        pass
    try:
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except RuntimeError:
        pass
