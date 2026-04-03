"""
高级爬虫框架 v2
- 异步支持
- 代理池增强
- 速率限制
- 隐身浏览器
- 更完善的Hook集成
"""

import asyncio
import hashlib
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import aiohttp
import requests
from curl_cffi import requests as curl_requests
from playwright.sync_api import sync_playwright

from src.proxy_manager import ProxyPoolManager, ProxyPoolConfig, ProxyStatus
from src.rate_limiter import TokenBucket, SlidingWindowRateLimiter, MultiLimiter
from src.stealth_browser import StealthBrowser, StealthConfig, STealth_JS_INJECT
from src.js_hook_tools import JSHookManager

# 创建logger
logger = logging.getLogger(__name__)


# ============== 配置 ==============

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
    proxy_check_interval: int = 300  # 代理健康检查间隔

    # 存储配置
    storage_type: str = "file"  # mongodb, mysql, file
    storage_url: str = ""

    # 限流配置
    rate_limit: float = 10.0  # 每秒请求数
    enable_rate_limit: bool = True

    # 特性开关
    use_tls_bypass: bool = True
    use_stealth_browser: bool = True


class RequestMethod(Enum):
    """请求方法"""
    REQUESTS = "requests"
    CURL_CFFI = "curl_cffi"
    PLAYWRIGHT = "playwright"
    ASYNC_CURL = "async_curl"


# ============== 存储后端 ==============

class StorageBackend:
    """存储基类"""
    def save(self, item: dict) -> bool: raise NotImplementedError
    def exists(self, url: str) -> bool: raise NotImplementedError
    def get_all(self, filter_dict: dict = None) -> list: raise NotImplementedError


