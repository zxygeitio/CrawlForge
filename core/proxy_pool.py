"""
代理池管理模块
基于Redis的代理池实现，支持代理评分、自动切换等功能
"""

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import redis.asyncio as redis

from utils.logger import Logger, get_logger


class ProxyProtocol(Enum):
    """代理协议"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    ANY = "any"


class ProxyStatus(Enum):
    """代理状态"""
    AVAILABLE = "available"
    TESTING = "testing"
    UNAVAILABLE = "unavailable"
    BANNED = "banned"


@dataclass
class Proxy:
    """代理信息"""
    host: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: str = None
    password: str = None
    status: ProxyStatus = ProxyStatus.AVAILABLE
    score: float = 100.0
    success_count: int = 0
    fail_count: int = 0
    avg_response_time: float = 0.0
    last_check_time: float = 0
    last_success_time: float = 0
    tags: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        """获取代理URL"""
        if self.username and self.password:
            return f"{self.protocol.value}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol.value}://{self.host}:{self.port}"

    @property
    def is_available(self) -> bool:
        """代理是否可用"""
        return self.status == ProxyStatus.AVAILABLE and self.score > 0


@dataclass
class ProxyPoolConfig:
    """代理池配置"""
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = None
    proxy_key: str = "crawler:proxies"
    score_key: str = "crawler:proxy:scores"
    history_key: str = "crawler:proxy:history"
    min_score: float = 20.0
    max_proxies_per_fetch: int = 10
    test_url: str = "https://www.baidu.com"
    test_timeout: int = 10
    score_increment: float = 5.0
    score_decrement: float = 10.0
    decay_factor: float = 0.95


class ProxyPool:
    """
    异步代理池管理器

    基于Redis存储代理列表，支持代理评分、自动测试、
    失败重试、协议自动识别等功能。
    """

    def __init__(
        self,
        config: ProxyPoolConfig = None,
        logger: Logger = None
    ):
        """
        初始化代理池

        Args:
            config: 代理池配置
            logger: 日志记录器
        """
        self._config = config or ProxyPoolConfig()
        self._logger = logger or get_logger("ProxyPool")
        self._redis: redis.Redis = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._get_redis()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()

    async def _get_redis(self) -> redis.Redis:
        """获取或创建Redis连接"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._config.redis_host,
                port=self._config.redis_port,
                db=self._config.redis_db,
                password=self._config.redis_password,
                decode_responses=True
            )
        return self._redis

    async def close(self) -> None:
        """关闭Redis连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def add_proxy(self, proxy: Proxy) -> bool:
        """
        添加代理到池中

        Args:
            proxy: 代理对象

        Returns:
            是否添加成功
        """
        try:
            await self._get_redis()
            proxy_data = {
                "host": proxy.host,
                "port": proxy.port,
                "protocol": proxy.protocol.value,
                "username": proxy.username or "",
                "password": proxy.password or "",
                "status": proxy.status.value,
                "score": proxy.score,
                "success_count": proxy.success_count,
                "fail_count": proxy.fail_count,
                "avg_response_time": proxy.avg_response_time,
                "last_check_time": proxy.last_check_time,
                "last_success_time": proxy.last_success_time,
                "tags": ",".join(proxy.tags)
            }

            proxy_key = f"{self._config.proxy_key}:{proxy.host}:{proxy.port}"
            await self._redis.hset(proxy_key, mapping=proxy_data)
            await self._redis.sadd(self._config.proxy_key, proxy_key)

            self._logger.info(f"添加代理: {proxy.url}")
            return True

        except Exception as e:
            self._logger.error(f"添加代理失败: {e}")
            return False

    async def add_proxies(self, proxies: list[Proxy]) -> int:
        """
        批量添加代理

        Args:
            proxies: 代理列表

        Returns:
            成功添加的数量
        """
        count = 0
        for proxy in proxies:
            if await self.add_proxy(proxy):
                count += 1
        return count

    async def remove_proxy(self, host: str, port: int) -> bool:
        """
        从池中移除代理

        Args:
            host: 代理主机
            port: 代理端口

        Returns:
            是否移除成功
        """
        try:
            await self._get_redis()
            proxy_key = f"{self._config.proxy_key}:{host}:{port}"
            await self._redis.srem(self._config.proxy_key, proxy_key)
            await self._redis.delete(proxy_key)
            await self._redis.hdel(self._config.score_key, proxy_key)

            self._logger.info(f"移除代理: {host}:{port}")
            return True

        except Exception as e:
            self._logger.error(f"移除代理失败: {e}")
            return False

    async def get_proxy(self) -> Optional[Proxy]:
        """
        获取一个可用代理（根据评分权重）

        Returns:
            可用代理，如果没有可用代理则返回None
        """
        try:
            await self._get_redis()
            proxy_keys = await self._redis.smembers(self._config.proxy_key)

            if not proxy_keys:
                return None

            available_proxies = []
            for proxy_key in proxy_keys:
                proxy_data = await self._redis.hgetall(proxy_key)
                if not proxy_data:
                    continue

                proxy = self._dict_to_proxy(proxy_data)
                if proxy.is_available:
                    weight = proxy.score
                    for _ in range(int(weight)):
                        available_proxies.append(proxy)

            if not available_proxies:
                return None

            selected = random.choice(available_proxies)
            self._logger.debug(f"选中代理: {selected.url} (评分: {selected.score})")
            return selected

        except Exception as e:
            self._logger.error(f"获取代理失败: {e}")
            return None

    async def get_proxies(self, count: int = None) -> list[Proxy]:
        """
        获取多个可用代理

        Args:
            count: 要获取的数量，None表示获取所有

        Returns:
            可用代理列表
        """
        try:
            await self._get_redis()
            proxy_keys = await self._redis.smembers(self._config.proxy_key)

            if not proxy_keys:
                return []

            available_proxies = []
            for proxy_key in proxy_keys:
                proxy_data = await self._redis.hgetall(proxy_key)
                if not proxy_data:
                    continue

                proxy = self._dict_to_proxy(proxy_data)
                if proxy.is_available:
                    available_proxies.append(proxy)

            if count is None:
                return available_proxies

            return random.sample(
                available_proxies,
                min(count, len(available_proxies))
            )

        except Exception as e:
            self._logger.error(f"获取代理列表失败: {e}")
            return []

    async def report_proxy_result(
        self,
        host: str,
        port: int,
        success: bool,
        response_time: float = 0
    ) -> None:
        """
        报告代理使用结果

        用于更新代理评分

        Args:
            host: 代理主机
            port: 代理端口
            success: 请求是否成功
            response_time: 响应时间（秒）
        """
        try:
            await self._get_redis()
            proxy_key = f"{self._config.proxy_key}:{host}:{port}"

            current_data = await self._redis.hgetall(proxy_key)
            if not current_data:
                return

            proxy = self._dict_to_proxy(current_data)

            if success:
                proxy.success_count += 1
                proxy.last_success_time = time.time()

                total_time = proxy.avg_response_time * proxy.success_count
                proxy.avg_response_time = (total_time + response_time) / (proxy.success_count + 1)

                proxy.score = min(100, proxy.score + self._config.score_increment)

                proxy.status = ProxyStatus.AVAILABLE

            else:
                proxy.fail_count += 1
                proxy.score = max(0, proxy.score - self._config.score_decrement)

                if proxy.score < self._config.min_score:
                    proxy.status = ProxyStatus.UNAVAILABLE

            update_data = {
                "score": proxy.score,
                "success_count": proxy.success_count,
                "fail_count": proxy.fail_count,
                "avg_response_time": proxy.avg_response_time,
                "last_check_time": time.time(),
                "last_success_time": proxy.last_success_time,
                "status": proxy.status.value
            }

            await self._redis.hset(proxy_key, mapping=update_data)

            history_key = f"{self._config.history_key}:{host}:{port}"
            await self._redis.lpush(history_key, json.dumps({
                "success": success,
                "response_time": response_time,
                "timestamp": time.time()
            }))
            await self._redis.ltrim(history_key, 0, 99)

        except Exception as e:
            self._logger.error(f"更新代理状态失败: {e}")

    async def test_proxy(self, proxy: Proxy) -> bool:
        """
        测试代理是否可用

        Args:
            proxy: 代理对象

        Returns:
            代理是否可用
        """
        try:
            import aiohttp

            proxy_url = proxy.url
            timeout = aiohttp.ClientTimeout(total=self._config.test_timeout)

            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get(
                    self._config.test_url,
                    proxy=proxy_url,
                    timeout=timeout
                ) as resp:
                    response_time = time.time() - start_time
                    success = resp.status == 200

                    await self.report_proxy_result(
                        proxy.host,
                        proxy.port,
                        success,
                        response_time
                    )

                    return success

        except Exception as e:
            self._logger.debug(f"代理测试失败 {proxy.url}: {e}")
            await self.report_proxy_result(proxy.host, proxy.port, False)
            return False

    async def test_all_proxies(self) -> dict[str, bool]:
        """
        测试所有代理

        Returns:
            测试结果字典
        """
        proxies = await self.get_proxies()
        results = {}

        for proxy in proxies:
            results[proxy.url] = await self.test_proxy(proxy)

        return results

    async def get_proxy_stats(self) -> dict:
        """
        获取代理池统计信息

        Returns:
            统计信息字典
        """
        try:
            await self._get_redis()
            proxy_keys = await self._redis.smembers(self._config.proxy_key)

            stats = {
                "total": len(proxy_keys),
                "available": 0,
                "unavailable": 0,
                "banned": 0,
                "testing": 0,
                "avg_score": 0
            }

            total_score = 0
            for proxy_key in proxy_keys:
                proxy_data = await self._redis.hgetall(proxy_key)
                if not proxy_data:
                    continue

                status = proxy_data.get("status", "")
                if status == "available":
                    stats["available"] += 1
                elif status == "unavailable":
                    stats["unavailable"] += 1
                elif status == "banned":
                    stats["banned"] += 1
                elif status == "testing":
                    stats["testing"] += 1

                total_score += float(proxy_data.get("score", 0))

            if proxy_keys:
                stats["avg_score"] = total_score / len(proxy_keys)

            return stats

        except Exception as e:
            self._logger.error(f"获取统计信息失败: {e}")
            return {}

    def _dict_to_proxy(self, data: dict) -> Proxy:
        """将字典转换为Proxy对象"""
        tags = data.get("tags", "")
        return Proxy(
            host=data.get("host", ""),
            port=int(data.get("port", 0)),
            protocol=ProxyProtocol(data.get("protocol", "http")),
            username=data.get("username") or None,
            password=data.get("password") or None,
            status=ProxyStatus(data.get("status", "available")),
            score=float(data.get("score", 100)),
            success_count=int(data.get("success_count", 0)),
            fail_count=int(data.get("fail_count", 0)),
            avg_response_time=float(data.get("avg_response_time", 0)),
            last_check_time=float(data.get("last_check_time", 0)),
            last_success_time=float(data.get("last_success_time", 0)),
            tags=tags.split(",") if tags else []
        )


if __name__ == "__main__":
    async def test():
        config = ProxyPoolConfig()
        async with ProxyPool(config) as pool:
            proxy1 = Proxy(
                host="127.0.0.1",
                port=8080,
                protocol=ProxyProtocol.HTTP
            )
            await pool.add_proxy(proxy1)

            proxy2 = Proxy(
                host="127.0.0.2",
                port=8080,
                protocol=ProxyProtocol.HTTP,
                username="user",
                password="pass"
            )
            await pool.add_proxy(proxy2)

            proxy = await pool.get_proxy()
            print(f"获取代理: {proxy.url if proxy else 'None'}")

            stats = await pool.get_proxy_stats()
            print(f"代理池统计: {stats}")

            if proxy:
                await pool.report_proxy_result(proxy.host, proxy.port, True, 0.5)

            stats = await pool.get_proxy_stats()
            print(f"更新后统计: {stats}")

    asyncio.run(test())
