"""
数据提取器模块
"""

from .base import (
    BaseExtractor,
    ExtractionResult,
    ExtractionRule,
    CompositeExtractor
)
from .json_extractor import JSONExtractor, JSONPathExtractor
from .html_extractor import HTMLExtractor, XPathExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "ExtractionRule",
    "CompositeExtractor",
    "JSONExtractor",
    "JSONPathExtractor",
    "HTMLExtractor",
    "XPathExtractor",
]
