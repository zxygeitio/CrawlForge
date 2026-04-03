"""
代理池管理器 v2
- 代理评分机制
- 健康检查
- 自动淘汰
- 故障转移
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import aiohttp


class ProxyStatus(Enum):
    """代理状态"""
    UNKNOWN = "unknown"
    ALIVE = "alive"
    DEAD = "dead"
    CHECKING = "checking"
    RATE_LIMITED = "rate_limited"


@dataclass
class Proxy:
    """代理信息"""
    url: str
    status: ProxyStatus = ProxyStatus.UNKNOWN
    score: float = 100.0  # 评分 0-100
    success_count: int = 0
    fail_count: int = 0
    last_check: float = 0
    last_success: float = 0
    avg_latency: float = 0
    tags: dict = field(default_factory=dict)  # 代理标签：country, type等


@dataclass
class ProxyPoolConfig:
    """代理池配置"""
    min_score: float = 50.0  # 低于此分数淘汰
    max_fail_rate: float = 0.5  # 失败率阈值
    check_interval: int = 300  # 健康检查间隔(秒)
    check_timeout: int = 10  # 检查超时(秒)
    check_url: str = "https://httpbin.org/ip"  # 检查用URL
    concurrent_check: int = 5  # 并发检查数


class ProxyPoolManager:
    """
    增强型代理池管理器

    特性:
    - 评分机制 (成功率、延迟、可用性)
    - 自动健康检查
    - 故障自动转移
    - 代理标签过滤
    """

    def __init__(self, config: ProxyPoolConfig = None):
        self.config = config or ProxyPoolConfig()
        self.proxies: dict[str, Proxy] = {}
        self._lock = asyncio.Lock()
        self._check_task: Optional[asyncio.Task] = None

    async def add_proxy(self, proxy_url: str, tags: dict = None) -> bool:
        """添加代理"""
        async with self._lock:
            if proxy_url in self.proxies:
                return False

            proxy = Proxy(
                url=proxy_url,
                tags=tags or {}
            )
            self.proxies[proxy_url] = proxy
            return True

    async def add_proxies(self, proxy_urls: list[str]):
        """批量添加代理"""
        tasks = [self.add_proxy(url) for url in proxy_urls]
        await asyncio.gather(*tasks)

    async def remove_proxy(self, proxy_url: str):
        """移除代理"""
        async with self._lock:
            self.proxies.pop(proxy_url, None)

    def get_proxy(
        self,
        tags: dict = None,
        prefer_high_score: bool = True
    ) -> Optional[Proxy]:
        """
        获取最佳代理

        Args:
            tags: 代理标签要求
            prefer_high_score: 是否优先高评分
        """
        candidates = []

        for proxy in self.proxies.values():
            if proxy.status == ProxyStatus.DEAD:
                continue

            # 标签过滤
            if tags:
                match = all(
                    proxy.tags.get(k) == v
                    for k, v in tags.items()
                )
                if not match:
                    continue

            candidates.append(proxy)

        if not candidates:
            return None

        # 按评分排序
        if prefer_high_score:
            candidates.sort(key=lambda p: p.score, reverse=True)
            # 权重随机：高分代理更容易被选中
            return self._weighted_random_select(candidates)
        else:
            return random.choice(candidates)

    def _weighted_random_select(self, proxies: list[Proxy]) -> Proxy:
        """
        加权随机选择

        评分高的代理有更高概率被选中
        """
        weights = [max(p.score, 1) for p in proxies]
        total = sum(weights)
        r = random.uniform(0, total)

        cumulative = 0
        for proxy in proxies:
            cumulative += max(proxy.score, 1)
            if cumulative >= r:
                return proxy

        return proxies[-1]

    async def get_proxy_async(
        self,
        tags: dict = None,
        prefer_high_score: bool = True
    ) -> Optional[Proxy]:
        """
        异步获取最佳代理

        Args:
            tags: 代理标签要求
            prefer_high_score: 是否优先高评分
        """
        async with self._lock:
            candidates = []

            for proxy in self.proxies.values():
                if proxy.status == ProxyStatus.DEAD:
                    continue

                # 标签过滤
                if tags:
                    match = all(
                        proxy.tags.get(k) == v
                        for k, v in tags.items()
                    )
                    if not match:
                        continue

                candidates.append(proxy)

            if not candidates:
                return None

            # 按评分排序
            if prefer_high_score:
                candidates.sort(key=lambda p: p.score, reverse=True)
                return self._weighted_random_select(candidates)
            else:
                return random.choice(candidates)

    async def report_result(
        self,
        proxy_url: str,
        success: bool,
        latency: float = None
    ):
        """
        上报代理使用结果

        Args:
            proxy_url: 代理URL
            success: 是否成功
            latency: 响应延迟(秒)
        """
        async with self._lock:
            proxy = self.proxies.get(proxy_url)
            if not proxy:
                return

            # 更新计数
            if success:
                proxy.success_count += 1
                proxy.last_success = time.time()

                if latency is not None:
                    # 滑动平均更新延迟
                    if proxy.avg_latency == 0:
                        proxy.avg_latency = latency
                    else:
                        proxy.avg_latency = proxy.avg_latency * 0.7 + latency * 0.3
            else:
                proxy.fail_count += 1

            # 计算评分
            total = proxy.success_count + proxy.fail_count
            if total > 0:
                success_rate = proxy.success_count / total

                # 评分 = 成功率 * 70 + 延迟得分 * 30
                latency_score = max(0, 100 - proxy.avg_latency * 10) if proxy.avg_latency > 0 else 50
                proxy.score = success_rate * 70 + latency_score * 30

                # 失败率过高降分
                if success_rate < self.config.max_fail_rate:
                    proxy.score *= 0.5

            # 死亡代理标记
            if proxy.score < self.config.min_score:
                proxy.status = ProxyStatus.DEAD

    def _normalize_proxy_url(self, proxy_url: str) -> str:
        """标准化代理URL格式"""
        # 支持的协议前缀
        valid_prefixes = ('http://', 'https://', 'socks5://', 'socks4://')
        if any(proxy_url.startswith(p) for p in valid_prefixes):
            return proxy_url
        # 没有协议前缀，默认添加http://
        return f"http://{proxy_url}"

    async def check_proxy_health(self, proxy: Proxy) -> bool:
        """检查单个代理健康状态"""
        proxy.status = ProxyStatus.CHECKING

        try:
            normalized_proxy = self._normalize_proxy_url(proxy.url)

            async with aiohttp.ClientSession() as session:
                start = time.time()
                async with session.get(
                    self.config.check_url,
                    proxy=normalized_proxy,
                    timeout=aiohttp.ClientTimeout(total=self.config.check_timeout)
                ) as resp:
                    latency = time.time() - start

                    if resp.status == 200:
                        proxy.status = ProxyStatus.ALIVE
                        proxy.last_check = time.time()
                        # 更新延迟
                        if proxy.avg_latency == 0:
                            proxy.avg_latency = latency
                        else:
                            proxy.avg_latency = proxy.avg_latency * 0.7 + latency * 0.3
                        return True

        except Exception as e:
            logging.warning(f"Proxy health check failed for {proxy.url}: {e}")

        proxy.status = ProxyStatus.DEAD
        return False

    async def check_all_proxies(self):
        """并发检查所有代理"""
        alive = [p for p in self.proxies.values() if p.status != ProxyStatus.DEAD]

        # 分批检查
        batch_size = self.config.concurrent_check
        for i in range(0, len(alive), batch_size):
            batch = alive[i:i + batch_size]
            await asyncio.gather(*[
                self.check_proxy_health(p) for p in batch
            ])

    async def start_health_checker(self):
        """启动健康检查后台任务"""
        async def _checker():
            while True:
                await asyncio.sleep(self.config.check_interval)
                await self.check_all_proxies()

        self._check_task = asyncio.create_task(_checker())

    def stop_health_checker(self):
        """停止健康检查"""
        if self._check_task:
            self._check_task.cancel()

    def get_stats(self) -> dict:
        """获取代理池统计"""
        total = len(self.proxies)
        alive = sum(1 for p in self.proxies.values() if p.status == ProxyStatus.ALIVE)

        return {
            "total": total,
            "alive": alive,
            "dead": total - alive,
            "avg_score": sum(p.score for p in self.proxies.values()) / max(total, 1)
        }

    async def get_proxy_for_request(self, tags: dict = None) -> Optional[str]:
        """获取代理URL字符串"""
        proxy = self.get_proxy(tags)
        return proxy.url if proxy else None


# ============ 同步版本 ============

class SyncProxyPoolManager:
    """同步版本的代理池管理器"""

    def __init__(self, config: ProxyPoolConfig = None):
        self.config = config or ProxyPoolConfig()
        self.proxies: dict[str, Proxy] = {}

    def add_proxy(self, proxy_url: str, tags: dict = None):
        if proxy_url not in self.proxies:
            self.proxies[proxy_url] = Proxy(
                url=proxy_url,
                tags=tags or {}
            )

    def get_proxy(self, tags: dict = None) -> Optional[str]:
        candidates = [
            p for p in self.proxies.values()
            if p.status != ProxyStatus.DEAD
        ]

        if not candidates:
            return None

        if tags:
            candidates = [
                p for p in candidates
                if all(p.tags.get(k) == v for k, v in tags.items())
            ]

        if not candidates:
            return None

        candidates.sort(key=lambda p: p.score, reverse=True)
        return candidates[0].url

    def report_result(self, proxy_url: str, success: bool, latency: float = None):
        proxy = self.proxies.get(proxy_url)
        if not proxy:
            return

        if success:
            proxy.success_count += 1
            proxy.last_success = time.time()
            if latency:
                proxy.avg_latency = proxy.avg_latency * 0.7 + latency * 0.3 if proxy.avg_latency else latency
        else:
            proxy.fail_count += 1

        total = proxy.success_count + proxy.fail_count
        if total > 0:
            success_rate = proxy.success_count / total
            latency_score = max(0, 100 - proxy.avg_latency * 10) if proxy.avg_latency else 50
            proxy.score = success_rate * 70 + latency_score * 30

        if proxy.score < self.config.min_score:
            proxy.status = ProxyStatus.DEAD
