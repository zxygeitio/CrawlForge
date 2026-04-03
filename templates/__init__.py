"""
站点模板模块
"""

from .site_template import (
    SiteConfig,
    PageResult,
    BaseSiteTemplate,
    HARBasedSiteTemplate,
    BatchCrawlerTemplate,
    DataPipeline
)

__all__ = [
    "SiteConfig",
    "PageResult",
    "BaseSiteTemplate",
    "HARBasedSiteTemplate",
    "BatchCrawlerTemplate",
    "DataPipeline",
]
