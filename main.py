"""
爬虫逆向框架主入口
整合所有模块，提供统一的入口点
"""

import asyncio
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.logger import Logger, get_logger, LogLevel
from utils.network import NetworkClient, RequestConfig, HttpMethod
from utils.crypto_utils import MD5, SHA, AES, DES, RSA, Base64Encoder
from core.har_parser import HARParser, HARLog
from core.js_decrypt import JSDecryptor, SignatureReconstructor
from core.signature import SignatureGenerator, SignatureConfig, SignatureAlgorithm
from core.proxy_pool import ProxyPool, ProxyPoolConfig, Proxy
from extractors.json_extractor import JSONExtractor
from extractors.html_extractor import HTMLExtractor
from extractors.base import ExtractionRule
from handlers.captcha.slider import SliderCaptchaHandler
from handlers.captcha.image import ImageCaptchaHandler
from handlers.retry import RetryHandler, RetryConfig, RetryStrategy, CircuitBreaker
from templates.site_template import (
    SiteConfig,
    BaseSiteTemplate,
    HARBasedSiteTemplate,
    DataPipeline
)


VERSION = "1.0.0"


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    name: str
    base_url: str
    har_file: Optional[str] = None
    output_file: Optional[str] = None
    log_level: LogLevel = LogLevel.INFO
    enable_proxy: bool = False
    proxy_redis_host: str = "localhost"
    proxy_redis_port: int = 6379


class CrawlerReverse:
    """
    爬虫逆向框架主类

    整合所有功能模块，提供简洁的API
    """

    def __init__(self, config: CrawlerConfig):
        """
        初始化爬虫逆向框架

        Args:
            config: 爬虫配置
        """
        self._config = config
        self._logger = get_logger("CrawlerReverse", config.log_level)
        self._network_client: NetworkClient = None
        self._proxy_pool: ProxyPool = None
        self._site_template: BaseSiteTemplate = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._network_client = NetworkClient()
        await self._network_client.__aenter__()

        if self._config.enable_proxy:
            proxy_config = ProxyPoolConfig(
                redis_host=self._config.proxy_redis_host,
                redis_port=self._config.proxy_redis_port
            )
            self._proxy_pool = ProxyPool(proxy_config)
            await self._proxy_pool.__aenter__()

        self._logger.info(f"爬虫逆向框架 v{VERSION} 初始化完成")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._proxy_pool:
            await self._proxy_pool.__aexit__(exc_type, exc_val, exc_tb)
        if self._network_client:
            await self._network_client.__aexit__(exc_type, exc_val, exc_tb)

    async def fetch(self, url: str, **kwargs):
        """
        发送HTTP请求

        Args:
            url: 请求URL
            **kwargs: 其他参数

        Returns:
            响应对象
        """
        proxy = None
        if self._proxy_pool:
            proxy_obj = await self._proxy_pool.get_proxy()
            if proxy_obj:
                proxy = proxy_obj.url

        config = RequestConfig(
            url=url,
            proxy=proxy,
            **kwargs
        )

        response = await self._network_client.request(config)

        if proxy:
            success = response.ok
            await self._proxy_pool.report_proxy_result(
                proxy.split(":")[0].split("//")[-1],
                int(proxy.split(":")[-1]),
                success
            )

        return response

    async def parse_har(self, har_file: str = None) -> HARLog:
        """
        解析HAR文件

        Args:
            har_file: HAR文件路径

        Returns:
            HARLog对象
        """
        har_file = har_file or self._config.har_file
        if not har_file:
            raise ValueError("未指定HAR文件")

        parser = HARParser(self._logger)
        har_log = parser.parse_file(har_file)

        self._logger.info(f"解析HAR文件: {har_file}")
        self._logger.info(f"条目数量: {len(har_log.entries)}")

        return har_log

    def create_signature_generator(
        self,
        secret_key: str,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.MD5
    ) -> SignatureGenerator:
        """
        创建签名生成器

        Args:
            secret_key: 密钥
            algorithm: 签名算法

        Returns:
            签名生成器
        """
        config = SignatureConfig(
            algorithm=algorithm,
            secret_key=secret_key
        )
        return SignatureGenerator(config, self._logger)

    async def add_proxy(self, proxy_url: str) -> bool:
        """
        添加代理到代理池

        Args:
            proxy_url: 代理URL

        Returns:
            是否添加成功
        """
        if not self._proxy_pool:
            self._logger.error("代理池未启用")
            return False

        parts = proxy_url.replace("http://", "").replace("https://", "").split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 8080

        proxy = Proxy(host=host, port=port)
        return await self._proxy_pool.add_proxy(proxy)

    async def get_proxy(self) -> Optional[Proxy]:
        """
        获取一个代理

        Returns:
            代理对象
        """
        if not self._proxy_pool:
            return None
        return await self._proxy_pool.get_proxy()

    async def test_proxy(self, proxy: Proxy) -> bool:
        """
        测试代理

        Args:
            proxy: 代理对象

        Returns:
            代理是否可用
        """
        if not self._proxy_pool:
            return False
        return await self._proxy_pool.test_proxy(proxy)


