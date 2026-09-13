import logging
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logger(logger_name='copilot'):
    """配置并返回一个全局可用的logger实例"""

    # 创建logger
    logger = logging.getLogger(logger_name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 设置日志级别
    logger.setLevel(logging.DEBUG)

    # 创建日志文件目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 配置控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    log_file_name = f"{logger_name}.log"

    # 配置文件输出
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, log_file_name),
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

# 创建全局logger实例
logger = setup_logger()