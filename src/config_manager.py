"""
配置管理
支持 YAML/JSON 配置文件
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    name: str = "crawler"
    timeout: int = 30
    retry_times: int = 3
    retry_delay: float = 1.0
    download_delay: float = 1.0
    concurrent: int = 5

    # 浏览器配置
    headless: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # 代理配置
    proxy_pool: list = field(default_factory=list)
    proxy_enabled: bool = False
    proxy_check_interval: int = 300

    # 存储配置
    storage_type: str = "file"
    storage_url: str = ""

    # 限流配置
    rate_limit: float = 10.0
    enable_rate_limit: bool = True

    # 特性开关
    use_tls_bypass: bool = True
    use_stealth_browser: bool = True

    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = None


class ConfigManager:
    """
    配置管理器

    支持:
    - YAML 文件加载
    - JSON 文件加载
    - 环境变量覆盖
    - 配置验证
    """

    _instance: Optional["ConfigManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config: Optional[CrawlerConfig] = None
        self._raw_config: dict = {}

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """获取单例实例"""
        return cls()

    def _validate_path(self, path: str, base_dir: str = None) -> str:
        """
        验证路径安全，防止 path traversal 攻击。

        Args:
            path: 用户提供的路径
            base_dir: 允许的基础目录。
                     - None: 加载时使用 cwd，保存时由调用者传入目标父目录

        Returns:
            经验证的绝对路径

        Raises:
            ValueError: 路径超出允许范围（包含 .. 逃逸）
        """
        # 展开用户和环境变量
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)

        # 先规范化（解析 .. 等），再转绝对路径
        normalized = os.path.normpath(path)
        abs_path = os.path.abspath(normalized)

        # 确定允许的基础目录
        if base_dir is None:
            # 加载配置：默认以 cwd 为基准，防止逃逸到系统目录如 /etc、C:\Windows
            # 生产环境建议通过 CRAWLER_CONFIG_ROOT 环境变量显式指定安全根目录
            base_dir = os.environ.get(
                "CRAWLER_CONFIG_ROOT",
                os.getcwd()
            )
        abs_base = os.path.abspath(base_dir)

        # 分层安全策略：
        # - load 操作：阻止显式 .. 逃逸（防止 ../etc/passwd 类型的攻击）
        #   纯绝对路径（如 C:\Windows\config.cfg）由 os.path.exists 拦截，此处不重复拒绝
        # - save 操作：强制 containment（由 save_to_yaml/json 的 relpath 检查保证）
        # 对 load：仅在包含 .. 时做 containment 检查（normpath 会在规范化后消除 ..）
        has_traversal = ".." in path
        if has_traversal and not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
            raise ValueError(
                f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                f"which is outside allowed directory '{abs_base}'"
            )

        return abs_path

    def load_from_yaml(self, path: str) -> CrawlerConfig:
        """从 YAML 文件加载配置"""
        path = self._validate_path(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self._raw_config = yaml.safe_load(f) or {}

        self._apply_env_overrides()
        self._config = self._raw_config_to_dataclass()
        return self._config

    def load_from_json(self, path: str) -> CrawlerConfig:
        """从 JSON 文件加载配置"""
        path = self._validate_path(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self._raw_config = json.load(f)

        self._apply_env_overrides()
        self._config = self._raw_config_to_dataclass()
        return self._config

    def load_from_dict(self, config_dict: dict) -> CrawlerConfig:
        """从字典加载配置"""
        self._raw_config = config_dict
        self._apply_env_overrides()
        self._config = self._raw_config_to_dataclass()
        return self._config

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        env_mappings = {
            "CRAWLER_NAME": ("name", str),
            "CRAWLER_TIMEOUT": ("timeout", int),
            "CRAWLER_RETRY_TIMES": ("retry_times", int),
            "CRAWLER_RATE_LIMIT": ("rate_limit", float),
            "CRAWLER_PROXY_ENABLED": ("proxy_enabled", lambda x: x.lower() == "true"),
            "CRAWLER_HEADLESS": ("headless", lambda x: x.lower() == "true"),
            "CRAWLER_LOG_LEVEL": ("log_level", str),
        }

        for env_key, (config_key, converter) in env_mappings.items():
            value = os.environ.get(env_key)
            if value is not None:
                try:
                    self._raw_config[config_key] = converter(value)
                except (ValueError, TypeError):
                    pass

    def _raw_config_to_dataclass(self) -> CrawlerConfig:
        """将原始配置字典转换为 dataclass"""
        return CrawlerConfig(
            name=self._raw_config.get("name", "crawler"),
            timeout=self._raw_config.get("timeout", 30),
            retry_times=self._raw_config.get("retry_times", 3),
            retry_delay=self._raw_config.get("retry_delay", 1.0),
            download_delay=self._raw_config.get("download_delay", 1.0),
            concurrent=self._raw_config.get("concurrent", 5),
            headless=self._raw_config.get("headless", True),
            user_agent=self._raw_config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            ),
            proxy_pool=self._raw_config.get("proxy_pool", []),
            proxy_enabled=self._raw_config.get("proxy_enabled", False),
            proxy_check_interval=self._raw_config.get("proxy_check_interval", 300),
            storage_type=self._raw_config.get("storage_type", "file"),
            storage_url=self._raw_config.get("storage_url", ""),
            rate_limit=self._raw_config.get("rate_limit", 10.0),
            enable_rate_limit=self._raw_config.get("enable_rate_limit", True),
            use_tls_bypass=self._raw_config.get("use_tls_bypass", True),
            use_stealth_browser=self._raw_config.get("use_stealth_browser", True),
            log_level=self._raw_config.get("log_level", "INFO"),
            log_file=self._raw_config.get("log_file"),
        )

    def get_config(self) -> Optional[CrawlerConfig]:
        """获取当前配置"""
        return self._config

    def update_config(self, **kwargs):
        """更新配置项"""
        if self._config is None:
            raise RuntimeError("No config loaded")

        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        # 同步回 raw_config
        for key in kwargs:
            self._raw_config[key] = kwargs[key]

    def save_to_yaml(self, path: str):
        """保存配置到 YAML 文件"""
        if self._config is None:
            raise RuntimeError("No config to save")

        # 展开路径后规范化，用 relpath 判断是否逃逸 cwd 或 CRAWLER_CONFIG_ROOT
        # CRAWLER_CONFIG_ROOT 允许跨盘符保存（如 save 到 /tmp 或 C:\Temp）
        expanded = os.path.expanduser(os.path.expandvars(path))
        normalized = os.path.normpath(expanded)
        abs_path = os.path.abspath(normalized)
        base = os.environ.get("CRAWLER_CONFIG_ROOT", os.getcwd())
        try:
            rel = os.path.relpath(abs_path, base)
            if rel.startswith(".."):
                raise ValueError(
                    f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                    f"which is outside the allowed directory '{base}'"
                )
        except ValueError:
            # 跨盘符：使用 commonpath 判断 target 是否在 base 的子树外
            # （Unix 上 cwd=/project, target=/tmp → commonpath=/, relpath=../../tmp）
            try:
                common = os.path.commonpath([abs_path, base])
                # 如果 target 的父目录（base）与 base 完全无关，说明是跨盘符逃逸
                if not abs_path.startswith(base + os.sep) and abs_path != base:
                    raise ValueError(
                        f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                        f"which is outside the allowed directory '{base}'"
                    )
            except ValueError:
                # commonpath 在跨盘符时抛 ValueError → 拒绝
                raise ValueError(
                    f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                    f"which is outside the allowed directory '{base}'"
                )

        path = self._validate_path(path, base_dir=base)
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._raw_config, f, allow_unicode=True, default_flow_style=False)

    def save_to_json(self, path: str):
        """保存配置到 JSON 文件"""
        if self._config is None:
            raise RuntimeError("No config to save")

        # 展开路径后规范化，用 relpath 判断是否逃逸 cwd 或 CRAWLER_CONFIG_ROOT
        expanded = os.path.expanduser(os.path.expandvars(path))
        normalized = os.path.normpath(expanded)
        abs_path = os.path.abspath(normalized)
        base = os.environ.get("CRAWLER_CONFIG_ROOT", os.getcwd())
        try:
            rel = os.path.relpath(abs_path, base)
            if rel.startswith(".."):
                raise ValueError(
                    f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                    f"which is outside the allowed directory '{base}'"
                )
        except ValueError:
            # 跨盘符：使用 commonpath 判断 target 是否在 base 的子树外
            try:
                common = os.path.commonpath([abs_path, base])
                if not abs_path.startswith(base + os.sep) and abs_path != base:
                    raise ValueError(
                        f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                        f"which is outside the allowed directory '{base}'"
                    )
            except ValueError:
                raise ValueError(
                    f"Path traversal attempt detected: '{path}' resolves to '{abs_path}', "
                    f"which is outside the allowed directory '{base}'"
                )

        path = self._validate_path(path, base_dir=base)
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._raw_config, f, ensure_ascii=False, indent=2)


def create_default_config(path: str = "config.yaml"):
    """创建默认配置文件"""
    default_config = CrawlerConfig()
    # 设置 CRAWLER_CONFIG_ROOT 到目标文件所在目录，允许跨盘符保存
    expanded = os.path.expanduser(os.path.expandvars(path))
    normalized = os.path.normpath(expanded)
    abs_path = os.path.abspath(normalized)
    old_root = os.environ.get("CRAWLER_CONFIG_ROOT")
    os.environ["CRAWLER_CONFIG_ROOT"] = os.path.dirname(abs_path)
    try:
        manager = ConfigManager()
        manager.load_from_dict({
            "name": default_config.name,
            "timeout": default_config.timeout,
            "retry_times": default_config.retry_times,
            "retry_delay": default_config.retry_delay,
            "download_delay": default_config.download_delay,
            "concurrent": default_config.concurrent,
            "headless": default_config.headless,
            "user_agent": default_config.user_agent,
            "proxy_pool": default_config.proxy_pool,
            "proxy_enabled": default_config.proxy_enabled,
            "proxy_check_interval": default_config.proxy_check_interval,
            "storage_type": default_config.storage_type,
            "storage_url": default_config.storage_url,
            "rate_limit": default_config.rate_limit,
            "enable_rate_limit": default_config.enable_rate_limit,
            "use_tls_bypass": default_config.use_tls_bypass,
            "use_stealth_browser": default_config.use_stealth_browser,
            "log_level": default_config.log_level,
            "log_file": default_config.log_file,
        })
        manager.save_to_yaml(path)
    finally:
        if old_root is None:
            os.environ.pop("CRAWLER_CONFIG_ROOT", None)
        else:
            os.environ["CRAWLER_CONFIG_ROOT"] = old_root
    return path
