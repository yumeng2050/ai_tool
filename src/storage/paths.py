"""目录与文件命名约定。

资料按「时间 + 内容」命名；命名规则集中在本模块，后续调整只改这里。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.config.settings import AppSettings


def _slug(text: str, max_len: int = 40) -> str:
    """把标题压缩为安全的文件名片段。"""
    cleaned = (text or "untitled").strip().replace(" ", "-")
    return cleaned[:max_len].strip("-") or "untitled"


def raw_document_path(
    settings: AppSettings,
    site_url: str,
    title: str,
    collected_at: datetime | None = None,
) -> Path:
    """原始资料文件路径：``时间_标题.md``。"""
    timestamp = (collected_at or datetime.now()).strftime("%Y%m%d-%H%M%S")
    name = f"{timestamp}_{_slug(title or site_url)}.md"
    return settings.raw_dir / name


def analysis_result_path(
    settings: AppSettings,
    target: str,
    category: str,
    created_at: datetime | None = None,
) -> Path:
    """分析结果文件路径：``时间_对象_类型.md``。"""
    timestamp = (created_at or datetime.now()).strftime("%Y%m%d-%H%M%S")
    name = f"{timestamp}_{_slug(target)}_{_slug(category)}.md"
    return settings.output_dir / name
