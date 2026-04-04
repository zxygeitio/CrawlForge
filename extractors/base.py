"""
数据提取器基类模块
定义提取器的抽象基类和通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from utils.logger import Logger, get_logger


T = TypeVar("T")


@dataclass
class ExtractionResult(Generic[T]):
    """数据提取结果"""
    success: bool
    data: T = None
    error: str = None
    raw_data: Any = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ExtractionRule:
    """提取规则"""
    name: str
    selector: str
    attribute: str = None
    default_value: Any = None
    is_required: bool = False
    processor: callable = None


class BaseExtractor(ABC, Generic[T]):
    """
    数据提取器基类

    所有具体提取器应继承此类并实现extract方法
    """

    def __init__(self, logger: Logger = None):
        """
        初始化提取器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("BaseExtractor")

    @abstractmethod
    async def extract(self, raw_data: Any) -> ExtractionResult[T]:
        """
        提取数据

        Args:
            raw_data: 原始数据

        Returns:
            提取结果
        """
        pass

    def validate_result(self, result: ExtractionResult[T]) -> bool:
        """
        验证提取结果

        Args:
            result: 提取结果

        Returns:
            结果是否有效
        """
        if not result.success:
            return False

        if result.data is None:
            return False

        return True

    def create_error_result(self, error: str, raw_data: Any = None) -> ExtractionResult[T]:
        """
        创建错误结果

        Args:
            error: 错误信息
            raw_data: 原始数据

        Returns:
            错误结果对象
        """
        return ExtractionResult(
            success=False,
            error=error,
            raw_data=raw_data
        )

    def create_success_result(
        self,
        data: T,
        raw_data: Any = None,
        metadata: dict = None
    ) -> ExtractionResult[T]:
        """
        创建成功结果

        Args:
            data: 提取的数据
            raw_data: 原始数据
            metadata: 元数据

        Returns:
            成功结果对象
        """
        return ExtractionResult(
            success=True,
            data=data,
            raw_data=raw_data,
            metadata=metadata or {}
        )


class BatchExtractor(BaseExtractor[list[T]]):
    """
    批量提取器基类

    用于从多个数据源中批量提取数据
    """

    def __init__(self, child_extractor: BaseExtractor = None, logger: Logger = None):
        """
        初始化批量提取器

        Args:
            child_extractor: 子提取器
            logger: 日志记录器
        """
        super().__init__(logger)
        self._child_extractor = child_extractor

    async def extract_batch(self, raw_data_list: list[Any]) -> list[ExtractionResult[T]]:
        """
        批量提取数据

        Args:
            raw_data_list: 原始数据列表

        Returns:
            提取结果列表
        """
        import asyncio

        tasks = [
            self._child_extractor.extract(raw_data)
            for raw_data in raw_data_list
        ]

        return await asyncio.gather(*tasks)


class CompositeExtractor(BaseExtractor[dict]):
    """
    组合提取器

    使用多个子提取器组合完成复杂的数据提取任务
    """

    def __init__(self, extractors: dict[str, BaseExtractor] = None, logger: Logger = None):
        """
        初始化组合提取器

        Args:
            extractors: 子提取器字典，键为名称，值为提取器
            logger: 日志记录器
        """
        super().__init__(logger)
        self._extractors = extractors or {}

    def add_extractor(self, name: str, extractor: BaseExtractor) -> None:
        """
        添加子提取器

        Args:
            name: 提取器名称
            extractor: 提取器实例
        """
        self._extractors[name] = extractor

    def remove_extractor(self, name: str) -> None:
        """
        移除子提取器

        Args:
            name: 提取器名称
        """
        self._extractors.pop(name, None)

    async def extract(self, raw_data: Any) -> ExtractionResult[dict]:
        """
        提取数据

        使用所有子提取器提取数据并组合结果

        Args:
            raw_data: 原始数据

        Returns:
            提取结果
        """
        results: dict = {}
        errors: list[str] = []

        for name, extractor in self._extractors.items():
            try:
                result = await extractor.extract(raw_data)
                if result.success:
                    results[name] = result.data
                else:
                    errors.append(f"{name}: {result.error}")
            except Exception as e:
                error_msg = f"{name}提取异常: {e}"
                self._logger.error(error_msg)
                errors.append(error_msg)

        if not results:
            return self.create_error_result(
                f"所有提取器失败: {'; '.join(errors)}",
                raw_data
            )

        return self.create_success_result(
            data=results,
            raw_data=raw_data,
            metadata={"errors": errors, "extractor_count": len(self._extractors)}
        )


if __name__ == "__main__":
    class TestExtractor(BaseExtractor[str]):
        async def extract(self, raw_data: Any) -> ExtractionResult[str]:
            if isinstance(raw_data, str):
                return self.create_success_result(raw_data.upper(), raw_data)
            return self.create_error_result("不是字符串类型", raw_data)

    extractor = TestExtractor()
    result = extractor.extract("hello world")
    print(f"提取结果: {result}")
    print(f"数据: {result.data}")
    print(f"成功: {result.success}")
