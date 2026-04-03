"""
日志工具模块
提供统一的日志配置和管理功能
"""

import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger:
    """
    日志管理器

    提供统一的日志配置，支持控制台和文件输出，
    支持不同的日志级别和格式化选项。
    """

    _instances: dict[str, logging.Logger] = {}

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        log_file: Optional[Path] = None,
        format_string: Optional[str] = None
    ):
        """
        初始化日志管理器

        Args:
            name: 日志记录器名称
            level: 日志级别
            log_file: 日志文件路径（可选）
            format_string: 自定义格式字符串（可选）
        """
        self.name = name
        self.level = level
        self.log_file = log_file
        self.format_string = format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @property
    def logger(self) -> logging.Logger:
        """获取或创建日志记录器实例"""
        if self.name not in Logger._instances:
            Logger._instances[self.name] = self._create_logger()
        return Logger._instances[self.name]

    def _create_logger(self) -> logging.Logger:
        """创建并配置日志记录器"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level.value)
        logger.handlers.clear()

        formatter = logging.Formatter(self.format_string)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level.value)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(self.level.value)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def debug(self, message: str, **kwargs) -> None:
        """记录调试信息"""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """记录一般信息"""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """记录警告信息"""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """记录错误信息"""
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """记录严重错误信息"""
        self.logger.critical(message, **kwargs)


def get_logger(
    name: str,
    level: LogLevel = LogLevel.INFO,
    log_file: Optional[str] = None
) -> Logger:
    """
    获取日志记录器的便捷函数

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（可选）

    Returns:
        Logger实例
    """
    return Logger(
        name=name,
        level=level,
        log_file=Path(log_file) if log_file else None
    )


if __name__ == "__main__":
    logger = get_logger("test", LogLevel.DEBUG)

    logger.debug("这是调试信息")
    logger.info("这是信息")
    logger.warning("这是警告")
    logger.error("这是错误")
    logger.critical("这是严重错误")
