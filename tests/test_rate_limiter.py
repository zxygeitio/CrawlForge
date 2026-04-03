"""
限流器测试
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from src.rate_limiter import (
    TokenBucket,
    TokenBucketConfig,
    SlidingWindowRateLimiter,
    AdaptiveRateLimiter,
    MultiLimiter,
)


class TestTokenBucket:
    """令牌桶测试"""

    @pytest.fixture
    def bucket(self):
        """创建令牌桶"""
        config = TokenBucketConfig(rate=10.0, capacity=10)
        return TokenBucket(config=config)

    @pytest.mark.asyncio
    async def test_acquire_with_available_tokens(self, bucket):
        """测试获取可用令牌"""
        result = await bucket.acquire(tokens=1, timeout=0.1)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_depletes_tokens(self, bucket):
        """测试获取令牌消耗"""
        await bucket.acquire(tokens=5)
        available = bucket.available_tokens()
        assert available <= 5  # 可能有补充

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self, bucket):
        """测试获取多个令牌"""
        result = await bucket.acquire(tokens=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_timeout_when_empty(self, bucket):
        """测试桶空时超时"""
        bucket._tokens = 0
        # Use extremely small timeout - less than minimum sleep time
        # The deadline will expire during the sleep, causing return on next iteration
        result = await bucket.acquire(tokens=1, timeout=0.00001)
        assert result is False

    @pytest.mark.asyncio
    async def test_refill_adds_tokens(self, bucket):
        """测试补充令牌"""
        bucket._tokens = 0
        await asyncio.sleep(0.2)  # 等待补充
        bucket._refill()
        assert bucket._tokens > 0

    @pytest.mark.asyncio
    async def test_bucket_capacity_limit(self, bucket):
        """测试桶容量限制"""
        bucket._tokens = bucket.config.capacity
        bucket._refill()
        assert bucket._tokens == bucket.config.capacity

    def test_available_tokens(self, bucket):
        """测试获取可用令牌数"""
        bucket._tokens = 5
        assert bucket.available_tokens() == 5


class TestSlidingWindowRateLimiter:
    """滑动窗口限流器测试"""

    @pytest.fixture
    def limiter(self):
        """创建滑动窗口限流器"""
        return SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self, limiter):
        """测试限制内获取"""
        for _ in range(5):
            result = await limiter.acquire(timeout=0.1)
            assert result is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self, limiter):
        """测试超过限制"""
        # 先占满
        for _ in range(5):
            await limiter.acquire()

        # 下一次应该失败或等待
        result = await limiter.acquire(timeout=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_window_cleanup(self, limiter):
        """测试窗口清理"""
        # 添加旧请求
        limiter._requests.append(time.monotonic() - 2)  # 2秒前
        limiter._requests.append(time.monotonic() - 0.5)  # 0.5秒前

        await limiter.acquire()
        usage = limiter.get_current_usage()

        # 旧请求应该被清理
        assert usage <= 2

    def test_get_current_usage(self, limiter):
        """测试获取当前使用量"""
        limiter._requests = [time.monotonic(), time.monotonic()]
        assert limiter.get_current_usage() == 2


class TestAdaptiveRateLimiter:
    """自适应限流器测试"""

    @pytest.fixture
    def limiter(self):
        """创建自适应限流器"""
        return AdaptiveRateLimiter(
            initial_rate=10.0,
            min_rate=0.5,
            max_rate=100.0,
            increase_factor=1.2,
            decrease_factor=0.5,
        )

    @pytest.mark.asyncio
    async def test_increase_rate_on_success(self, limiter):
        """测试成功时增加速率"""
        initial_rate = limiter.current_rate
        await limiter.acquire(success=True)
        # 速率应该增加
        assert limiter.current_rate >= initial_rate

    @pytest.mark.asyncio
    async def test_decrease_rate_on_failure(self, limiter):
        """测试失败时降低速率"""
        limiter.current_rate = 10.0
        await limiter.acquire(success=False)
        # 速率应该降低
        assert limiter.current_rate < 10.0

    @pytest.mark.asyncio
    async def test_rate_minimum_limit(self, limiter):
        """测试速率下限"""
        limiter.current_rate = limiter.min_rate
        await limiter.acquire(success=False)
        assert limiter.current_rate >= limiter.min_rate

    @pytest.mark.asyncio
    async def test_rate_maximum_limit(self, limiter):
        """测试速率上限"""
        limiter.current_rate = limiter.max_rate
        await limiter.acquire(success=True)
        assert limiter.current_rate <= limiter.max_rate


class TestMultiLimiter:
    """多维度限流器测试"""

    @pytest.fixture
    def limiter(self):
        """创建多维度限流器"""
        return MultiLimiter()

    @pytest.mark.asyncio
    async def test_global_limit(self, limiter):
        """测试全局限流"""
        # 先消耗全局令牌
        await limiter.acquire(tokens=100)

        # 验证全局令牌已减少
        assert limiter._global._tokens < 100

        # 测试当全局桶为空时，请求被拒绝
        # 由于 MultiLimiter 没有 timeout，我们直接 mock 来验证逻辑
        original_bucket = limiter._global

        # 创建mock桶并替换
        mock_bucket = AsyncMock()
        mock_bucket.acquire = AsyncMock(return_value=False)  # 模拟获取失败
        limiter._global = mock_bucket

        result = await limiter.acquire()
        assert result is False

        # 恢复
        limiter._global = original_bucket

    @pytest.mark.asyncio
    async def test_domain_limit(self, limiter):
        """测试域名限流"""
        # 先消耗域名令牌以创建域名的桶
        for _ in range(20):
            await limiter.acquire(domain="example.com")

        # 获取域名桶的引用
        domain_bucket = limiter._domains["example.com"]

        # Mock域名桶的acquire返回False
        original_acquire = domain_bucket.acquire
        domain_bucket.acquire = AsyncMock(return_value=False)

        result = await limiter.acquire(domain="example.com")
        assert result is False

        # 恢复
        domain_bucket.acquire = original_acquire

    @pytest.mark.asyncio
    async def test_different_domains_independent(self, limiter):
        """测试不同域名独立限流"""
        # 消耗 example.com 的令牌
        for _ in range(20):
            await limiter.acquire(domain="example.com")

        # Mock example.com的桶
        example_bucket = limiter._domains["example.com"]
        example_bucket.acquire = AsyncMock(return_value=False)

        # example.com 应该被限流
        result1 = await limiter.acquire(domain="example.com")
        assert result1 is False

        # other.com 不受影响
        result2 = await limiter.acquire(domain="other.com")
        assert result2 is True

        # 恢复
        example_bucket.acquire = AsyncMock(return_value=True)

    @pytest.mark.asyncio
    async def test_set_domain_rate(self, limiter):
        """测试设置域名限流参数"""
        limiter.set_domain_rate("example.com", rate=5.0, capacity=10)

        # 验证域名桶已创建且参数正确
        domain_bucket = limiter._domains["example.com"]
        assert domain_bucket.config.rate == 5.0
        assert domain_bucket.config.capacity == 10

        # 保存原始acquire方法
        original_acquire = domain_bucket.acquire

        # 消耗令牌
        for _ in range(10):
            await limiter.acquire(domain="example.com")

        # Mock为耗尽状态
        domain_bucket.acquire = AsyncMock(return_value=False)
        result = await limiter.acquire(domain="example.com")
        assert result is False

        # 恢复
        domain_bucket.acquire = original_acquire
