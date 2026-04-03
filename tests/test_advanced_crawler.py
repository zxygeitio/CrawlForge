"""
AdvancedCrawler 核心模块测试
"""

import json
import time
from unittest.mock import patch, MagicMock

import pytest

from src.advanced_crawler import (
    AdvancedCrawler,
    CrawlerConfig,
    RequestMethod,
    SyncFileStorage,
)
from src.proxy_manager import SyncProxyPoolManager


class TestSyncFileStorage:
    """SyncFileStorage 测试 - 验证 O(1) URL index"""

    @pytest.fixture
    def temp_storage_file(self, tmp_path):
        """提供临时存储文件路径"""
        return str(tmp_path / "test_storage.json")

    @pytest.fixture
    def storage(self, temp_storage_file):
        """创建 SyncFileStorage 实例"""
        return SyncFileStorage(temp_storage_file)

    def test_save_creates_item(self, storage):
        """测试保存单个 item"""
        item = {"url": "https://example.com/page1", "title": "Page 1"}
        result = storage.save(item)

        assert result is True
        items = storage.get_all()
        assert len(items) == 1
        assert items[0]["url"] == "https://example.com/page1"
        assert "hash" in items[0]
        assert "updated_at" in items[0]

    def test_save_updates_existing_url(self, storage):
        """测试相同 URL 更新而非重复创建"""
        item1 = {"url": "https://example.com/page1", "title": "Page 1"}
        item2 = {"url": "https://example.com/page1", "title": "Page 1 Updated"}

        storage.save(item1)
        storage.save(item2)

        items = storage.get_all()
        assert len(items) == 1  # 只有一个 item
        assert items[0]["title"] == "Page 1 Updated"

    def test_exists_returns_true_for_saved_url(self, storage):
        """测试 exists 对已保存 URL 返回 True"""
        item = {"url": "https://example.com/page1", "title": "Page 1"}
        storage.save(item)

        assert storage.exists("https://example.com/page1") is True

    def test_exists_returns_false_for_unsaved_url(self, storage):
        """测试 exists 对未保存 URL 返回 False"""
        assert storage.exists("https://example.com/nonexistent") is False

    def test_get_all_returns_all_items(self, storage):
        """测试 get_all 返回所有 items"""
        storage.save({"url": "https://example.com/1", "title": "Page 1"})
        storage.save({"url": "https://example.com/2", "title": "Page 2"})
        storage.save({"url": "https://example.com/3", "title": "Page 3"})

        items = storage.get_all()
        assert len(items) == 3

    def test_get_all_with_filter(self, storage):
        """测试带 filter 的 get_all"""
        storage.save({"url": "https://example.com/1", "type": "a"})
        storage.save({"url": "https://example.com/2", "type": "b"})
        storage.save({"url": "https://example.com/3", "type": "a"})

        items = storage.get_all(filter_dict={"type": "a"})
        assert len(items) == 2
        assert all(item["type"] == "a" for item in items)

    def test_get_all_with_empty_filter_returns_all(self, storage):
        """测试空 filter 返回所有 items"""
        storage.save({"url": "https://example.com/1"})
        storage.save({"url": "https://example.com/2"})

        items = storage.get_all(filter_dict={})
        assert len(items) == 2

    def test_url_index_is_set_for_o1_lookup(self, storage):
        """验证使用 set 实现 O(1) URL 查找"""
        storage.save({"url": "https://example.com/page1"})

        # _url_index 应该是 set 类型
        assert isinstance(storage._url_index, set)
        assert "https://example.com/page1" in storage._url_index

    def test_persistence_after_reload(self, temp_storage_file):
        """测试重新加载后数据持久化"""
        storage1 = SyncFileStorage(temp_storage_file)
        storage1.save({"url": "https://example.com/page1", "title": "Page 1"})

        # 重新创建实例加载数据
        storage2 = SyncFileStorage(temp_storage_file)
        assert storage2.exists("https://example.com/page1") is True
        assert len(storage2.get_all()) == 1

    def test_load_empty_file_creates_empty_storage(self, temp_storage_file):
        """测试加载不存在的文件创建空存储"""
        storage = SyncFileStorage(temp_storage_file)
        assert storage.get_all() == []
        assert len(storage._url_index) == 0


