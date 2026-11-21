"""HTTP 网页抓取与正文提取实现。

- 使用 ``httpx`` 抓取页面，跟随重定向，带简单限速；
- 正文提取优先使用 trafilatura（若已安装），否则回退 BeautifulSoup；
- 抓取失败、非 HTML 页面或正文过短时返回 ``None``，由上层记录跳过。

后续可新增浏览器动态渲染实现（如 Playwright），只要实现 :class:`~src.crawler.base.Crawler` 接口即可。
"""
from __future__ import annotations

import logging
import time

import httpx

from src.config.settings import AppSettings
from src.crawler.base import Crawler
from src.crawler.quality import check_document
from src.models.domain import RawDocument, SiteRecord

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class HTTPCrawler(Crawler):
    """静态页面抓取器。"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._last_fetch_at = 0.0
        # 最近一次 fetch 被跳过的原因，供上层展示
        self.last_skip_reason = ""

    # ===== 抓取 =====

    def fetch(self, site: SiteRecord) -> RawDocument | None:
        self.last_skip_reason = ""
        self._throttle()
        try:
            response = httpx.get(
                site.url,
                headers={"User-Agent": DEFAULT_UA},
                timeout=self.settings.request_timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("抓取失败 %s: %s", site.url, exc)
            self.last_skip_reason = f"抓取失败：{exc}"
            return None

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "xhtml" not in content_type:
            logger.info("非 HTML 页面，跳过 %s（%s）", site.url, content_type)
            self.last_skip_reason = f"非 HTML 页面（{content_type or '未知类型'}）"
            return None

        html = response.text
        title = self._extract_title(html)
        content = self._extract_content(html)

        ok, reason = check_document(
            url=site.url,
            title=title,
            content=content,
            min_chars=self.settings.min_content_chars,
        )
        if not ok:
            logger.info("内容校验未通过，跳过 %s：%s", site.url, reason)
            self.last_skip_reason = reason
            return None

        return RawDocument(
            site_url=site.url,
            title=title or site.url,
            content=content,
            target=site.target,
            category=site.category,
        )

    def _throttle(self) -> None:
        """两次抓取之间按配置限速。"""
        elapsed = time.monotonic() - self._last_fetch_at
        if elapsed < self.settings.rate_limit_seconds:
            time.sleep(self.settings.rate_limit_seconds - elapsed)
        self._last_fetch_at = time.monotonic()

    # ===== 正文提取 =====

    @staticmethod
    def _extract_title(html: str) -> str:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except ImportError:
            pass
        return ""

    @staticmethod
    def _extract_content(html: str) -> str:
        # 优先 trafilatura（若已安装），正文抽取质量更好
        try:
            import trafilatura

            extracted = trafilatura.extract(html)
            if extracted and extracted.strip():
                return extracted.strip()
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001 - 提取失败回退到 BS4
            logger.warning("trafilatura 提取失败，回退 BS4: %s", exc)

        return HTTPCrawler._extract_content_bs4(html)

    @staticmethod
    def _extract_content_bs4(html: str) -> str:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # 兜底：去掉标签的纯文本
            import re

            return re.sub(r"<[^>]+>", " ", html).strip()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "aside",
                "header",
                "noscript",
                "form",
                "iframe",
                "svg",
            ]
        ):
            tag.decompose()

        # 优先在正文容器内提取，减少侧栏 / 推荐位噪声
        containers = soup.select(
            "article, main, [role=main], #content, .content, .article, "
            ".article-content, .post-content, .entry-content, #main"
        )
        scope = containers[0] if containers else soup.body or soup

        parts: list[str] = []
        seen: set[str] = set()

        # 段落、标题、列表、表格单元格、引用、代码块都纳入提取
        for element in scope.select(
            "h1, h2, h3, h4, p, li, td, th, blockquote, pre, dd, figcaption"
        ):
            text = element.get_text(" ", strip=True)
            if not text or len(text) < 2:
                continue
            if text in seen:
                continue
            seen.add(text)
            parts.append(text)

        # 容器内没有结构性文本时，退化为容器整体文本
        if len("\n".join(parts)) < 200 and scope is not soup:
            fallback = scope.get_text("\n", strip=True)
            if fallback:
                return fallback

        return "\n".join(parts)