class MongoStorage(StorageBackend):
    """MongoDB存储"""
    def __init__(self, uri: str, db_name: str):
        from pymongo import MongoClient
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db["items"]

    def save(self, item: dict) -> bool:
        item["hash"] = hashlib.md5(item["url"].encode()).hexdigest()
        item["updated_at"] = datetime.utcnow()
        result = self.collection.update_one(
            {"url": item["url"]},
            {"$set": item},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def exists(self, url: str) -> bool:
        return self.collection.count_documents({"url": url}) > 0

    def get_all(self, filter_dict: dict = None) -> list:
        return list(self.collection.find(filter_dict or {}))


class FileStorage(StorageBackend):
    """本地文件存储"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self.items = []
        self._loaded = False

    async def _ensure_loaded(self):
        if not self._loaded:
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.items = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
                self.items = []
            self._loaded = True

    async def _save(self):
        async with self._lock:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)

    async def save(self, item: dict) -> bool:
        await self._ensure_loaded()
        item["hash"] = hashlib.md5(item["url"].encode()).hexdigest()
        item["updated_at"] = datetime.utcnow().isoformat()

        for i, existing in enumerate(self.items):
            if existing["url"] == item["url"]:
                self.items[i] = item
                await self._save()
                return True

        self.items.append(item)
        await self._save()
        return True

    async def exists(self, url: str) -> bool:
        await self._ensure_loaded()
        return any(item["url"] == url for item in self.items)

    async def get_all(self, filter_dict: dict = None) -> list:
        await self._ensure_loaded()
        if not filter_dict:
            return self.items
        return [item for item in self.items
                if all(item.get(k) == v for k, v in filter_dict.items())]


class SyncFileStorage:
    """同步文件存储"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.items = self._load()

    def _load(self) -> list:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, PermissionError):
            return []

    def _save(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def save(self, item: dict) -> bool:
        item["hash"] = hashlib.md5(item["url"].encode()).hexdigest()
        item["updated_at"] = datetime.utcnow().isoformat()

        for i, existing in enumerate(self.items):
            if existing["url"] == item["url"]:
                self.items[i] = item
                self._save()
                return True

        self.items.append(item)
        self._save()
        return True

    def exists(self, url: str) -> bool:
        return any(item["url"] == url for item in self.items)

    def get_all(self, filter_dict: dict = None) -> list:
        if not filter_dict:
            return self.items
        return [item for item in self.items
                if all(item.get(k) == v for k, v in filter_dict.items())]


# ============== 爬虫核心 ==============

class AdvancedCrawler:
    """
    高级爬虫框架

    支持:
    - 多方法请求 (requests, curl_cffi, playwright)
    - 自动重试 + 指数退避
    - 代理池评分
    - 速率限制
    - 隐身浏览器
    - 增量爬取
    """

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self._init_storage()
        self._init_proxy_pool()
        self._init_rate_limiter()
        self._init_stealth_browser()
        self._session = requests.Session()

    def _init_storage(self):
        if self.config.storage_type == "mongodb":
            self.storage = MongoStorage(self.config.storage_url, self.config.name)
        else:
            self.storage = SyncFileStorage(f"{self.config.name}_data.json")

    def _init_proxy_pool(self):
        self.proxy_pool = ProxyPoolManager(
            ProxyPoolConfig(check_interval=self.config.proxy_check_interval)
        )
        for proxy in self.config.proxy_pool:
            self.proxy_pool.add_proxy(proxy)

    def _init_rate_limiter(self):
        if self.config.enable_rate_limit:
            self.rate_limiter = MultiLimiter()
            self.rate_limiter.set_domain_rate("*", self.config.rate_limit)
        else:
            self.rate_limiter = None

    def _init_stealth_browser(self):
        if self.config.use_stealth_browser:
            stealth_config = StealthConfig(
                headless=self.config.headless,
                user_agent=self.config.user_agent,
            )
            self.stealth_browser = StealthBrowser(stealth_config)
        else:
            self.stealth_browser = None

    def _get_proxy(self) -> Optional[dict]:
        if not self.config.proxy_enabled:
            return None
        # 使用同步方法获取代理，避免在同步函数中运行事件循环
        proxy = self.proxy_pool.get_proxy()
        if proxy:
            return {"http": proxy.url, "https": proxy.url}
        return None

    def _request_curl(self, method: str, url: str, **kwargs) -> Optional[Any]:
        """curl_cffi请求 (TLS绕过)"""
        try:
            kwargs.setdefault("timeout", self.config.timeout)
            kwargs.setdefault("impersonate", "chrome")

            if method.upper() == "GET":
                return curl_requests.get(url, **kwargs)
            return curl_requests.post(url, **kwargs)
        except Exception as e:
            logger.exception(f"curl_cffi Error for {url}: {e}")
            return None

    def _request_requests(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """requests请求"""
        try:
            kwargs.setdefault("timeout", self.config.timeout)
            kwargs.setdefault("headers", {"User-Agent": self.config.user_agent})

            proxies = self._get_proxy()
            if proxies:
                kwargs["proxies"] = proxies

            if method.upper() == "GET":
                return self._session.get(url, **kwargs)
            return self._session.post(url, **kwargs)
        except Exception as e:
            logger.exception(f"requests Error for {url}: {e}")
            return None

    def _request_playwright(self, url: str, wait_until: str = "domcontentloaded",
                           js_code: str = None, hooks: list = None) -> Optional[Any]:
        """Playwright请求"""
        if not self.stealth_browser:
            return None

        browser = None
        context = None
        try:
            browser = self.stealth_browser.launch()
            context = browser.new_context()
            page = context.new_page()

            # 安装Hook
            if hooks:
                JSHookManager.install_hooks(page, hooks)
            else:
                page.evaluate(STealth_JS_INJECT)

            response = page.goto(url, wait_until=wait_until)

            if js_code:
                result = page.evaluate(js_code)
                return result

            content = page.content()
            return {
                "status": response.status if response else None,
                "content": content
            }
        except Exception as e:
            logger.exception(f"Playwright Error for {url}: {e}")
            return None
        finally:
            # 确保资源释放，即使发生异常也不例外
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
            except Exception as e:
                logger.warning(f"Failed to close browser resources: {e}")

    async def _async_request_curl(self, method: str, url: str, **kwargs) -> Optional[Any]:
        """异步curl_cffi请求"""
        try:
            kwargs.setdefault("timeout", self.config.timeout)
            kwargs.setdefault("impersonate", "chrome")

            if method.upper() == "GET":
                return await curl_requests.get(url, **kwargs)
            return await curl_requests.post(url, **kwargs)
        except Exception as e:
            logger.exception(f"async_curl Error for {url}: {e}")
            return None

    def _exponential_backoff(self, attempt: int) -> float:
        """指数退避"""
        return min(self.config.retry_delay * (2 ** attempt), 60)

    def request(
        self,
        method: str,
        url: str,
        use_method: RequestMethod = RequestMethod.CURL_CFFI,
        **kwargs
    ) -> Optional[Any]:
        """发送请求 (同步)"""
        # 增量检查
        if self.storage.exists(url):
            logger.info(f"Already crawled: {url}")
            return None

        for attempt in range(self.config.retry_times):
            if use_method == RequestMethod.CURL_CFFI:
                response = self._request_curl(method, url, **kwargs)
            elif use_method == RequestMethod.PLAYWRIGHT:
                response = self._request_playwright(url, **kwargs)
            else:
                response = self._request_requests(method, url, **kwargs)

            if response and hasattr(response, 'status_code') and response.status_code == 200:
                time.sleep(self.config.download_delay)
                return response

            if attempt < self.config.retry_times - 1:
                delay = self._exponential_backoff(attempt)
                logger.warning(f"Retry {attempt + 1} after {delay}s for {url}...")
                time.sleep(delay)

        return None

    async def async_request(
        self,
        method: str,
        url: str,
        use_method: RequestMethod = RequestMethod.ASYNC_CURL,
        **kwargs
    ) -> Optional[Any]:
        """发送请求 (异步)"""
        if self.storage.exists(url):
            logger.info(f"Already crawled: {url}")
            return None

        for attempt in range(self.config.retry_times):
            if use_method == RequestMethod.ASYNC_CURL:
                response = await self._async_request_curl(method, url, **kwargs)
            else:
                response = self.request(method, url, use_method, **kwargs)

            if response and hasattr(response, 'status_code') and response.status_code == 200:
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                return response

            if attempt < self.config.retry_times - 1:
                delay = self._exponential_backoff(attempt)
                logger.warning(f"Retry {attempt + 1} after {delay}s for {url}...")
                await asyncio.sleep(delay)

        return None

    def crawl_page(
        self,
        url: str,
        parser: Callable[[Any], dict],
        use_method: RequestMethod = RequestMethod.CURL_CFFI,
        **kwargs
    ) -> Optional[dict]:
        """爬取单个页面"""
        response = self.request("GET", url, use_method, **kwargs)
        if not response:
            return None

        try:
            item = parser(response)
            if item:
                item["url"] = url
                item["crawled_at"] = datetime.utcnow().isoformat()
                self.storage.save(item)
            return item
        except Exception as e:
            logger.exception(f"Parse Error for {url}: {e}")
            return None

    async def async_crawl_page(
        self,
        url: str,
        parser: Callable[[Any], dict],
        use_method: RequestMethod = RequestMethod.ASYNC_CURL,
        **kwargs
    ) -> Optional[dict]:
        """爬取单个页面 (异步)"""
        response = await self.async_request("GET", url, use_method, **kwargs)
        if not response:
            return None

        try:
            item = parser(response)
            if item:
                item["url"] = url
                item["crawled_at"] = datetime.utcnow().isoformat()
                if isinstance(self.storage, SyncFileStorage):
                    # 在executor中运行同步存储操作，避免阻塞事件循环
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.storage.save, item)
                else:
                    await self.storage.save(item)
            return item
        except Exception as e:
            logger.exception(f"Parse Error for {url}: {e}")
            return None

    async def crawl_site_async(
        self,
        start_url: str,
        url_extractor: Callable[[Any], list],
        parser: Callable[[Any], dict],
        max_pages: int = 100,
        max_concurrent: int = 5,
        use_method: RequestMethod = RequestMethod.ASYNC_CURL,
        **kwargs
    ) -> list:
        """异步爬取整站"""
        results = []
        pending_urls = [start_url]
        visited_urls = set()
        semaphore = asyncio.Semaphore(max_concurrent)

        async def crawl_one(url: str) -> Optional[dict]:
            async with semaphore:
                if url in visited_urls:
                    return None
                visited_urls.add(url)
                logger.debug(f"Crawling: {url}")
                return await self.async_crawl_page(url, parser, use_method, **kwargs)

        while len(visited_urls) < max_pages and pending_urls:
            current_url = pending_urls.pop(0)
            if current_url in visited_urls:
                continue

            result = await crawl_one(current_url)
            if result:
                results.append(result)

            # 提取新URL
            response = await self.async_request("GET", current_url, use_method, **kwargs)
            if response:
                new_urls = url_extractor(response)
                for url in new_urls:
                    if url not in visited_urls:
                        pending_urls.append(url)

            await asyncio.sleep(self.config.download_delay)

        return results

    def close(self):
        """关闭资源"""
        if self.stealth_browser:
            self.stealth_browser.close()
        if hasattr(self.proxy_pool, 'stop_health_checker'):
            self.proxy_pool.stop_health_checker()


# ============== 使用示例 ==============

def example_parser(response) -> dict:
    """示例解析函数"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')
    return {
        "title": soup.find("title").text if soup.find("title") else "",
        "content": soup.get_text(strip=True)[:500],
    }


def example_url_extractor(response) -> list:
    """示例URL提取函数"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')
    base_url = "https://example.com"

    urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("/"):
            urls.append(base_url + href)
        elif href.startswith("http"):
            urls.append(href)
    return urls


if __name__ == "__main__":
    config = CrawlerConfig(
        name="example_crawler",
        timeout=30,
        download_delay=1.0,
        rate_limit=10.0,
        proxy_enabled=False,
        storage_type="file",
        use_stealth_browser=True
    )

    crawler = AdvancedCrawler(config)

    # 同步爬取示例
    results = crawler.crawl_page(
        url="https://example.com",
        parser=example_parser,
        use_method=RequestMethod.CURL_CFFI
    )

    print(f"Result: {results}")
    crawler.close()