class TestCrawlerConfig:
    """CrawlerConfig 默认值测试"""

    def test_default_values(self):
        """测试配置默认值"""
        config = CrawlerConfig()

        assert config.name == "crawler"
        assert config.timeout == 30
        assert config.retry_times == 3
        assert config.retry_delay == 1.0
        assert config.download_delay == 1.0
        assert config.concurrent == 5

    def test_browser_defaults(self):
        """测试浏览器配置默认值"""
        config = CrawlerConfig()

        assert config.headless is True
        assert "Chrome" in config.user_agent

    def test_proxy_defaults(self):
        """测试代理配置默认值"""
        config = CrawlerConfig()

        assert config.proxy_pool == []
        assert config.proxy_enabled is False
        assert config.proxy_check_interval == 300

    def test_storage_defaults(self):
        """测试存储配置默认值"""
        config = CrawlerConfig()

        assert config.storage_type == "file"
        assert config.storage_url == ""

    def test_rate_limit_defaults(self):
        """测试限流配置默认值"""
        config = CrawlerConfig()

        assert config.rate_limit == 10.0
        assert config.enable_rate_limit is True

    def test_feature_flags_defaults(self):
        """测试特性开关默认值"""
        config = CrawlerConfig()

        assert config.use_tls_bypass is True
        assert config.use_stealth_browser is True

    def test_custom_values(self):
        """测试自定义配置值"""
        config = CrawlerConfig(
            name="custom_crawler",
            timeout=60,
            retry_times=5,
            rate_limit=20.0,
        )

        assert config.name == "custom_crawler"
        assert config.timeout == 60
        assert config.retry_times == 5
        assert config.rate_limit == 20.0


class TestRequestMethod:
    """RequestMethod 枚举测试"""

    def test_request_method_enum_exists(self):
        """测试 RequestMethod 枚举存在"""
        assert hasattr(RequestMethod, "REQUESTS")
        assert hasattr(RequestMethod, "CURL_CFFI")
        assert hasattr(RequestMethod, "PLAYWRIGHT")
        assert hasattr(RequestMethod, "ASYNC_CURL")

    def test_request_method_values(self):
        """测试 RequestMethod 枚举值"""
        assert RequestMethod.REQUESTS.value == "requests"
        assert RequestMethod.CURL_CFFI.value == "curl_cffi"
        assert RequestMethod.PLAYWRIGHT.value == "playwright"
        assert RequestMethod.ASYNC_CURL.value == "async_curl"

    def test_request_method_is_enum(self):
        """验证是 Enum 类型"""
        from enum import Enum
        assert issubclass(RequestMethod, Enum)


class TestAdvancedCrawler:
    """AdvancedCrawler 集成测试 (不涉及真实网络)"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return CrawlerConfig(
            name="test_crawler",
            timeout=10,
            retry_times=2,
            use_stealth_browser=False,  # 禁用浏览器避免启动
        )

    @pytest.fixture
    def crawler(self, config, tmp_path):
        """创建 AdvancedCrawler 实例"""
        storage_path = str(tmp_path / "test_data.json")
        config.storage_type = "file"
        return AdvancedCrawler(config)

    def test_crawler_initializes_with_storage(self, crawler):
        """测试爬虫初始化时创建存储"""
        assert crawler.storage is not None
        assert hasattr(crawler.storage, "save")
        assert hasattr(crawler.storage, "exists")

    def test_crawler_initializes_with_rate_limiter(self, crawler):
        """测试爬虫初始化时创建限流器"""
        assert crawler.rate_limiter is not None

    def test_exponential_backoff(self, crawler):
        """测试指数退避计算"""
        # 第一次重试: delay * 2^0 = 1.0 * 1 = 1.0
        assert crawler._exponential_backoff(0) == 1.0
        # 第二次重试: delay * 2^1 = 1.0 * 2 = 2.0
        assert crawler._exponential_backoff(1) == 2.0
        # 第三次重试: delay * 2^2 = 1.0 * 4 = 4.0
        assert crawler._exponential_backoff(2) == 4.0

    def test_exponential_backoff_max_cap(self, crawler):
        """测试指数退避上限为 60 秒"""
        # 即使很大次数重试，也不超过 60
        assert crawler._exponential_backoff(10) == 60.0
        assert crawler._exponential_backoff(100) == 60.0
