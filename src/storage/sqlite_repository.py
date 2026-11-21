"""SQLite 站点台账实现。

数据库文件位于 ``data/sites/sites.db``（已被 ``.gitignore`` 忽略，不纳入版本库）。
表结构与领域模型 :class:`~src.models.domain.SiteRecord` 一一对应：

- 时间字段以 ISO8601 字符串存储；
- ``source_files`` 以 JSON 数组字符串存储；
- 上层只依赖 :class:`~src.storage.base.SiteRepository` 接口，后续可替换其他存储。
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from src.config.settings import AppSettings
from src.models.domain import SiteRecord, SiteStatus
from src.storage.base import SiteRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    url              TEXT PRIMARY KEY,
    target           TEXT NOT NULL,
    category         TEXT NOT NULL,
    status           TEXT NOT NULL,
    first_found_at   TEXT NOT NULL,
    last_analyzed_at TEXT,
    source_files     TEXT NOT NULL DEFAULT '[]',
    note             TEXT
)
"""


def _row_to_record(row: sqlite3.Row) -> SiteRecord:
    """把数据库行转换为领域模型。"""
    last_analyzed = row["last_analyzed_at"]
    return SiteRecord(
        url=row["url"],
        target=row["target"],
        category=row["category"],
        status=SiteStatus(row["status"]),
        first_found_at=datetime.fromisoformat(row["first_found_at"]),
        last_analyzed_at=(
            datetime.fromisoformat(last_analyzed) if last_analyzed else None
        ),
        source_files=json.loads(row["source_files"] or "[]"),
        note=row["note"],
    )


class SQLiteSiteRepository(SiteRepository):
    """基于 SQLite 文件的站点台账。"""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ===== 内部工具 =====

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextlib.contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """事务上下文：提交后关闭连接。"""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._db() as conn:
            conn.execute(SCHEMA)

    @staticmethod
    def _serialize(site: SiteRecord) -> tuple:
        return (
            site.url,
            site.target,
            site.category,
            site.status.value,
            site.first_found_at.isoformat(),
            site.last_analyzed_at.isoformat() if site.last_analyzed_at else None,
            json.dumps(site.source_files, ensure_ascii=False),
            site.note,
        )

    # ===== SiteRepository 接口实现 =====

    def add(self, site: SiteRecord) -> None:
        """新增一条站点记录；URL 已存在时由数据库主键约束报错。"""
        with self._db() as conn:
            conn.execute(
                "INSERT INTO sites "
                "(url, target, category, status, first_found_at, "
                "last_analyzed_at, source_files, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                self._serialize(site),
            )

    def update(self, site: SiteRecord) -> None:
        """更新已有站点记录的全部字段。"""
        with self._db() as conn:
            conn.execute(
                "UPDATE sites SET target=?, category=?, status=?, first_found_at=?, "
                "last_analyzed_at=?, source_files=?, note=? WHERE url=?",
                (
                    site.target,
                    site.category,
                    site.status.value,
                    site.first_found_at.isoformat(),
                    site.last_analyzed_at.isoformat() if site.last_analyzed_at else None,
                    json.dumps(site.source_files, ensure_ascii=False),
                    site.note,
                    site.url,
                ),
            )

    def get(self, url: str) -> Optional[SiteRecord]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM sites WHERE url=?", (url,)
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_all(self) -> list[SiteRecord]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM sites ORDER BY first_found_at"
            ).fetchall()
        return [_row_to_record(row) for row in rows]


def build_sqlite_repository(settings: AppSettings) -> SQLiteSiteRepository:
    """按配置创建 SQLite 台账（数据库文件位于 data/sites/sites.db）。"""
    return SQLiteSiteRepository(settings.sites_dir / "sites.db")
