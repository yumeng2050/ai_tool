"""抓取内容质量校验。

抓取到的网页不一定是有效资料：可能命中盗版影视站、SEO 垃圾站，
或只抓到导航栏 / 菜单文字。本模块在正文落盘前做一次校验，
不通过的内容直接丢弃，避免污染后续归纳。

判定维度：

1. **域名黑名单**：常见垃圾站、跳转站、导航站域名片段；
2. **标题/正文垃圾关键词**：成人、影视资源、关键词堆砌等特征；
3. **正文有效长度**：低于阈值视为无有效内容；
4. **导航页特征**：短行占比过高、行内容高度重复。

规则集中在常量区，后续可按实际抓取情况扩充。
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# ===== 域名黑名单（命中任意片段即拒绝）=====
BLOCKED_DOMAIN_PATTERNS: tuple[str, ...] = (
    "htjzs.com",
    "dytt",
    "y80s",
    "btbtt",
    "caoliu",
    "xunleidianying",
)

# ===== 标题垃圾关键词（标题命中即判定为 SEO 垃圾页）=====
SPAM_TITLE_KEYWORDS: tuple[str, ...] = (
    "一区二区",
    "二区三区",
    "三区四区",
    "在线观看免费高清",
    "全集资源",
    "国语在线观看",
    "高清无码",
    "免费下载",
    "百度云资源",
    "成人",
    "福利",
    "电影网",
    "影院",
    "天美星空",
    "永久域名",
    "最新地址",
)

# ===== 正文垃圾关键词（出现次数过多视为垃圾页）=====
SPAM_CONTENT_KEYWORDS: tuple[str, ...] = (
    "一区二区",
    "在线观看",
    "永久域名",
    "最新地址",
    "请收藏本站",
    "本站永久",
    "AV在线",
)

# 单位：字符
MIN_LINE_LENGTH = 6
# 短行（导航项）占比超过该比例，且行数足够多时，判定为导航页
NAV_RATIO_THRESHOLD = 0.6
NAV_MIN_LINES = 8


def _normalized_length(text: str) -> int:
    """去掉空白后的字符数。"""
    return len(re.sub(r"\s+", "", text or ""))


def is_blocked_domain(url: str) -> bool:
    """域名是否命中黑名单。"""
    host = (urlparse(url).hostname or "").lower()
    return any(pattern in host for pattern in BLOCKED_DOMAIN_PATTERNS)


def has_spam_title(title: str) -> bool:
    """标题是否含垃圾关键词。"""
    text = (title or "").lower()
    return any(word.lower() in text for word in SPAM_TITLE_KEYWORDS)


def _spam_keyword_hits(content: str) -> int:
    text = (content or "").lower()
    return sum(text.count(word.lower()) for word in SPAM_CONTENT_KEYWORDS)


def looks_like_navigation(content: str) -> bool:
    """是否为导航 / 菜单页：短行占绝大多数且行数较多。"""
    lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
    if len(lines) < NAV_MIN_LINES:
        return False
    short_lines = sum(1 for line in lines if _normalized_length(line) < MIN_LINE_LENGTH + 4)
    return short_lines / len(lines) >= NAV_RATIO_THRESHOLD


def check_document(
    *,
    url: str,
    title: str,
    content: str,
    min_chars: int = 300,
) -> tuple[bool, str]:
    """校验抓取结果是否可作为资料使用。

    :return: ``(是否通过, 未通过原因)``
    """
    if is_blocked_domain(url):
        return False, "域名在黑名单内"

    if has_spam_title(title):
        return False, "标题含垃圾关键词（疑似盗版影视 / SEO 垃圾页）"

    if _normalized_length(content) < min_chars:
        return False, f"正文有效字符不足 {min_chars}"

    if _spam_keyword_hits(content) >= 3:
        return False, "正文含大量垃圾关键词"

    if looks_like_navigation(content):
        return False, "疑似导航 / 菜单页，无有效正文"

    return True, ""
