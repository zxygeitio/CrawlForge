"""
JSON数据提取器
提供从JSON数据中提取字段的功能
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Union

from .base import (
    BaseExtractor,
    ExtractionResult,
    ExtractionRule,
    CompositeExtractor
)
from ..utils.logger import Logger, get_logger


@dataclass
class JSONPath:
    """JSON路径配置"""
    path: str
    default: Any = None


class JSONExtractor(BaseExtractor[dict]):
    """
    JSON数据提取器

    支持JSONPath语法、字段映射、数据转换等功能
    """

    def __init__(
        self,
        rules: list[ExtractionRule] = None,
        logger: Logger = None
    ):
        """
        初始化JSON提取器

        Args:
            rules: 提取规则列表
            logger: 日志记录器
        """
        super().__init__(logger)
        self._rules = rules or []

    def add_rule(self, rule: ExtractionRule) -> None:
        """
        添加提取规则

        Args:
            rule: 提取规则
        """
        self._rules.append(rule)

    def remove_rule(self, name: str) -> None:
        """
        移除提取规则

        Args:
            name: 规则名称
        """
        self._rules = [r for r in self._rules if r.name != name]

    async def extract(self, raw_data: Any) -> ExtractionResult[dict]:
        """
        提取JSON数据

        Args:
            raw_data: 原始JSON数据（字符串或字典）

        Returns:
            提取结果
        """
        try:
            if isinstance(raw_data, str):
                data = json.loads(raw_data)
            else:
                data = raw_data

            if not isinstance(data, dict):
                return self.create_error_result(
                    f"期望dict类型，实际{type(data).__name__}",
                    raw_data
                )

            result: dict = {}
            errors: list[str] = []

            for rule in self._rules:
                try:
                    value = self._extract_by_path(data, rule.selector)

                    if value is None:
                        if rule.is_required:
                            errors.append(f"必需字段 {rule.name} 未找到")
                        if rule.default_value is not None:
                            value = rule.default_value
                    else:
                        if rule.processor:
                            value = rule.processor(value)

                    result[rule.name] = value

                except Exception as e:
                    error_msg = f"提取 {rule.name} 失败: {e}"
                    self._logger.warning(error_msg)
                    errors.append(error_msg)
                    if rule.is_required:
                        return self.create_error_result(error_msg, raw_data)

            metadata = {
                "errors": errors,
                "field_count": len(self._rules)
            }

            return self.create_success_result(result, raw_data, metadata)

        except json.JSONDecodeError as e:
            return self.create_error_result(f"JSON解析失败: {e}", raw_data)
        except Exception as e:
            return self.create_error_result(f"提取失败: {e}", raw_data)

    def _extract_by_path(self, data: dict, path: str) -> Any:
        """
        根据路径提取数据

        支持的路径格式:
        - 简单键: "name"
        - 嵌套键: "user.name"
        - 数组索引: "items.0"
        - 数组切片: "items.[0:3]"
        - 条件匹配: "items[?@.type=='A']"

        Args:
            data: 数据字典
            path: 路径字符串

        Returns:
            提取的值
        """
        if not path:
            return data

        parts = self._parse_path(path)
        current = data

        for part in parts:
            if current is None:
                return None

            if isinstance(part, str):
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

            elif isinstance(part, int):
                if isinstance(current, (list, tuple)):
                    if 0 <= part < len(current):
                        current = current[part]
                    else:
                        return None
                else:
                    return None

            elif isinstance(part, tuple):
                start, end = part
                if isinstance(current, (list, tuple)):
                    current = current[start:end]
                else:
                    return None

            elif isinstance(part, dict):
                condition = part
                if isinstance(current, list):
                    filtered = []
                    for item in current:
                        if self._check_condition(item, condition):
                            filtered.append(item)
                    current = filtered
                else:
                    current = None

        return current

    def _parse_path(self, path: str) -> list:
        """
        解析路径为部件列表

        Args:
            path: 路径字符串

        Returns:
            路径部件列表
        """
        parts = []
        current = ""
        i = 0

        while i < len(path):
            char = path[i]

            if char == ".":
                if current:
                    parts.append(current)
                    current = ""
                i += 1

            elif char == "[":
                if current:
                    parts.append(current)
                    current = ""

                j = i + 1
                bracket_content = ""
                while j < len(path) and path[j] != "]":
                    bracket_content += path[j]
                    j += 1

                if bracket_content.startswith("?"):
                    condition = self._parse_condition(bracket_content[1:])
                    parts.append(condition)
                elif ":" in bracket_content:
                    start, end = self._parse_slice(bracket_content)
                    parts.append((start, end))
                elif bracket_content.isdigit():
                    parts.append(int(bracket_content))
                else:
                    bracket_content = bracket_content.strip("'\"")
                    parts.append(bracket_content)

                i = j + 1

            else:
                current += char
                i += 1

        if current:
            parts.append(current)

        return parts

    def _parse_condition(self, cond_str: str) -> dict:
        """解析条件表达式"""
        match = re.match(r"@\.(\w+)\s*([=!<>]+)\s*['\"]?(.+?)['\"]?$", cond_str)
        if match:
            return {
                "field": match.group(1),
                "operator": match.group(2),
                "value": match.group(3)
            }
        return {}

    def _parse_slice(self, slice_str: str) -> tuple:
        """解析切片表达式"""
        parts = slice_str.split(":")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else None
        return (start, end)

    def _check_condition(self, item: dict, condition: dict) -> bool:
        """检查元素是否满足条件"""
        if not condition or not isinstance(item, dict):
            return True

        field_name = condition.get("field")
        operator = condition.get("operator")
        expected_value = condition.get("value")

        if field_name not in item:
            return False

        actual_value = str(item[field_name])

        if operator == "==":
            return actual_value == expected_value
        elif operator == "!=":
            return actual_value != expected_value
        elif operator == ">":
            return actual_value > expected_value
        elif operator == "<":
            return actual_value < expected_value

        return False


class JSONPathExtractor(JSONExtractor):
    """
    JSONPath风格提取器

    支持类似JSONPath的语法进行数据提取
    """

    def extract_jsonpath(self, data: Union[str, dict], jsonpath: str) -> list:
        """
        使用JSONPath提取数据

        Args:
            data: JSON数据
            jsonpath: JSONPath表达式

        Returns:
            匹配的值列表
        """
        if isinstance(data, str):
            data = json.loads(data)

        return self._extract_by_path(data, jsonpath)


if __name__ == "__main__":
    sample_json = {
        "code": 0,
        "message": "success",
        "data": {
            "user": {
                "id": 1001,
                "name": "张三",
                "email": "zhangsan@example.com",
                "roles": ["admin", "user"]
            },
            "items": [
                {"id": 1, "name": "商品A", "price": 100, "type": "A"},
                {"id": 2, "name": "商品B", "price": 200, "type": "B"},
                {"id": 3, "name": "商品C", "price": 150, "type": "A"}
            ],
            "total": 450
        }
    }

    rules = [
        ExtractionRule(
            name="user_id",
            selector="data.user.id",
            is_required=True
        ),
        ExtractionRule(
            name="user_name",
            selector="data.user.name",
            default_value="匿名用户"
        ),
        ExtractionRule(
            name="item_names",
            selector="data.items.[?@.type=='A'].name"
        ),
        ExtractionRule(
            name="first_item_price",
            selector="data.items.0.price",
            processor=lambda x: float(x)
        )
    ]

    extractor = JSONExtractor(rules)
    result = extractor.extract(sample_json)

    print("=== JSON提取器测试 ===")
    print(f"成功: {result.success}")
    print(f"数据: {result.data}")
    print(f"错误: {result.error}")
    print(f"元数据: {result.metadata}")

    jsonpath_extractor = JSONPathExtractor()

    print("\n=== JSONPath测试 ===")
    names = jsonpath_extractor.extract_jsonpath(sample_json, "data.items.[?@.type=='A'].name")
    print(f"类型为A的商品名称: {names}")

    prices = jsonpath_extractor.extract_jsonpath(sample_json, "data.items.[:2].price")
    print(f"前两个商品价格: {prices}")
