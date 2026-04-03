"""
爬虫逆向框架 v2
Crawler Reverse Engineering Framework

导出核心组件供外部使用
"""

from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod
from src.proxy_manager import ProxyPoolManager, ProxyPoolConfig, ProxyStatus
from src.rate_limiter import (
    TokenBucket,
    SlidingWindowRateLimiter,
    AdaptiveRateLimiter,
    MultiLimiter,
    TokenBucketConfig,
)
from src.stealth_browser import StealthBrowser, StealthConfig
from src.js_hook_tools import JSHookManager
from src.config_manager import ConfigManager, create_default_config
from src.logger import (
    LogManager,
    setup_logger,
    get_logger,
    debug,
    info,
    warning,
    error,
    critical,
    exception,
    success,
)
from src.captcha_solver import (
    CaptchaResult,
    BaseCaptchaSolver,
    SliderCaptchaSolver,
    ImageCaptchaSolver,
    GeeTestCaptchaSolver,
    create_solver,
)
from src.humanizer import (
    UserAgentPool,
    HumanDelay,
    MouseTrajectory,
    FingerprintPool,
    HeaderOrder,
    BehaviorSimulator,
    humanized_delay,
)
from src.monitor import Monitor, AlertManager
from src.data_processor import DataCleaner, DataExporter

__all__ = [
    # 核心爬虫
    "AdvancedCrawler",
    "CrawlerConfig",
    "RequestMethod",
    # 代理池
    "ProxyPoolManager",
    "ProxyPoolConfig",
    "ProxyStatus",
    # 速率限制
    "TokenBucket",
    "SlidingWindowRateLimiter",
    "AdaptiveRateLimiter",
    "MultiLimiter",
    "TokenBucketConfig",
    # 隐身浏览器
    "StealthBrowser",
    "StealthConfig",
    # Hook工具箱
    "JSHookManager",
    # 配置管理
    "ConfigManager",
    "create_default_config",
    # 日志
    "LogManager",
    "setup_logger",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "success",
    # 验证码
    "CaptchaResult",
    "BaseCaptchaSolver",
    "SliderCaptchaSolver",
    "ImageCaptchaSolver",
    "GeeTestCaptchaSolver",
    "create_solver",
    # 拟人化
    "UserAgentPool",
    "HumanDelay",
    "MouseTrajectory",
    "FingerprintPool",
    "HeaderOrder",
    "BehaviorSimulator",
    "humanized_delay",
    # 监控
    "Monitor",
    "AlertManager",
    # 数据处理
    "DataCleaner",
    "DataExporter",
]

__version__ = "2.0.0"
