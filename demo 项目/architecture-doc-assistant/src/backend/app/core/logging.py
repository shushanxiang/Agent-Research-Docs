"""
日志配置
========
统一日志格式，支持控制台 + 文件输出，JSON 结构化日志。
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
)


def setup_logging(level: int = logging.INFO) -> None:
    """初始化全局日志配置"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console)

    # 文件 handler (轮转策略可后续通过 RotatingFileHandler 实现)
    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    # 压低第三方库日志
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
