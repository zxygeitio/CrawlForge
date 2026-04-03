"""
数据处理模块
支持数据清洗、转换、验证和导出
"""

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import StringIO, BytesIO
from typing import Any, Callable, Iterator, Optional, Union

# HTML解析器
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# XPath支持
try:
    from lxml import etree
    from lxml.html import HtmlElement, document_fromstring, fragment_fromstring
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False

# pandas (可选)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def _validate_sql_identifier(name: str) -> str:
    """
    验证SQL标识符(表名/字段名)的安全性
    只允许字母、数字和下划线
    """
    if not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid SQL identifier: '{name}'. Only alphanumeric characters and underscores are allowed.")
    return name


class DataType(Enum):
    """数据类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    JSON = "json"
    HTML = "html"


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


@dataclass
class FieldSchema:
    """字段Schema定义"""
    name: str
    data_type: DataType
    required: bool = False
    default: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    choices: Optional[list] = None
    custom_validator: Optional[Callable[[Any], bool]] = None

    def validate(self, value: Any) -> Optional[str]:
        """验证单个字段值,返回错误信息或None"""
        # 空值检查
        if value is None:
            if self.required:
                return f"Field '{self.name}' is required"
            return None

        # 类型检查
        if self.data_type == DataType.STRING:
            if not isinstance(value, str):
                try:
                    value = str(value)
                except Exception:
                    return f"Field '{self.name}' must be a string"
        elif self.data_type == DataType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return f"Field '{self.name}' must be an integer"
        elif self.data_type == DataType.FLOAT:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return f"Field '{self.name}' must be a number"
        elif self.data_type == DataType.BOOLEAN:
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes", "on")
            elif not isinstance(value, bool):
                try:
                    value = bool(value)
                except Exception:
                    return f"Field '{self.name}' must be a boolean"
        elif self.data_type == DataType.DATE:
            if not isinstance(value, str):
                return f"Field '{self.name}' must be a date string"
            # 尝试解析日期
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
                try:
                    datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                return f"Field '{self.name}' must be a valid date string"

        # 范围检查
        if self.min_value is not None and value < self.min_value:
            return f"Field '{self.name}' must be >= {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return f"Field '{self.name}' must be <= {self.max_value}"

        # 选项检查
        if self.choices is not None and value not in self.choices:
            return f"Field '{self.name}' must be one of {self.choices}"

        # 正则检查
        if self.pattern is not None and isinstance(value, str):
            if not re.match(self.pattern, value):
                return f"Field '{self.name}' does not match pattern {self.pattern}"

        # 自定义验证
        if self.custom_validator is not None:
            try:
                if not self.custom_validator(value):
                    return f"Field '{self.name}' failed custom validation"
            except Exception as e:
                return f"Field '{self.name}' validation error: {e}"

        return None


class DataSchema:
    """数据Schema验证器"""

    def __init__(self, fields: list[FieldSchema]):
        self.fields = fields

    def validate(self, data: dict) -> ValidationResult:
        """验证数据字典"""
        errors = []
        for field_schema in self.fields:
            value = data.get(field_schema.name)
            error = field_schema.validate(value)
            if error:
                errors.append(error)

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


class DataCleaner:
    """数据清洗器"""

    @staticmethod
    def deduplicate(items: list, key: Optional[Callable] = None) -> list:
        """
        去重

        Args:
            items: 待去重列表
            key: 可选的key函数,用于确定唯一性

        Returns:
            去重后的列表
        """
        if key is None:
            seen = set()
            result = []
            for item in items:
                # 对于字典,转换为可哈希的表示
                if isinstance(item, dict):
                    item_key = tuple(sorted(item.items()))
                else:
                    item_key = item

                if item_key not in seen:
                    seen.add(item_key)
                    result.append(item)
            return result
        else:
            seen = set()
            result = []
            for item in items:
                item_key = key(item)
                if item_key not in seen:
                    seen.add(item_key)
                    result.append(item)
            return result

    @staticmethod
    def remove_duplicates_by_fields(items: list, fields: list[str]) -> list:
        """根据指定字段去重"""
        seen = set()
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = tuple(item.get(f) for f in fields)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def handle_nulls(
        items: list,
        strategy: str = "remove",
        fill_value: Any = None,
        null_values: Optional[set] = None
    ) -> list:
        """
        处理空值

        Args:
            items: 数据列表
            strategy: 处理策略 - 'remove', 'fill', 'keep'
            fill_value: 填充值(strategy='fill'时使用)
            null_values: 视为空值的集合

        Returns:
            处理后的列表
        """
        if null_values is None:
            null_values = {"", "null", "NULL", "None", "none", "N/A", "n/a", "-", "--", ""}

        result = []
        for item in items:
            if isinstance(item, dict):
                cleaned_item = {}
                has_null = False
                for k, v in item.items():
                    v_str = str(v).strip() if v is not None else None
                    is_null = v is None or (v_str in null_values)

                    if is_null:
                        has_null = True
                        if strategy == "fill":
                            cleaned_item[k] = fill_value
                        elif strategy == "keep":
                            cleaned_item[k] = v
                    else:
                        cleaned_item[k] = v

                if strategy == "remove" and not has_null:
                    result.append(cleaned_item)
                elif strategy != "remove":
                    result.append(cleaned_item)
            else:
                if strategy == "remove":
                    if item is not None and str(item).strip() not in null_values:
                        result.append(item)
                elif strategy == "fill":
                    result.append(item if item is not None else fill_value)
                else:
                    result.append(item)

        return result

    @staticmethod
    def standardize_format(
        items: list,
        strip_whitespace: bool = True,
        lower_fields: Optional[list] = None,
        upper_fields: Optional[list] = None,
        normalize_unicode: bool = True
    ) -> list:
        """
        格式标准化

        Args:
            items: 数据列表
            strip_whitespace: 是否去除空白
            lower_fields: 转小写的字段列表
            upper_fields: 转大写的字段列表
            normalize_unicode: 是否标准化Unicode

        Returns:
            处理后的列表
        """
        lower_fields = lower_fields or []
        upper_fields = upper_fields or []

        result = []
        for item in items:
            if isinstance(item, dict):
                cleaned = {}
                for k, v in item.items():
                    if isinstance(v, str):
                        if strip_whitespace:
                            v = v.strip()
                        if normalize_unicode:
                            # WARNING: NFKC normalization may alter character semantics
                            # (e.g., ligatures, subscripts, special characters)
                            v = unicodedata.normalize("NFKC", v)
                        if k in lower_fields:
                            v = v.lower()
                        elif k in upper_fields:
                            v = v.upper()
                    cleaned[k] = v
                result.append(cleaned)
            elif isinstance(item, str):
                v = item
                if strip_whitespace:
                    v = v.strip()
                if normalize_unicode:
                    v = unicodedata.normalize("NFKC", v)
                result.append(v)
            else:
                result.append(item)

        return result


class DataTransformer:
    """数据转换器"""

    @staticmethod
    def parse_html(html: str, parser: str = "html.parser") -> Optional[Any]:
        """
        解析HTML

        Args:
            html: HTML字符串
            parser: 解析器 - 'html.parser', 'lxml', 'html5lib'

        Returns:
            BeautifulSoup对象
        """
        if not BS4_AVAILABLE:
            raise ImportError("BeautifulSoup4 is not installed. Install with: pip install beautifulsoup4")

        return BeautifulSoup(html, parser)

    @staticmethod
    def extract_by_css(html: str, selector: str, parser: str = "html.parser") -> list:
        """CSS选择器提取"""
        soup = DataTransformer.parse_html(html, parser)
        if soup is None:
            return []
        return [elem.get_text(strip=True) for elem in soup.select(selector)]

    @staticmethod
    def extract_by_jsonpath(data: Any, path: str) -> list:
        """
        JSONPath提取

        Args:
            data: JSON数据(dict或list)
            path: JSONPath路径,如 '$.store.book[*].author'

        Returns:
            匹配结果列表
        """
        try:
            import jsonpath_ng
            from jsonpath_ng.ext import parse
        except ImportError:
            # 手动实现简单的JSONPath
            return DataTransformer._simple_jsonpath(data, path)

        jsonpath_expr = parse(path)
        return [match.value for match in jsonpath_expr.find(data)]

    @staticmethod
    def _simple_jsonpath(data: Any, path: str) -> list:
        """简单的JSONPath实现"""
        result = []
        # 移除 $ 符号
        path = path.strip("$")

        if not path.startswith("."):
            path = "." + path

        parts = path.replace("[", ".[").split(".")
        current = data

        for part in parts:
            if part == "":
                continue

            if part.startswith("["):
                # 数组索引
                idx_str = part[1:-1]
                if idx_str.isdigit():
                    idx = int(idx_str)
                    if isinstance(current, (list, tuple)) and idx < len(current):
                        current = current[idx]
                    else:
                        return []
                elif idx_str == "*":
                    if isinstance(current, (list, tuple)):
                        next_parts = parts[parts.index(part) + 1:]
                        for item in current:
                            sub_result = DataTransformer._apply_path(item, next_parts)
                            result.extend(sub_result if isinstance(sub_result, list) else [sub_result])
                        return result
                    else:
                        return []
                else:
                    return []
            elif isinstance(current, dict):
                current = current.get(part, {})
                if current is None:
                    return []
            else:
                return []

        return [current] if current is not None else []

    @staticmethod
    def _apply_path(data: Any, path_parts: list) -> Any:
        """应用路径部分"""
        current = data
        for part in path_parts:
            if part == "":
                continue
            if part.startswith("["):
                continue
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    @staticmethod
    def xpath_extract(html: str, xpath_expr: str) -> list:
        """
        XPath提取

        Args:
            html: HTML字符串
            xpath_expr: XPath表达式

        Returns:
            提取结果列表
        """
        if not LXML_AVAILABLE:
            raise ImportError("lxml is not installed. Install with: pip install lxml")

        root = document_fromstring(html)
        return [
            elem.text_content() if hasattr(elem, 'text_content') else str(elem)
            for elem in root.xpath(xpath_expr)
        ]

    @staticmethod
    def convert_encoding(text: str, to_encoding: str = "utf-8", from_encoding: Optional[str] = None) -> str:
        """
        编码转换

        Args:
            text: 输入文本
            to_encoding: 目标编码
            from_encoding: 源编码(如果为None,会自动检测)

        Returns:
            转换后的字符串
        """
        if from_encoding is None:
            # 自动检测编码
            for enc in ("utf-8", "gbk", "gb2312", "gb18030", "big5", "shift_jis"):
                try:
                    text.encode(to_encoding)
                    from_encoding = enc
                    break
                except UnicodeEncodeError:
                    continue

        if from_encoding is None:
            from_encoding = "utf-8"

        try:
            return text.encode(to_encoding, errors="ignore").decode(to_encoding)
        except Exception:
            return text


class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_schema(data: dict, schema: DataSchema) -> ValidationResult:
        """使用Schema验证数据"""
        return schema.validate(data)

    @staticmethod
    def validate_type(value: Any, expected_type: type) -> bool:
        """类型检查"""
        if expected_type == int:
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == float:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected_type == bool:
            return isinstance(value, bool)
        elif expected_type == str:
            return isinstance(value, str)
        elif expected_type == list:
            return isinstance(value, list)
        elif expected_type == dict:
            return isinstance(value, dict)
        return isinstance(value, expected_type)

    @staticmethod
    def validate_range(value: Union[int, float], min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
        """范围校验"""
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    @staticmethod
    def validate_pattern(value: str, pattern: str) -> bool:
        """正则验证"""
        return bool(re.match(pattern, value))


class DataExporter:
    """数据导出器"""

    def __init__(self, use_pandas: bool = PANDAS_AVAILABLE):
        """
        初始化导出器

        Args:
            use_pandas: 是否使用pandas(如果可用)
        """
        self.use_pandas = use_pandas and PANDAS_AVAILABLE

    def export_to_csv(
        self,
        data: list,
        file_path: Optional[str] = None,
        fieldnames: Optional[list] = None,
        encoding: str = "utf-8",
        mode: str = "w"
    ) -> Optional[str]:
        """
        导出为CSV

        Args:
            data: 数据列表
            file_path: 文件路径(如果为None,返回CSV字符串)
            fieldnames: 字段名列表
            encoding: 编码
            mode: 写入模式('w'或'a')

        Returns:
            CSV字符串(如果file_path为None)或None
        """
        if not data:
            return "" if file_path is None else None

        # 确定fieldnames
        if fieldnames is None:
            if isinstance(data[0], dict):
                fieldnames = list(data[0].keys())

        output = StringIO()

        # 构建CSV
        writer = csv.DictWriter(output, fieldnames=fieldnames or [], extrasaction='ignore')

        if mode == "w" or file_path is None:
            if fieldnames:
                writer.writeheader()

        for item in data:
            if isinstance(item, dict):
                writer.writerow(item)
            else:
                writer.writerow({fieldnames[0] if fieldnames else "value": item})

        csv_content = output.getvalue()
        output.close()

        if file_path:
            with open(file_path, mode, encoding=encoding, newline="") as f:
                f.write(csv_content)
            return None
        else:
            return csv_content

    def export_to_json(
        self,
        data: Any,
        file_path: Optional[str] = None,
        encoding: str = "utf-8",
        indent: int = 2,
        ensure_ascii: bool = False
    ) -> Optional[str]:
        """
        导出为JSON

        Args:
            data: 数据
            file_path: 文件路径(如果为None,返回JSON字符串)
            encoding: 编码
            indent: 缩进
            ensure_ascii: 是否保留ASCII

        Returns:
            JSON字符串(如果file_path为None)或None
        """
        json_str = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)

        if file_path:
            with open(file_path, "w", encoding=encoding) as f:
                f.write(json_str)
            return None
        else:
            return json_str

    def export_to_excel(
        self,
        data: list,
        file_path: str,
        sheet_name: str = "Sheet1",
        index: bool = False
    ) -> None:
        """
        导出为Excel

        Args:
            data: 数据列表
            file_path: 文件路径
            sheet_name: 工作表名称
            index: 是否包含索引
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is not installed. Install with: pip install pandas")

        if not data:
            return

        df = pd.DataFrame(data)
        df.to_excel(file_path, sheet_name=sheet_name, index=index, engine="openpyxl")

    def export_to_database(
        self,
        data: list,
        connection,
        table_name: str,
        batch_size: int = 1000,
        if_exists: str = "append"
    ) -> int:
        """
        批量写入数据库

        Args:
            data: 数据列表
            connection: 数据库连接对象
            table_name: 表名
            batch_size: 批量大小
            if_exists: 表存在时的策略 - 'append', 'replace', 'fail'

        Returns:
            插入的记录数
        """
        if not data:
            return 0

        # 获取字段名并验证
        if isinstance(data[0], dict):
            fields = list(data[0].keys())
            # 验证表名和字段名安全
            _validate_sql_identifier(table_name)
            fields = [_validate_sql_identifier(f) for f in fields]
            placeholders = ", ".join(["?" for _ in fields])
            sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({placeholders})"
        else:
            return 0

        cursor = connection.cursor()

        # 处理if_exists
        if if_exists == "replace":
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            # 创建表
            create_sql = f"CREATE TABLE {table_name} ({', '.join([f'{f} TEXT' for f in fields])})"
            cursor.execute(create_sql)
        elif if_exists == "fail":
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone():
                raise ValueError(f"Table '{table_name}' already exists")

        total_inserted = 0
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            for item in batch:
                values = [item.get(f) for f in fields]
                cursor.execute(sql, values)
            connection.commit()
            total_inserted += len(batch)

        cursor.close()
        return total_inserted


