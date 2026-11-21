"""持久化与文件存储层。"""

from src.storage.base import SiteRepository
from src.storage.document_store import (
    load_raw_documents,
    save_analysis_result,
    save_raw_document,
)
from src.storage.paths import analysis_result_path, raw_document_path
from src.storage.sqlite_repository import SQLiteSiteRepository, build_sqlite_repository

__all__ = [
    "SiteRepository",
    "SQLiteSiteRepository",
    "analysis_result_path",
    "build_sqlite_repository",
    "load_raw_documents",
    "raw_document_path",
    "save_analysis_result",
    "save_raw_document",
]
