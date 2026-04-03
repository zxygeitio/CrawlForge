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
    ProtocolSliderCaptchaSolver,
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
    TouchTrajectory,
    KeyboardSimulator,
    ScrollSimulator,
)
from src.monitor import Monitor, AlertManager
from src.data_processor import DataCleaner, DataExporter
from src.tls_fingerprint import TLSFingerprintAnalyzer, JA3Calculator, detect_tls_fingerprint
from src.page_analyzer import (
    PageAnalysis,
    PageStructureAnalyzer,
    SimpleAIPageAnalyzer,
    CaptchaType,
    AntiBotMeasure,
)

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
    "ProtocolSliderCaptchaSolver",
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
    "TouchTrajectory",
    "KeyboardSimulator",
    "ScrollSimulator",
    # 监控
    "Monitor",
    "AlertManager",
    # 数据处理
    "DataCleaner",
    "DataExporter",
    # TLS指纹分析
    "TLSFingerprintAnalyzer",
    "JA3Calculator",
    "detect_tls_fingerprint",
    # 页面分析
    "PageAnalysis",
    "PageStructureAnalyzer",
    "SimpleAIPageAnalyzer",
    "CaptchaType",
    "AntiBotMeasure",
]

__version__ = "2.0.0"
