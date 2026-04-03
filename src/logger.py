"""
统一日志系统
支持 loguru (优先) 或标准 logging 回退
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from loguru import logger as _loguru_logger
    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False
    _loguru_logger = None


class StandardLogger:
    """标准 logging 回退"""

    def __init__(self):
        self._logger = logging.getLogger("crawler")
        self._logger.setLevel(logging.INFO)

        # 控制台处理器
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def add_file(self, path: str, level: str = "INFO"):
        """添加文件处理器"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setLevel(getattr(logging, level.upper()))
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def debug(self, msg, **kwargs):
        self._logger.debug(msg, **kwargs)

    def info(self, msg, **kwargs):
        self._logger.info(msg, **kwargs)

    def warning(self, msg, **kwargs):
        self._logger.warning(msg, **kwargs)

    def error(self, msg, **kwargs):
        self._logger.error(msg, **kwargs)

    def critical(self, msg, **kwargs):
        self._logger.critical(msg, **kwargs)

    def exception(self, msg, **kwargs):
        self._logger.exception(msg, **kwargs)

    def success(self, msg, **kwargs):
        self._logger.info(f"[SUCCESS] {msg}")


class LogManager:
    """
    日志管理器

    特性:
    - 单例模式
    - 自动创建日志目录
    - 按日期自动分割
    - 多级别日志
    - 结构化日志输出
    """

    _instance: Optional["LogManager"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LogManager._initialized:
            return
        LogManager._initialized = True

        if LOGURU_AVAILABLE:
            self._logger = _loguru_logger
        else:
            self._logger = StandardLogger()

        self._log_file: Optional[str] = None
        self._log_level: str = "INFO"
        self._enable_console: bool = True

    def setup(
        self,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        log_dir: str = "logs",
        enable_console: bool = True,
        rotation: str = "10 MB",
        retention: str = "7 days",
        compression: str = "zip",
    ):
        """
        设置日志

        Args:
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            log_file: 日志文件名，如果为 None 则自动生成
            log_dir: 日志目录
            enable_console: 是否输出到控制台
            rotation: 分割大小或时间 (e.g. "100 MB", "02:00", "daily")
            retention: 保留时间 (e.g. "7 days", "1 month")
            compression: 压缩格式 (e.g. "zip", "gz")
        """
        self._log_level = log_level
        self._enable_console = enable_console

        if LOGURU_AVAILABLE:
            # loguru 模式
            self._logger.remove()

            if enable_console:
                self._logger.add(
                    sys.stderr,
                    level=log_level,
                    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
                    colorize=True,
                )

            if log_file or log_dir:
                log_dir_path = Path(log_dir)
                log_dir_path.mkdir(parents=True, exist_ok=True)

                if log_file is None:
                    log_file = f"crawler_{datetime.now().strftime('%Y%m%d')}.log"

                log_path = log_dir_path / log_file
                self._log_file = str(log_path)

                self._logger.add(
                    log_path,
                    level=log_level,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
                    rotation=rotation,
                    retention=retention,
                    compression=compression,
                    encoding="utf-8",
                )
        else:
            # 标准 logging 模式
            self._logger = StandardLogger()
            if enable_console:
                self._logger._logger.setLevel(getattr(logging, log_level.upper()))

            if log_file or log_dir:
                log_dir_path = Path(log_dir)
                log_dir_path.mkdir(parents=True, exist_ok=True)
                if log_file is None:
                    log_file = f"crawler_{datetime.now().strftime('%Y%m%d')}.log"
                self._logger.add_file(str(log_dir_path / log_file), log_level)

        return self

    def add_file(
        self,
        path: str,
        level: str = "INFO",
        rotation: str = "10 MB",
        retention: str = "7 days",
    ):
        """添加额外的日志文件处理器"""
        if LOGURU_AVAILABLE:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._logger.add(
                path,
                level=level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
            )
        else:
            self._logger.add_file(path, level)

    def debug(self, message: str, **kwargs):
        """调试日志"""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """信息日志"""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """警告日志"""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """错误日志"""
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self._logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs):
        """异常日志（自动包含堆栈）"""
        self._logger.exception(message, **kwargs)

    def success(self, message: str, **kwargs):
        """成功日志"""
        self._logger.success(message, **kwargs)

    def log_crawl_event(
        self,
        event_type: str,
        url: str,
        status: str,
        duration: float = None,
        error: str = None,
    ):
        """记录爬虫事件"""
        if event_type == "request":
            self.info(f"[CRAWL] Request: {url}")
        elif event_type == "success":
            msg = f"[CRAWL] Success: {url}"
            if duration:
                msg += f" ({duration:.2f}s)"
            self.success(msg)
        elif event_type == "retry":
            self.warning(f"[CRAWL] Retry: {url} - {error}")
        elif event_type == "fail":
            self.error(f"[CRAWL] Fail: {url} - {error}")

    def log_proxy_event(self, proxy: str, event: str, success: bool = True):
        """记录代理事件"""
        status = "OK" if success else "FAIL"
        self.info(f"[PROXY] {status} | {proxy} | {event}")

    def log_captcha_event(self, captcha_type: str, solved: bool, duration: float = None):
        """记录验证码事件"""
        status = "Solved" if solved else "Failed"
        msg = f"[CAPTCHA] {status}: {captcha_type}"
        if duration:
            msg += f" ({duration:.2f}s)"

        if solved:
            self.success(msg)
        else:
            self.error(msg)


# 全局日志管理器实例
_log_manager: Optional[LogManager] = None


def get_logger() -> LogManager:
    """获取全局日志管理器"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
        _log_manager.setup()
    return _log_manager


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    **kwargs
) -> LogManager:
    """设置全局日志"""
    global _log_manager
    _log_manager = LogManager()
    _log_manager.setup(log_level=log_level, log_file=log_file, log_dir=log_dir, **kwargs)
    return _log_manager


# 快捷函数
def debug(message: str, **kwargs):
    get_logger().debug(message, **kwargs)


def info(message: str, **kwargs):
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs):
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs):
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs):
    get_logger().critical(message, **kwargs)


def exception(message: str, **kwargs):
    get_logger().exception(message, **kwargs)


def success(message: str, **kwargs):
    get_logger().success(message, **kwargs)
