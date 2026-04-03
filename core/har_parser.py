"""
HAR文件解析模块
提供HAR (HTTP Archive Format) 文件的解析功能
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..utils.logger import Logger, get_logger


@dataclass
class HARHeader:
    """HTTP头部"""
    name: str
    value: str
    comment: Optional[str] = None


@dataclass
class HARQueryParam:
    """查询参数"""
    name: str
    value: str
    comment: Optional[str] = None


@dataclass
class HARPostData:
    """POST数据"""
    mime_type: str
    text: str
    params: list[dict] = field(default_factory=list)


@dataclass
class HARRequest:
    """HAR请求"""
    method: str
    url: str
    http_version: str
    headers: list[HARHeader]
    query_string: list[HARQueryParam]
    post_data: Optional[HARPostData] = None
    headers_size: int = -1
    body_size: int = -1


@dataclass
class HARResponse:
    """HAR响应"""
    status: int
    status_text: str
    http_version: str
    headers: list[HARHeader]
    content: dict
    redirect_url: str = ""
    headers_size: int = -1
    body_size: int = -1


@dataclass
class HAREntry:
    """HAR条目"""
    request: HARRequest
    response: HARResponse
    time: float
    started_date_time: datetime
    wait_time: float = 0
    receive_time: float = 0


@dataclass
class HARLog:
    """HAR日志"""
    version: str
    creator: dict
    entries: list[HAREntry]
    pages: list[dict] = field(default_factory=list)


class HARParser:
    """
    HAR文件解析器

    解析浏览器导出的HAR文件，提取请求/响应信息，
    支持筛选特定域名的请求、搜索特定参数等功能。
    """

    def __init__(self, logger: Logger = None):
        """
        初始化HAR解析器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("HARParser")

    def parse_file(self, file_path: str) -> HARLog:
        """
        解析HAR文件

        Args:
            file_path: HAR文件路径

        Returns:
            HARLog对象
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.parse(data)

    def parse(self, data: dict) -> HARLog:
        """
        解析HAR数据

        Args:
            data: HAR格式的字典数据

        Returns:
            HARLog对象
        """
        log = data.get("log", {})
        version = log.get("version", "1.2")
        creator = log.get("creator", {})

        entries = []
        for entry_data in log.get("entries", []):
            entry = self._parse_entry(entry_data)
            if entry:
                entries.append(entry)

        pages = log.get("pages", [])

        return HARLog(
            version=version,
            creator=creator,
            entries=entries,
            pages=pages
        )

    def _parse_entry(self, entry_data: dict) -> Optional[HAREntry]:
        """解析单个条目"""
        try:
            request_data = entry_data.get("request", {})
            request = HARRequest(
                method=request_data.get("method", "GET"),
                url=request_data.get("url", ""),
                http_version=request_data.get("httpVersion", "HTTP/1.1"),
                headers=self._parse_headers(request_data.get("headers", [])),
                query_string=self._parse_query_params(request_data.get("queryString", [])),
                post_data=self._parse_post_data(request_data.get("postData"))
            )

            response_data = entry_data.get("response", {})
            response = HARResponse(
                status=response_data.get("status", 0),
                status_text=response_data.get("statusText", ""),
                http_version=response_data.get("httpVersion", "HTTP/1.1"),
                headers=self._parse_headers(response_data.get("headers", [])),
                content=response_data.get("content", {}),
                redirect_url=response_data.get("redirectURL", "")
            )

            started_date_time_str = entry_data.get("startedDateTime", "")
            started_date_time = datetime.fromisoformat(
                started_date_time_str.replace("Z", "+00:00")
            ) if started_date_time_str else datetime.now()

            return HAREntry(
                request=request,
                response=response,
                time=entry_data.get("time", 0),
                started_date_time=started_date_time,
                wait_time=entry_data.get("timings", {}).get("wait", 0),
                receive_time=entry_data.get("timings", {}).get("receive", 0)
            )
        except Exception as e:
            self._logger.warning(f"解析HAR条目失败: {e}")
            return None

    def _parse_headers(self, headers_data: list) -> list[HARHeader]:
        """解析头部列表"""
        return [
            HARHeader(
                name=h.get("name", ""),
                value=h.get("value", ""),
                comment=h.get("comment")
            )
            for h in headers_data
        ]

    def _parse_query_params(self, params_data: list) -> list[HARQueryParam]:
        """解析查询参数列表"""
        return [
            HARQueryParam(
                name=p.get("name", ""),
                value=p.get("value", ""),
                comment=p.get("comment")
            )
            for p in params_data
        ]

    def _parse_post_data(self, post_data_data: dict) -> Optional[HARPostData]:
        """解析POST数据"""
        if not post_data_data:
            return None
        return HARPostData(
            mime_type=post_data_data.get("mimeType", ""),
            text=post_data_data.get("text", ""),
            params=post_data_data.get("params", [])
        )

    def filter_by_domain(self, har_log: HARLog, domain: str) -> list[HAREntry]:
        """
        筛选指定域名的请求

        Args:
            har_log: HAR日志对象
            domain: 域名（支持正则表达式）

        Returns:
            匹配的条目列表
        """
        pattern = re.compile(domain)
        return [
            entry for entry in har_log.entries
            if pattern.search(entry.request.url)
        ]

    def filter_by_url_pattern(self, har_log: HARLog, pattern: str) -> list[HAREntry]:
        """
        按URL模式筛选请求

        Args:
            har_log: HAR日志对象
            pattern: URL模式（支持正则表达式）

        Returns:
            匹配的条目列表
        """
        regex = re.compile(pattern)
        return [
            entry for entry in har_log.entries
            if regex.search(entry.request.url)
        ]

    def filter_by_method(self, har_log: HARLog, method: str) -> list[HAREntry]:
        """
        筛选指定HTTP方法的请求

        Args:
            har_log: HAR日志对象
            method: HTTP方法（如 GET, POST）

        Returns:
            匹配的条目列表
        """
        return [
            entry for entry in har_log.entries
            if entry.request.method.upper() == method.upper()
        ]

    def filter_by_content_type(self, har_log: HARLog, mime_type: str) -> list[HAREntry]:
        """
        筛选指定内容类型的响应

        Args:
            har_log: HAR日志对象
            mime_type: MIME类型（如 application/json）

        Returns:
            匹配的条目列表
        """
        return [
            entry for entry in har_log.entries
            if mime_type.lower() in entry.response.content.get("mimeType", "").lower()
        ]

    def extract_api_endpoints(self, har_log: HARLog) -> dict[str, list[str]]:
        """
        提取API端点

        Args:
            har_log: HAR日志对象

        Returns:
            端点字典，键为路径，值为请求方法列表
        """
        endpoints: dict[str, list[str]] = {}
        for entry in har_log.entries:
            url = entry.request.url
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path

                if path not in endpoints:
                    endpoints[path] = []
                if entry.request.method not in endpoints[path]:
                    endpoints[path].append(entry.request.method)
            except Exception:
                continue
        return endpoints

    def extract_signatures(self, har_log: HARLog) -> list[dict]:
        """
        提取可能用于签名的参数

        查找包含 sign、token、signature、nonce、timestamp 等关键字的参数

        Args:
            har_log: HAR日志对象

        Returns:
            签名参数列表
        """
        signature_keywords = ["sign", "token", "signature", "nonce", "timestamp", "salt", "key"]
        signatures: list[dict] = []

        for entry in har_log.entries:
            for param in entry.request.query_string:
                if any(kw in param.name.lower() for kw in signature_keywords):
                    signatures.append({
                        "name": param.name,
                        "value": param.value,
                        "url": entry.request.url,
                        "method": entry.request.method
                    })

            if entry.request.post_data:
                for param in entry.request.post_data.params:
                    if any(kw in param.get("name", "").lower() for kw in signature_keywords):
                        signatures.append({
                            "name": param.get("name"),
                            "value": param.get("value"),
                            "url": entry.request.url,
                            "method": entry.request.method
                        })

        return signatures

    def get_request_body(self, entry: HAREntry) -> Optional[str]:
        """
        获取请求体内容

        Args:
            entry: HAR条目

        Returns:
            请求体字符串
        """
        if entry.request.post_data:
            return entry.request.post_data.text
        return None

    def get_response_body(self, entry: HAREntry) -> Optional[str]:
        """
        获取响应体内容

        Args:
            entry: HAR条目

        Returns:
            响应体字符串
        """
        content = entry.response.content
        if "text" in content:
            return content["text"]
        return None


if __name__ == "__main__":
    parser = HARParser()

    sample_har = {
        "log": {
            "version": "1.2",
            "creator": {
                "name": "Test",
                "version": "1.0"
            },
            "entries": [
                {
                    "startedDateTime": "2024-01-01T00:00:00Z",
                    "time": 100,
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/data?sign=abc123",
                        "httpVersion": "HTTP/1.1",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "queryString": [
                            {"name": "sign", "value": "abc123"},
                            {"name": "timestamp", "value": "1234567890"}
                        ],
                        "postData": None
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "httpVersion": "HTTP/1.1",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"code": 0, "data": {"id": 1}}'
                        },
                        "redirectURL": ""
                    },
                    "timings": {
                        "wait": 50,
                        "receive": 10
                    }
                }
            ]
        }
    }

    har_log = parser.parse(sample_har)
    print(f"HAR版本: {har_log.version}")
    print(f"条目数量: {len(har_log.entries)}")

    for entry in har_log.entries:
        print(f"\n请求: {entry.request.method} {entry.request.url}")
        print(f"响应状态: {entry.response.status}")
        print(f"耗时: {entry.time}ms")

    endpoints = parser.extract_api_endpoints(har_log)
    print(f"\nAPI端点: {endpoints}")

    sigs = parser.extract_signatures(har_log)
    print(f"\n签名参数: {sigs}")
