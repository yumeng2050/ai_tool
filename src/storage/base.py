"""站点台账仓储抽象。

实现可替换：SQLite、JSON 文件，后续切换到 ORM / 其他数据库。
上层只依赖本接口，不关心持久化细节。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.models.domain import SiteRecord, SiteStatus


class SiteRepository(ABC):
    """站点台账读写接口。"""

    @abstractmethod
    def add(self, site: SiteRecord) -> None:
        """新增一条站点记录。"""

    @abstractmethod
    def update(self, site: SiteRecord) -> None:
        """更新已有站点记录。"""

    @abstractmethod
    def get(self, url: str) -> Optional[SiteRecord]:
        """按 URL 查询站点记录，不存在时返回 ``None``。"""

    @abstractmethod
    def list_all(self) -> list[SiteRecord]:
        """返回全部站点记录。"""

    def list_by_status(self, status: SiteStatus) -> list[SiteRecord]:
        """按分析状态筛选站点（通用默认实现）。"""
        return [site for site in self.list_all() if site.status == status]
