"""领域数据模型。

模块间统一传递的核心结构。当前使用标准库 ``dataclass`` 实现，
后续如需字段校验 / 序列化，可平滑替换为 pydantic，不影响上层调用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SiteStatus(str, Enum):
    """站点分析状态。"""

    PENDING = "pending"      # 未分析
    ANALYZED = "analyzed"    # 已分析


@dataclass
class Target:
    """关注对象与资料类型。"""

    name: str                                   # 对象：国家 / 人物 / 机构
    category: str                               # 类型：财政 / 结构 / 历史
    keywords: list[str] = field(default_factory=list)


@dataclass
class SiteRecord:
    """信息源站点台账记录。"""

    url: str
    target: str
    category: str
    status: SiteStatus = SiteStatus.PENDING
    first_found_at: datetime = field(default_factory=datetime.now)
    last_analyzed_at: Optional[datetime] = None
    source_files: list[str] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class RawDocument:
    """抓取并提取正文后的原始资料。"""

    site_url: str
    title: str
    content: str
    collected_at: datetime = field(default_factory=datetime.now)
    file_path: Optional[str] = None
    target: Optional[str] = None
    category: Optional[str] = None


@dataclass
class AnalysisResult:
    """归纳整理后的分析结果。"""

    target: str
    category: str
    summary: str
    source_files: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    extra: dict = field(default_factory=dict)
