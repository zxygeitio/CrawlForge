"""
HTML数据提取器
提供从HTML页面中提取数据的功能
"""

import re
from dataclasses import dataclass
from typing import Any, Optional, Union

from .base import BaseExtractor, ExtractionResult, ExtractionRule
from ..utils.logger import Logger, get_logger


try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


@dataclass
class CSSSelector:
    """CSS选择器配置"""
    selector: str
    attribute: str = None
    index: int = None


class HTMLExtractor(BaseExtractor[dict]):
    """
    HTML数据提取器

    基于BeautifulSoup的CSS选择器提供灵活的数据提取
    """

    def __init__(
        self,
        rules: list[ExtractionRule] = None,
        logger: Logger = None
    ):
        """
        初始化HTML提取器

        Args:
            rules: 提取规则列表
            logger: 日志记录器
        """
        super().__init__(logger)

        if not HAS_BS4:
            raise ImportError("请安装 beautifulsoup4: pip install beautifulsoup4")

        self._rules = rules or []
        self._soup: BeautifulSoup = None

    def add_rule(self, rule: ExtractionRule) -> None:
        """
        添加提取规则

        Args:
            rule: 提取规则
        """
        self._rules.append(rule)

    def parse_html(self, html: str) -> BeautifulSoup:
        """
        解析HTML

        Args:
            html: HTML字符串

        Returns:
            BeautifulSoup对象
        """
        return BeautifulSoup(html, "html.parser")

    async def extract(self, raw_data: Any) -> ExtractionResult[dict]:
        """
        提取HTML数据

        Args:
            raw_data: 原始HTML数据

        Returns:
            提取结果
        """
        try:
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            self._soup = self.parse_html(raw_data)

            result: dict = {}
            errors: list[str] = []

            for rule in self._rules:
                try:
                    value = self._extract_by_rule(rule)

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

        except Exception as e:
            return self.create_error_result(f"HTML提取失败: {e}", raw_data)

    def _extract_by_rule(self, rule: ExtractionRule) -> Any:
        """
        根据规则提取数据

        Args:
            rule: 提取规则

        Returns:
            提取的值
        """
        selector = rule.selector

        if selector.startswith("#"):
            elements = [self._soup.find(id=selector[1:])]
        elif selector.startswith("."):
            elements = self._soup.find_all(class_=selector[1:])
        elif selector.startswith("["):
            match = re.match(r"\[(\w+)=(.+)\]", selector)
            if match:
                elements = self._soup.find_all(attrs={match.group(1): match.group(2)})
            else:
                elements = self._soup.find_all(selector)
        else:
            elements = self._soup.select(selector)

        if not elements:
            return None

        if rule.attribute:
            values = []
            for elem in elements:
                attr_value = elem.get(rule.attribute)
                if attr_value:
                    values.append(attr_value)
            return values if values else None

        if len(elements) == 1:
            return self._get_element_text(elements[0])

        return [self._get_element_text(elem) for elem in elements]

    def _get_element_text(self, element) -> str:
        """
        获取元素文本

        Args:
            element: BeautifulSoup元素

        Returns:
            元素文本
        """
        if element is None:
            return ""

        text = element.get_text(strip=True)

        text = re.sub(r"\s+", " ", text)

        return text

    def extract_links(self, html: str = None) -> list[str]:
        """
        提取所有链接

        Args:
            html: HTML字符串，如果为None则使用已解析的HTML

        Returns:
            链接列表
        """
        soup = self.parse_html(html) if html else self._soup
        if not soup:
            return []

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") or href.startswith("/"):
                links.append(href)

        return links

    def extract_images(self, html: str = None) -> list[str]:
        """
        提取所有图片链接

        Args:
            html: HTML字符串，如果为None则使用已解析的HTML

        Returns:
            图片链接列表
        """
        soup = self.parse_html(html) if html else self._soup
        if not soup:
            return []

        images = []
        for img in soup.find_all("img", src=True):
            images.append(img["src"])

        return images

    def extract_tables(self, html: str = None) -> list[list[list[str]]]:
        """
        提取表格数据

        Args:
            html: HTML字符串，如果为None则使用已解析的HTML

        Returns:
            表格数据列表，每张表格是一个二维列表
        """
        soup = self.parse_html(html) if html else self._soup
        if not soup:
            return []

        tables = []
        for table in soup.find_all("table"):
            table_data = []
            for row in table.find_all("tr"):
                row_data = []
                for cell in row.find_all(["td", "th"]):
                    row_data.append(self._get_element_text(cell))
                if row_data:
                    table_data.append(row_data)
            if table_data:
                tables.append(table_data)

        return tables


