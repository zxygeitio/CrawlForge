"""
UCP (undetected-chromedriver) 浏览器后端

集成 undetected-chromedriver，提供高强度反检测浏览器能力。
用于对抗 小红书/贴吧/马蜂窝 等深度 JS 反爬站点。

undetected-chromedriver 基于 Selenium + CDP 补丁，
在浏览器二进制层面 patch 掉了大部分自动化检测信号。
"""

import logging
import threading
from typing import Optional

import undetected_chromedriver as ucp
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)


class UCPBrowser:
    """
    UCP 浏览器管理器（线程安全单例）

    使用示例:
        browser = UCPBrowser()
        browser.get(url)
        content = browser.page_source
        browser.close()
    """

    _instance: Optional["UCPBrowser"] = None
    _lock = threading.Lock()

    def __init__(self, config: "UCPConfig" = None):
        self.config = config or UCPConfig()
        self._driver: Optional[ucp.Chrome] = None

    @classmethod
    def get_instance(cls, config: "UCPConfig" = None) -> "UCPBrowser":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    def launch(self) -> ucp.Chrome:
        """启动 UCP 浏览器"""
        if self._driver is not None:
            return self._driver

        options = Options()

        if self.config.headless:
            options.add_argument("--headless=new")

        # 基础反检测参数（与 stealth browser 一致）
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--mute-audio")
        options.add_argument(f"--window-size={self.config.viewport['width']},{self.config.viewport['height']}")

        # User-Agent
        if self.config.user_agent:
            options.add_argument(f"--user-agent={self.config.user_agent}")

        # 代理
        if self.config.proxy:
            proxy = self.config.proxy.get("server", "")
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")

        # 语言
        options.add_argument("--lang=zh-CN")

        # 启动（undetected_chromedriver 自动打 CDP 补丁）
        self._driver = ucp.Chrome(
            options=options,
            version_main=None,  # 自动检测本地 Chrome 版本
            patcher_force_close=True,
        )

        if self.config.headless:
            self._driver.set_window_size(
                self.config.viewport["width"],
                self.config.viewport["height"]
            )

        logger.info("[UCP] Browser launched (stealth mode)")
        return self._driver

    def get(self, url: str, timeout: int = 30) -> str:
        """
        打开 URL 并返回页面源码

        Args:
            url: 目标 URL
            timeout: 超时秒数

        Returns:
            页面 HTML 源码
        """
        driver = self.launch()
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        return driver.page_source

    def get_with_cookies(self, url: str, cookies: list = None,
                         timeout: int = 30) -> tuple[str, list]:
        """
        打开 URL（可选带 cookies）并返回源码 + 当前 cookies

        Args:
            url: 目标 URL
            cookies: Selenium 格式的 cookies 列表
            timeout: 超时秒数

        Returns:
            (页面源码, 当前cookies列表)
        """
        driver = self.launch()

        if cookies:
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"Failed to add cookie: {e}")

        driver.set_page_load_timeout(timeout)
        driver.get(url)
        page_cookies = driver.get_cookies()
        return driver.page_source, page_cookies

    def get_cookies(self) -> list:
        """获取当前所有 cookies"""
        if self._driver is None:
            return []
        return self._driver.get_cookies()

    def close(self):
        """关闭浏览器"""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
            logger.info("[UCP] Browser closed")

    @classmethod
    def reset_instance(cls):
        """重置单例（用于多实例场景）"""
        with cls._lock:
            if cls._instance is not None:
                try:
                    cls._instance._driver.quit()
                except Exception:
                    pass
                cls._instance = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class UCPConfig:
    """UCP 浏览器配置"""

    def __init__(
        self,
        headless: bool = True,
        user_agent: str = None,
        proxy: dict = None,
        viewport: dict = None,
    ):
        self.headless = headless
        self.user_agent = user_agent
        self.proxy = proxy
        self.viewport = viewport or {"width": 1920, "height": 1080}
