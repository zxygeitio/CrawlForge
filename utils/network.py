"""
网络请求封装模块
基于 aiohttp 的异步 HTTP 客户端
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union
from urllib.parse import urljoin, urlencode

import aiohttp

from .logger import Logger, get_logger


class HttpMethod(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ResponseType(Enum):
    """响应类型枚举"""
    TEXT = "text"
    JSON = "json"
    BYTES = "bytes"
    AUTO = "auto"


@dataclass
class RequestConfig:
    """请求配置"""
    method: HttpMethod = HttpMethod.GET
    url: str = ""
    params: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    data: Any = None
    json_data: dict = None
    cookies: dict = field(default_factory=dict)
    timeout: int = 30
    allow_redirects: bool = True
    verify_ssl: bool = True
    proxy: str = None
    response_type: ResponseType = ResponseType.AUTO


@dataclass
class Response:
    """HTTP响应封装"""
    status: int
    headers: dict
    body: Any
    text: str
    cookies: dict
    url: str
    request_config: RequestConfig

    @property
    def ok(self) -> bool:
        """请求是否成功"""
        return 200 <= self.status < 300

    def json(self) -> Any:
        """解析JSON响应"""
        if isinstance(self.body, (dict, list)):
            return self.body
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        """请求失败时抛出异常"""
        if not self.ok:
            raise HttpError(
                f"HTTP {self.status} Error",
                status=self.status,
                response=self
            )


class HttpError(Exception):
    """HTTP错误异常"""

    def __init__(self, message: str, status: int = None, response: Response = None):
        super().__init__(message)
        self.status = status
        self.response = response


class NetworkClient:
    """
    异步网络请求客户端

    基于 aiohttp 的封装，提供简洁的 API 支持，
    支持代理、重试、并发控制等功能。
    """

    def __init__(
        self,
        logger: Logger = None,
        default_timeout: int = 30,
        default_headers: dict = None,
        max_connections: int = 100
    ):
        """
        初始化网络客户端

        Args:
            logger: 日志记录器
            default_timeout: 默认超时时间（秒）
            default_headers: 默认请求头
            max_connections: 最大并发连接数
        """
        self._logger = logger or get_logger("NetworkClient")
        self._default_timeout = default_timeout
        self._default_headers = default_headers or {}
        self._max_connections = max_connections
        self._semaphore: asyncio.Semaphore = None
        self._session: aiohttp.ClientSession = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建会话"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self._max_connections,
                limit_per_host=self._max_connections
            )
            timeout = aiohttp.ClientTimeout(total=self._default_timeout)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
            self._semaphore = asyncio.Semaphore(self._max_connections)
        return self._session

    async def close(self) -> None:
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def request(self, config: RequestConfig) -> Response:
        """
        发送HTTP请求

        Args:
            config: 请求配置

        Returns:
            响应对象
        """
        await self._get_session()

        async with self._semaphore:
            try:
                return await self._do_request(config)
            except aiohttp.ClientError as e:
                self._logger.error(f"请求错误: {e}, URL: {config.url}")
                raise HttpError(f"请求失败: {e}") from e
            except asyncio.TimeoutError:
                self._logger.error(f"请求超时: {config.url}")
                raise HttpError("请求超时")

    async def _do_request(self, config: RequestConfig) -> Response:
        """执行实际的HTTP请求"""
        headers = {**self._default_headers, **config.headers}

        timeout = aiohttp.ClientTimeout(total=config.timeout)

        async with self._session.request(
            method=config.method.value,
            url=config.url,
            params=config.params if config.params else None,
            headers=headers,
            data=config.data,
            json=config.json_data,
            cookies=config.cookies,
            timeout=timeout,
            allow_redirects=config.allow_redirects,
            ssl=config.verify_ssl if isinstance(config.verify_ssl, bool) else None,
            proxy=config.proxy
        ) as resp:
            body = await resp.read()

            if config.response_type == ResponseType.JSON or (
                config.response_type == ResponseType.AUTO and
                "application/json" in resp.headers.get("Content-Type", "")
            ):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    pass

            return Response(
                status=resp.status,
                headers=dict(resp.headers),
                body=body,
                text=body.decode("utf-8") if isinstance(body, bytes) else str(body),
                cookies=dict(resp.cookies),
                url=str(resp.url),
                request_config=config
            )

    async def get(
        self,
        url: str,
        params: dict = None,
        headers: dict = None,
        **kwargs
    ) -> Response:
        """
        发送GET请求

        Args:
            url: 请求URL
            params: 查询参数
            headers: 请求头
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        config = RequestConfig(
            method=HttpMethod.GET,
            url=url,
            params=params,
            headers=headers,
            **kwargs
        )
        return await self.request(config)

    async def post(
        self,
        url: str,
        data: Any = None,
        json_data: dict = None,
        headers: dict = None,
        **kwargs
    ) -> Response:
        """
        发送POST请求

        Args:
            url: 请求URL
            data: 表单数据
            json_data: JSON数据
            headers: 请求头
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        config = RequestConfig(
            method=HttpMethod.POST,
            url=url,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs
        )
        return await self.request(config)

    async def put(
        self,
        url: str,
        data: Any = None,
        json_data: dict = None,
        headers: dict = None,
        **kwargs
    ) -> Response:
        """
        发送PUT请求

        Args:
            url: 请求URL
            data: 表单数据
            json_data: JSON数据
            headers: 请求头
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        config = RequestConfig(
            method=HttpMethod.PUT,
            url=url,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs
        )
        return await self.request(config)

    async def delete(
        self,
        url: str,
        headers: dict = None,
        **kwargs
    ) -> Response:
        """
        发送DELETE请求

        Args:
            url: 请求URL
            headers: 请求头
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        config = RequestConfig(
            method=HttpMethod.DELETE,
            url=url,
            headers=headers,
            **kwargs
        )
        return await self.request(config)


class BatchRequest:
    """
    批量请求管理器

    用于并发发送多个请求，控制并发数量
    """

    def __init__(
        self,
        client: NetworkClient,
        max_concurrency: int = 10,
        logger: Logger = None
    ):
        """
        初始化批量请求管理器

        Args:
            client: 网络客户端
            max_concurrency: 最大并发数
            logger: 日志记录器
        """
        self._client = client
        self._max_concurrency = max_concurrency
        self._logger = logger or get_logger("BatchRequest")

    async def execute(
        self,
        configs: list[RequestConfig]
    ) -> list[Response]:
        """
        批量执行请求

        Args:
            configs: 请求配置列表

        Returns:
            响应列表
        """
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def bounded_request(config: RequestConfig) -> Response:
            async with semaphore:
                return await self._client.request(config)

        tasks = [bounded_request(config) for config in configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._logger.error(f"请求 {i} 失败: {result}")
                valid_results.append(None)
            else:
                valid_results.append(result)

        return valid_results


if __name__ == "__main__":
    async def test():
        async with NetworkClient() as client:
            resp = await client.get("https://httpbin.org/get")
            print(f"状态码: {resp.status}")
            print(f"响应: {resp.text[:200]}")

            resp = await client.post(
                "https://httpbin.org/post",
                json_data={"key": "value"}
            )
            print(f"POST响应: {resp.json()}")

    asyncio.run(test())
