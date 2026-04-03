"""
速率限制器
- Token Bucket算法
- 滑动窗口
- 自适应限流
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TokenBucketConfig:
    """令牌桶配置"""
    rate: float = 10.0  # 每秒生成令牌数
    capacity: int = 100  # 桶容量
    initial_tokens: int = None  # 初始令牌数

    @property
    def burst_size(self) -> int:
        """突发容量"""
        return self.capacity


class TokenBucket:
    """
    令牌桶算法实现

    特点:
    - 允许一定程度的突发流量
    - 平滑限流
    - 支持多消费者
    """

    def __init__(self, config: TokenBucketConfig = None):
        self.config = config or TokenBucketConfig()
        self._tokens = self.config.initial_tokens or self.config.capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1, timeout: float = None) -> bool:
        """
        获取令牌

        Args:
            tokens: 需要令牌数
            timeout: 超时时间(秒), None表示无限等待

        Returns:
            是否成功获取
        """
        deadline = time.monotonic() + timeout if timeout else None

        while True:
            async with self._lock:
                self._refill()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

            # 检查超时
            if deadline and time.monotonic() >= deadline:
                return False

            # 等待重试
            wait_time = (tokens - self._tokens) / self.config.rate
            if timeout:
                wait_time = min(wait_time, deadline - time.monotonic())

            if wait_time > 0:
                await asyncio.sleep(max(0.01, wait_time))

    def _refill(self):
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        # 添加新令牌
        new_tokens = elapsed * self.config.rate
        self._tokens = min(self._tokens + new_tokens, self.config.capacity)

    def available_tokens(self) -> int:
        """当前可用令牌数"""
        self._refill()
        return int(self._tokens)


class SlidingWindowRateLimiter:
    """
    滑动窗口限流器

    更精确的限流算法，记录每个请求的时间戳
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self, timeout: float = None) -> bool:
        """
        获取限流许可

        Args:
            timeout: 最大等待时间

        Returns:
            是否获得许可
        """
        deadline = time.monotonic() + timeout if timeout else None

        while True:
            async with self._lock:
                self._cleanup()

                if len(self._requests) < self.max_requests:
                    self._requests.append(time.monotonic())
                    return True

            if deadline and time.monotonic() >= deadline:
                return False

            # 等待最旧请求过期
            async with self._lock:
                self._cleanup()
                if self._requests:
                    wait_time = self._requests[0] + self.window_seconds - time.monotonic()
                    if wait_time > 0:
                        await asyncio.sleep(min(wait_time, 0.1))

    def _cleanup(self):
        """清理过期请求记录"""
        cutoff = time.monotonic() - self.window_seconds
        self._requests = [t for t in self._requests if t > cutoff]

    def get_current_usage(self) -> int:
        """当前窗口内的请求数"""
        self._cleanup()
        return len(self._requests)


class AdaptiveRateLimiter:
    """
    自适应限流器

    根据响应状态自动调整限流参数
    """

    def __init__(
        self,
        initial_rate: float = 10.0,
        min_rate: float = 0.5,
        max_rate: float = 100.0,
        increase_factor: float = 1.2,
        decrease_factor: float = 0.5
    ):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_factor = increase_factor
        self.decrease_factor = decrease_factor
        self._bucket = TokenBucket(TokenBucketConfig(rate=initial_rate, capacity=int(initial_rate * 2)))

    async def acquire(self, success: bool = True) -> bool:
        """
        获取限流许可

        Args:
            success: 请求是否成功
        """
        # 根据结果调整速率
        if success:
            self._increase_rate()
        else:
            self._decrease_rate()

        return await self._bucket.acquire()

    def _increase_rate(self):
        """增加速率"""
        new_rate = min(self.current_rate * self.increase_factor, self.max_rate)
        if new_rate != self.current_rate:
            self.current_rate = new_rate
            self._bucket.config.rate = new_rate

    def _decrease_rate(self):
        """降低速率"""
        new_rate = max(self.current_rate * self.decrease_factor, self.min_rate)
        if new_rate != self.current_rate:
            self.current_rate = new_rate
            self._bucket.config.rate = new_rate


class MultiLimiter:
    """
    多维度限流器

    同时限制:
    - 全局限流
    - 域名限流
    - IP限流
    """

    def __init__(self):
        self._global = TokenBucket(TokenBucketConfig(rate=50, capacity=100))
        self._domains: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str = None, tokens: int = 1) -> bool:
        """
        获取限流许可

        Args:
            domain: 域名
            tokens: 令牌数
        """
        # 先检查全局
        if not await self._global.acquire(tokens):
            return False

        # 再检查域名
        if domain:
            async with self._lock:
                if domain not in self._domains:
                    self._domains[domain] = TokenBucket(
                        TokenBucketConfig(rate=10, capacity=20)
                    )

            if not await self._domains[domain].acquire(tokens):
                return False

        return True

    def set_domain_rate(self, domain: str, rate: float, capacity: int = None):
        """设置域名限流参数"""
        capacity = capacity or int(rate * 2)
        self._domains[domain] = TokenBucket(
            TokenBucketConfig(rate=rate, capacity=capacity)
        )