async def demo_basic_usage():
    """基础使用演示"""
    print("=" * 50)
    print("爬虫逆向框架 v1.0.0")
    print("=" * 50)

    config = CrawlerConfig(
        name="demo",
        base_url="https://httpbin.org"
    )

    async with CrawlerReverse(config) as crawler:
        print("\n--- 1. 基础HTTP请求 ---")
        response = await crawler.fetch(
            "https://httpbin.org/get",
            method=HttpMethod.GET
        )
        print(f"状态码: {response.status}")
        print(f"响应内容: {response.text[:200]}...")

        print("\n--- 2. POST请求 ---")
        response = await crawler.fetch(
            "https://httpbin.org/post",
            method=HttpMethod.POST,
            json_data={"username": "test", "password": "123456"}
        )
        print(f"POST响应: {response.json()}")

        print("\n--- 3. 加密工具演示 ---")
        md5_result = MD5.hash("Hello, World!")
        print(f"MD5: {md5_result}")

        sha_result = SHA.sha256("Hello, World!")
        print(f"SHA256: {sha_result}")

        aes = AES("0123456789abcdef", "0123456789abcdef")
        encrypted = aes.encrypt_base64("secret message")
        print(f"AES加密: {encrypted}")
        decrypted = aes.decrypt_base64(encrypted).decode("utf-8")
        print(f"AES解密: {decrypted}")

        print("\n--- 4. 签名生成演示 ---")
        sig_gen = crawler.create_signature_generator(
            secret_key="your_secret_key",
            algorithm=SignatureAlgorithm.MD5
        )
        params = {"app_id": "123456", "method": "user.info", "format": "json"}
        result = sig_gen.generate(params)
        print(f"签名: {result.sign}")
        print(f"带签名的参数: {result.params}")

        print("\n--- 5. 滑块验证码轨迹生成 ---")
        slider = SliderCaptchaHandler()
        trajectory = slider.generate_trajectory(200, duration=2.0)
        print(f"生成轨迹点数: {len(trajectory)}")
        print(f"起点: x={trajectory[0]['x']}, y={trajectory[0]['y']}")
        print(f"终点: x={trajectory[-1]['x']}, y={trajectory[-1]['y']}")


async def demo_proxy_pool():
    """代理池使用演示"""
    print("\n" + "=" * 50)
    print("代理池使用演示")
    print("=" * 50)

    config = CrawlerConfig(
        name="demo",
        base_url="https://httpbin.org",
        enable_proxy=True
    )

    async with CrawlerReverse(config) as crawler:
        proxy = Proxy(host="127.0.0.1", port=8080)
        success = await crawler.add_proxy("http://127.0.0.1:8080")
        print(f"添加代理: {'成功' if success else '失败'}")

        print("\n--- 代理统计 ---")
        if crawler._proxy_pool:
            stats = await crawler._proxy_pool.get_proxy_stats()
            print(f"总代理数: {stats.get('total', 0)}")
            print(f"可用代理: {stats.get('available', 0)}")


async def demo_retry_handler():
    """重试机制演示"""
    print("\n" + "=" * 50)
    print("重试机制演示")
    print("=" * 50)

    attempt_count = 0

    async def unreliable_api():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnectionError(f"模拟连接失败 (尝试 {attempt_count})")
        return {"status": "success", "attempts": attempt_count}

    config = RetryConfig(
        max_attempts=5,
        initial_delay=0.5,
        strategy=RetryStrategy.EXPONENTIAL,
        multiplier=2.0
    )
    handler = RetryHandler(config)

    print(f"执行不可靠API调用...")
    result = await handler.execute_async(unreliable_api)

    print(f"成功: {result.success}")
    print(f"尝试次数: {result.attempts}")
    print(f"总耗时: {result.total_time:.2f}s")
    print(f"延迟记录: {[f'{d:.2f}s' for d in result.delays]}")