class StreamProcessor:
    """流式处理器,用于处理大文件"""

    def __init__(self, chunk_size: int = 1000):
        """
        初始化流处理器

        Args:
            chunk_size: 每次处理的块大小
        """
        self.chunk_size = chunk_size

    def process_file(
        self,
        file_path: str,
        processor: Callable[[list], list],
        input_format: str = "jsonl"
    ) -> Iterator[list]:
        """
        流式处理文件

        Args:
            file_path: 文件路径
            processor: 处理函数,接收列表,返回列表
            input_format: 输入格式 - 'jsonl', 'csv'

        Yields:
            处理后的数据块
        """
        with open(file_path, "r", encoding="utf-8") as f:
            if input_format == "jsonl":
                buffer = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        buffer.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

                    if len(buffer) >= self.chunk_size:
                        yield processor(buffer)
                        buffer = []

                if buffer:
                    yield processor(buffer)

            elif input_format == "csv":
                reader = csv.DictReader(f)
                buffer = []
                for row in reader:
                    buffer.append(row)

                    if len(buffer) >= self.chunk_size:
                        yield processor(buffer)
                        buffer = []

                if buffer:
                    yield processor(buffer)

    def write_file(
        self,
        file_path: str,
        data_iterator: Iterator[list],
        output_format: str = "jsonl"
    ) -> int:
        """
        流式写入文件

        Args:
            file_path: 文件路径
            data_iterator: 数据迭代器
            output_format: 输出格式 - 'jsonl', 'csv'

        Returns:
            写入的记录总数
        """
        total_count = 0
        first_item = True

        with open(file_path, "w", encoding="utf-8") as f:
            for chunk in data_iterator:
                for item in chunk:
                    if output_format == "jsonl":
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    total_count += 1

        return total_count
