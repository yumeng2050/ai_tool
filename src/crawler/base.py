"""网页抓取与正文提取抽象。

实现可替换：httpx / requests 静态抓取、正文提取库
（trafilatura / BeautifulSoup）、动态页面渲染（浏览器自动化）等。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.domain import RawDocument, SiteRecord


class Crawler(ABC):
    """站点资料抓取接口。"""

    @abstractmethod
    def fetch(self, site: SiteRecord) -> RawDocument | None:
        """抓取单个站点并提取正文。

        :return: 提取后的原始资料；抓取失败或无有效内容时返回 ``None``
        """
