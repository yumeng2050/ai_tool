"""渠道发现抽象。

根据关注对象与资料类型，寻找候选信息源网站并生成台账记录。
实现方式可替换：LLM 推荐、搜索引擎、手工清单、RSS 源等。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.domain import SiteRecord, Target


class ChannelCollector(ABC):
    """信息渠道发现接口。"""

    @abstractmethod
    def discover(
        self,
        target: Target,
        hints: list[str] | None = None,
    ) -> list[SiteRecord]:
        """发现候选站点，返回待入库的站点记录。

        :param target: 关注对象与资料类型
        :param hints: 额外的站点线索 / 关键词
        """