async def demo_data_extractor():
    """数据提取演示"""
    print("\n" + "=" * 50)
    print("数据提取演示")
    print("=" * 50)

    sample_json = {
        "code": 0,
        "message": "success",
        "data": {
            "user": {
                "id": 1001,
                "name": "张三",
                "email": "zhangsan@example.com"
            },
            "items": [
                {"id": 1, "name": "商品A", "price": 100},
                {"id": 2, "name": "商品B", "price": 200}
            ],
            "total": 300
        }
    }

    rules = [
        ExtractionRule(name="user_id", selector="data.user.id", is_required=True),
        ExtractionRule(name="user_name", selector="data.user.name"),
        ExtractionRule(name="item_count", selector="data.items"),
        ExtractionRule(name="total", selector="data.total", processor=lambda x: float(x))
    ]

    extractor = JSONExtractor(rules)
    result = await extractor.extract(sample_json)

    print(f"提取成功: {result.success}")
    print(f"提取数据: {result.data}")
    if result.error:
        print(f"错误: {result.error}")


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="爬虫逆向框架 v1.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py demo                    # 运行演示
  python main.py fetch <url>             # 获取URL内容
  python main.py har <har_file>          # 解析HAR文件
  python main.py signature --key <key>   # 生成签名
        """
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("command", nargs="?", default="demo", help="命令")
    parser.add_argument("args", nargs="*", help="命令参数")
    parser.add_argument("--url", "-u", help="请求URL")
    parser.add_argument("--method", "-m", default="GET", help="HTTP方法")
    parser.add_argument("--data", "-d", help="请求数据 (JSON格式)")
    parser.add_argument("--har", help="HAR文件路径")
    parser.add_argument("--key", help="签名密钥")
    parser.add_argument("--output", "-o", help="输出文件")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    log_level = LogLevel[args.log_level]

    if args.command == "demo":
        print("运行演示...")
        asyncio.run(demo_basic_usage())
        asyncio.run(demo_proxy_pool())
        asyncio.run(demo_retry_handler())
        asyncio.run(demo_data_extractor())

    elif args.command == "fetch":
        if not args.url:
            print("错误: 请指定URL (--url)")
            sys.exit(1)

        config = CrawlerConfig(name="fetch", base_url="", log_level=log_level)

        async def fetch_url():
            async with CrawlerReverse(config) as crawler:
                method = HttpMethod[args.method.upper()] if args.method.upper() in [m.name for m in HttpMethod] else HttpMethod.GET
                json_data = json.loads(args.data) if args.data else None

                response = await crawler.fetch(args.url, method=method, json_data=json_data)

                if args.output:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    print(f"内容已保存到: {args.output}")
                else:
                    print(response.text)

        asyncio.run(fetch_url())

    elif args.command == "har":
        if not args.har and not args.args:
            print("错误: 请指定HAR文件 (--har <file>)")
            sys.exit(1)

        har_file = args.har or args.args[0]

        async def parse_har_file():
            config = CrawlerConfig(name="har_parser", base_url="", log_level=log_level)
            async with CrawlerReverse(config) as crawler:
                har_log = await crawler.parse_har(har_file)

                print(f"\nHAR文件分析结果:")
                print(f"  版本: {har_log.version}")
                print(f"  创建者: {har_log.creator.get('name', 'Unknown')}")
                print(f"  条目数量: {len(har_log.entries)}")

                parser = HARParser()
                endpoints = parser.extract_api_endpoints(har_log)

                print(f"\nAPI端点 ({len(endpoints)} 个):")
                for path, methods in list(endpoints.items())[:10]:
                    print(f"  {', '.join(methods)} {path}")

                signatures = parser.extract_signatures(har_log)
                print(f"\n签名参数 ({len(signatures)} 个):")
                for sig in signatures[:5]:
                    print(f"  {sig['name']} = {sig['value'][:30]}...")

        asyncio.run(parse_har_file())

    elif args.command == "signature":
        if not args.key:
            print("错误: 请指定签名密钥 (--key <key>)")
            sys.exit(1)

        sig_gen = SignatureGenerator(
            SignatureConfig(secret_key=args.key),
            get_logger("Signature", log_level)
        )

        params = {}
        if args.args:
            for arg in args.args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    params[key] = value

        result = sig_gen.generate(params)

        print(f"\n签名结果:")
        print(f"  签名: {result.sign}")
        print(f"  参数: {result.params}")

    else:
        print(f"未知命令: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
