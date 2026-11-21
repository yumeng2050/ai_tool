"""网页抓取层。"""

from src.crawler.base import Crawler
from src.crawler.http_crawler import HTTPCrawler

__all__ = ["Crawler", "HTTPCrawler"]