class XPathExtractor(BaseExtractor[dict]):
    """
    XPath风格提取器

    使用XPath表达式提取HTML数据
    """

    def __init__(self, rules: list[ExtractionRule] = None, logger: Logger = None):
        """
        初始化XPath提取器

        Args:
            rules: 提取规则列表
            logger: 日志记录器
        """
        super().__init__(logger)

        try:
            from lxml import etree
            self._lxml_available = True
        except ImportError:
            self._logger.warning("lxml未安装，XPathExtractor将不可用")
            self._lxml_available = False

        self._rules = rules or []

    async def extract(self, raw_data: Any) -> ExtractionResult[dict]:
        """
        提取HTML数据

        Args:
            raw_data: 原始HTML数据

        Returns:
            提取结果
        """
        if not self._lxml_available:
            return self.create_error_result("lxml未安装，无法使用XPathExtractor")

        try:
            from lxml import etree

            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            parser = etree.HTMLParser()
            tree = etree.fromstring(raw_data.encode("utf-8"), parser)

            result: dict = {}
            errors: list[str] = []

            for rule in self._rules:
                try:
                    value = self._xpath_extract(tree, rule)

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

            metadata = {
                "errors": errors,
                "field_count": len(self._rules)
            }

            return self.create_success_result(result, raw_data, metadata)

        except Exception as e:
            return self.create_error_result(f"XPath提取失败: {e}", raw_data)

    def _xpath_extract(self, tree, rule: ExtractionRule) -> Any:
        """使用XPath提取数据"""
        from lxml import etree

        elements = tree.xpath(rule.selector)

        if not elements:
            return None

        if rule.attribute:
            if isinstance(elements[0], etree._Element):
                return elements[0].get(rule.attribute)
            return None

        if len(elements) == 1:
            if isinstance(elements[0], str):
                return elements[0].strip()
            text = elements[0].text
            return text.strip() if text else ""

        return [elem.text.strip() if isinstance(elem, etree._Element) else str(elem)
                for elem in elements]


if __name__ == "__main__":
    sample_html = """
    <html>
        <head><title>测试页面</title></head>
        <body>
            <div class="container">
                <h1 id="title">欢迎来到爬虫世界</h1>
                <div class="user-info">
                    <p class="name">张三</p>
                    <p class="email">zhangsan@example.com</p>
                </div>
                <div class="products">
                    <div class="product" data-id="1">
                        <span class="name">商品A</span>
                        <span class="price">100</span>
                    </div>
                    <div class="product" data-id="2">
                        <span class="name">商品B</span>
                        <span class="price">200</span>
                    </div>
                </div>
                <a href="https://example.com/page1">链接1</a>
                <a href="/page2">链接2</a>
                <img src="https://example.com/image.jpg" alt="图片">
            </div>
        </body>
    </html>
    """

    rules = [
        ExtractionRule(
            name="title",
            selector="#title",
            is_required=True
        ),
        ExtractionRule(
            name="username",
            selector=".name",
            default_value="匿名"
        ),
        ExtractionRule(
            name="email",
            selector=".email"
        ),
        ExtractionRule(
            name="product_names",
            selector=".product .name"
        ),
        ExtractionRule(
            name="product_prices",
            selector=".product .price",
            processor=lambda x: float(x) if x.replace(".", "").isdigit() else 0
        )
    ]

    extractor = HTMLExtractor(rules)
    result = extractor.extract(sample_html)

    print("=== HTML提取器测试 ===")
    print(f"成功: {result.success}")
    print(f"数据: {result.data}")
    print(f"错误: {result.error}")

    print("\n=== 链接提取 ===")
    links = extractor.extract_links()
    print(f"链接: {links}")

    print("\n=== 图片提取 ===")
    images = extractor.extract_images()
    print(f"图片: {images}")
