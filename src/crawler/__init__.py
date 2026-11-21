"""网页抓取层。"""

from src.crawler.base import Crawler
from src.crawler.http_crawler import HTTPCrawler
from src.crawler.quality import check_document, probe_url

__all__ = ["Crawler", "HTTPCrawler", "check_document", "probe_url"]
