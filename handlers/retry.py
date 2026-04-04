"""
重试机制模块
提供灵活的重试策略和实现
"""

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Type, Union

from utils.logger import Logger, get_logger


class RetryStrategy(Enum):
    """重试策略枚举"""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    RANDOM = "random"


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_on_exceptions: tuple = (Exception,)
    backoff_multiplier: float = 1.5
    jitter: bool = True
    jitter_range: tuple = (0.8, 1.2)


@dataclass
class RetryResult:
    """重试结果"""
    success: bool
    result: Any = None
    error: Exception = None
    attempts: int = 0
    total_time: float = 0.0
    delays: list = field(default_factory=list)


class RetryHandler:
    """
    重试处理器

    提供多种重试策略，支持异步和同步函数
    """

    def __init__(
        self,
        config: RetryConfig = None,
        logger: Logger = None
    ):
        """
        初始化重试处理器

        Args:
            config: 重试配置
            logger: 日志记录器
        """
        self._config = config or RetryConfig()
        self._logger = logger or get_logger("RetryHandler")

    def calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟

        Args:
            attempt: 当前尝试次数（从1开始）

        Returns:
            延迟时间（秒）
        """
        strategy = self._config.strategy
        base_delay = self._config.initial_delay

        if strategy == RetryStrategy.FIXED:
            delay = base_delay

        elif strategy == RetryStrategy.LINEAR:
            delay = base_delay * attempt

        elif strategy == RetryStrategy.EXPONENTIAL:
            delay = base_delay * (self._config.multiplier ** (attempt - 1))

        elif strategy == RetryStrategy.FIBONACCI:
            fib = self._fibonacci(attempt)
            delay = base_delay * fib

        elif strategy == RetryStrategy.RANDOM:
            delay = random.uniform(base_delay, base_delay * self._config.multiplier)

        else:
            delay = base_delay

        delay = min(delay, self._config.max_delay)

        if self._config.jitter:
            jitter_min, jitter_max = self._config.jitter_range
            jitter = random.uniform(jitter_min, jitter_max)
            delay *= jitter

        return delay

    def _fibonacci(self, n: int) -> int:
        """计算斐波那契数"""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> RetryResult:
        """
        异步执行带重试

        Args:
            func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            重试结果
        """
        start_time = time.time()
        delays: list = []
        last_error: Exception = None

        for attempt in range(1, self._config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)

                total_time = time.time() - start_time
                self._logger.info(
                    f"执行成功 (尝试 {attempt}/{self._config.max_attempts})"
                )

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    total_time=total_time,
                    delays=delays
                )

            except self._config.retry_on_exceptions as e:
                last_error = e
                self._logger.warning(
                    f"执行失败 (尝试 {attempt}/{self._config.max_attempts}): {e}"
                )

                if attempt < self._config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    delays.append(delay)
                    self._logger.debug(f"等待 {delay:.2f}秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    self._logger.error(f"达到最大重试次数 {self._config.max_attempts}")

        total_time = time.time() - start_time
        return RetryResult(
            success=False,
            error=last_error,
            attempts=self._config.max_attempts,
            total_time=total_time,
            delays=delays
        )

    def execute_sync(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> RetryResult:
        """
        同步执行带重试

        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            重试结果
        """
        start_time = time.time()
        delays: list = []
        last_error: Exception = None

        for attempt in range(1, self._config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)

                total_time = time.time() - start_time
                self._logger.info(
                    f"执行成功 (尝试 {attempt}/{self._config.max_attempts})"
                )

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    total_time=total_time,
                    delays=delays
                )

            except self._config.retry_on_exceptions as e:
                last_error = e
                self._logger.warning(
                    f"执行失败 (尝试 {attempt}/{self._config.max_attempts}): {e}"
                )

                if attempt < self._config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    delays.append(delay)
                    self._logger.debug(f"等待 {delay:.2f}秒后重试...")
                    time.sleep(delay)
                else:
                    self._logger.error(f"达到最大重试次数 {self._config.max_attempts}")

        total_time = time.time() - start_time
        return RetryResult(
            success=False,
            error=last_error,
            attempts=self._config.max_attempts,
            total_time=total_time,
            delays=delays
        )


def with_retry(config: RetryConfig = None):
    """
    重试装饰器

    Args:
        config: 重试配置

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = RetryHandler(config)
            result = await handler.execute_async(func, *args, **kwargs)
            if not result.success:
                raise result.error
            return result.result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            handler = RetryHandler(config)
            result = handler.execute_sync(func, *args, **kwargs)
            if not result.success:
                raise result.error
            return result.result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class CircuitBreaker:
    """
    断路器

    当失败次数超过阈值时，快速失败不再重试
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        logger: Logger = None
    ):
        """
        初始化断路器

        Args:
            failure_threshold: 失败次数阈值
            recovery_timeout: 恢复超时（秒）
            expected_exception: 期望的异常类型
            logger: 日志记录器
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._expected_exception = expected_exception
        self._logger = logger or get_logger("CircuitBreaker")

        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "closed"

    @property
    def state(self) -> str:
        """获取断路器状态"""
        if self._state == "open":
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = "half-open"
                self._logger.info("断路器进入半开状态")
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过断路器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            Exception: 断路器打开时抛出异常
        """
        if self.state == "open":
            raise Exception("断路器处于打开状态，拒绝调用")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self._expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """处理成功调用"""
        if self._state == "half-open":
            self._logger.info("断路器关闭")
        self._failure_count = 0
        self._state = "closed"

    def _on_failure(self) -> None:
        """处理失败调用"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            self._logger.warning(
                f"断路器打开 (失败次数: {self._failure_count})"
            )
            self._state = "open"


if __name__ == "__main__":
    print("=== 重试机制测试 ===")

    config = RetryConfig(
        max_attempts=3,
        initial_delay=0.5,
        strategy=RetryStrategy.EXPONENTIAL,
        multiplier=2.0,
        jitter=False
    )

    handler = RetryHandler(config)

    print(f"重试配置: 最大尝试={config.max_attempts}, "
          f"初始延迟={config.initial_delay}s, "
          f"策略={config.strategy.value}")

    print("\n延迟计算:")
    for attempt in range(1, 5):
        delay = handler.calculate_delay(attempt)
        print(f"  尝试 {attempt}: {delay:.2f}s")

    print("\n=== 断路器测试 ===")

    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

    print(f"初始状态: {breaker.state}")

    for i in range(5):
        try:
            if random.random() < 0.7:
                raise ValueError(f"随机错误 {i}")
            print(f"调用 {i} 成功")
        except Exception as e:
            print(f"调用 {i} 失败: {e}")

    print(f"最终状态: {breaker.state}")

    async def test_async_retry():
        print("\n=== 异步重试测试 ===")

        attempt_count = 0

        async def unreliable_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError(f"第 {attempt_count} 次尝试失败")
            return f"成功! (共尝试 {attempt_count} 次)"

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.2,
            strategy=RetryStrategy.LINEAR
        )
        handler = RetryHandler(config)

        result = await handler.execute_async(unreliable_func)

        print(f"异步重试结果: success={result.success}, "
              f"attempts={result.attempts}, "
              f"total_time={result.total_time:.2f}s")

    asyncio.run(test_async_retry())
