"""
站点模板模块
提供站点爬取的通用模板和基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from core.har_parser import HARLog, HARParser
from core.signature import SignatureGenerator, SignatureConfig, SignatureAlgorithm
from extractors.base import BaseExtractor, ExtractionResult
from utils.logger import Logger, get_logger
from utils.network import NetworkClient, RequestConfig, HttpMethod


@dataclass
class SiteConfig:
    """站点配置"""
    name: str
    base_url: str
    headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    timeout: int = 30
    enable_proxy: bool = False
    proxy_url: str = None
    signature_config: SignatureConfig = None


@dataclass
class PageResult:
    """页面爬取结果"""
    url: str
    success: bool
    data: Any = None
    error: str = None
    status_code: int = 0


class BaseSiteTemplate(ABC):
    """
    站点爬取模板基类

    提供站点爬取的通用流程和接口
    """

    def __init__(
        self,
        config: SiteConfig,
        logger: Logger = None
    ):
        """
        初始化站点模板

        Args:
            config: 站点配置
            logger: 日志记录器
        """
        self._config = config
        self._logger = logger or get_logger(f"SiteTemplate-{config.name}")
        self._network_client: NetworkClient = None
        self._signature_generator: SignatureGenerator = None

        if config.signature_config:
            self._signature_generator = SignatureGenerator(config.signature_config)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._network_client = NetworkClient(
            default_headers=self._config.headers,
            default_timeout=self._config.timeout
        )
        await self._network_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._network_client:
            await self._network_client.__aexit__(exc_type, exc_val, exc_tb)

    async def fetch_page(self, url: str, **kwargs) -> PageResult:
        """
        获取页面

        Args:
            url: 页面URL
            **kwargs: 其他参数

        Returns:
            页面结果
        """
        full_url = self._build_url(url)

        config = RequestConfig(
            method=HttpMethod.GET,
            url=full_url,
            cookies=self._config.cookies,
            proxy=self._config.proxy_url if self._config.enable_proxy else None,
            **kwargs
        )

        try:
            response = await self._network_client.request(config)

            return PageResult(
                url=full_url,
                success=response.ok,
                data=response.body,
                status_code=response.status
            )

        except Exception as e:
            self._logger.error(f"获取页面失败: {e}")
            return PageResult(
                url=full_url,
                success=False,
                error=str(e)
            )

    async def post_data(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        **kwargs
    ) -> PageResult:
        """
        提交数据

        Args:
            url: 页面URL
            data: 表单数据
            json_data: JSON数据
            **kwargs: 其他参数

        Returns:
            页面结果
        """
        full_url = self._build_url(url)

        if self._signature_generator and json_data:
            signed_data = self._signature_generator.add_signature_to_params(json_data)
            json_data = signed_data

        config = RequestConfig(
            method=HttpMethod.POST,
            url=full_url,
            data=data,
            json_data=json_data,
            cookies=self._config.cookies,
            proxy=self._config.proxy_url if self._config.enable_proxy else None,
            **kwargs
        )

        try:
            response = await self._network_client.request(config)

            return PageResult(
                url=full_url,
                success=response.ok,
                data=response.body,
                status_code=response.status
            )

        except Exception as e:
            self._logger.error(f"提交数据失败: {e}")
            return PageResult(
                url=full_url,
                success=False,
                error=str(e)
            )

    def _build_url(self, url: str) -> str:
        """
        构建完整URL

        Args:
            url: 相对或绝对URL

        Returns:
            完整的URL
        """
        if url.startswith("http://") or url.startswith("https://"):
            return url

        from urllib.parse import urljoin
        return urljoin(self._config.base_url, url)

    @abstractmethod
    async def parse_page(self, page_result: PageResult) -> Any:
        """
        解析页面

        Args:
            page_result: 页面结果

        Returns:
            解析后的数据
        """
        pass

    async def crawl(self, **kwargs) -> Any:
        """
        执行爬取

        Returns:
            爬取结果
        """
        raise NotImplementedError("子类必须实现crawl方法")


class HARBasedSiteTemplate(BaseSiteTemplate):
    """
    基于HAR的站点模板

    从HAR文件分析站点并自动配置爬取参数
    """

    def __init__(
        self,
        config: SiteConfig,
        har_file: str = None,
        logger: Logger = None
    ):
        """
        初始化HAR-based站点模板

        Args:
            config: 站点配置
            har_file: HAR文件路径
            logger: 日志记录器
        """
        super().__init__(config, logger)
        self._har_file = har_file
        self._har_parser: HARParser = None
        self._har_log: HARLog = None

        if har_file:
            self._har_parser = HARParser()
            self._har_log = self._har_parser.parse_file(har_file)
            self._analyze_har()

    def _analyze_har(self) -> None:
        """分析HAR文件，提取站点配置"""
        if not self._har_log:
            return

        for entry in self._har_log.entries[:10]:
            for header in entry.request.headers:
                if header.name.lower() == "user-agent":
                    if "User-Agent" not in self._config.headers:
                        self._config.headers["User-Agent"] = header.value

            for param in entry.request.query_string:
                if param.name in ["sign", "token", "timestamp"]:
                    self._logger.info(f"发现签名参数: {param.name}")

    def extract_api_endpoints(self) -> dict:
        """
        提取API端点

        Returns:
            API端点字典
        """
        if not self._har_parser:
            return {}
        return self._har_parser.extract_api_endpoints(self._har_log)

    def get_signatures(self) -> list:
        """
        提取签名信息

        Returns:
            签名信息列表
        """
        if not self._har_parser:
            return []
        return self._har_parser.extract_signatures(self._har_log)

    async def parse_page(self, page_result: PageResult) -> Any:
        """解析页面"""
        return page_result.data


class BatchCrawlerTemplate:
    """
    批量爬取模板

    用于批量爬取多个页面或多个站点
    """

    def __init__(
        self,
        templates: list[BaseSiteTemplate],
        max_concurrency: int = 5,
        logger: Logger = None
    ):
        """
        初始化批量爬取模板

        Args:
            templates: 站点模板列表
            max_concurrency: 最大并发数
            logger: 日志记录器
        """
        self._templates = templates
        self._max_concurrency = max_concurrency
        self._logger = logger or get_logger("BatchCrawler")

    async def crawl_all(self) -> list[Any]:
        """
        爬取所有站点

        Returns:
            爬取结果列表
        """
        import asyncio

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def crawl_with_limit(template: BaseSiteTemplate) -> Any:
            async with semaphore:
                async with template:
                    return await template.crawl()

        tasks = [crawl_with_limit(t) for t in self._templates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._logger.error(f"站点 {i} 爬取失败: {result}")
                valid_results.append(None)
            else:
                valid_results.append(result)

        return valid_results


class DataPipeline:
    """
    数据处理管道

    支持多个提取器的链式调用
    """

    def __init__(self, logger: Logger = None):
        """
        初始化数据处理管道

        Args:
            logger: 日志记录器
        """
        self._extractors: list[BaseExtractor] = []
        self._logger = logger or get_logger("DataPipeline")

    def add_extractor(self, extractor: BaseExtractor) -> None:
        """
        添加提取器

        Args:
            extractor: 提取器实例
        """
        self._extractors.append(extractor)

    async def process(self, raw_data: Any) -> dict:
        """
        处理数据

        Args:
            raw_data: 原始数据

        Returns:
            处理结果字典
        """
        current_data = raw_data
        results: dict = {}

        for i, extractor in enumerate(self._extractors):
            try:
                result = await extractor.extract(current_data)

                if result.success:
                    results[f"step_{i}"] = result.data
                    current_data = result.data
                else:
                    self._logger.warning(
                        f"提取器 {i} 执行失败: {result.error}"
                    )

            except Exception as e:
                self._logger.error(f"提取器 {i} 执行异常: {e}")

        return results


if __name__ == "__main__":
    print("=== 站点模板测试 ===")

    config = SiteConfig(
        name="example",
        base_url="https://httpbin.org",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
    )

    print(f"站点配置: {config.name}, {config.base_url}")

    print("\n=== 数据处理管道测试 ===")

    from extractors.json_extractor import JSONExtractor
    from extractors.base import ExtractionRule

    pipeline = DataPipeline()

    rules = [
        ExtractionRule(name="origin", selector="origin"),
        ExtractionRule(name="url", selector="url")
    ]
    extractor = JSONExtractor(rules)
    pipeline.add_extractor(extractor)

    print("数据处理管道已创建")

    async def test_site_template():
        async with BaseSiteTemplate(config) as site:
            result = await site.fetch_page("/get")
            print(f"GET请求状态: {result.status_code}")
            print(f"成功: {result.success}")

            result = await site.post_data("/post", json_data={"key": "value"})
            print(f"POST请求状态: {result.status_code}")

    asyncio.run(test_site_template())
