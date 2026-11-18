"""日志：pythonw 没有控制台，出问题只能靠文件。"""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "timetable"


def setup(path: Path) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    def handle_exception(exc_type, exc_value, exc_tb):  # noqa: ANN001
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logger.error("未捕获的异常\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    sys.excepthook = handle_exception
    return logger


def get() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
