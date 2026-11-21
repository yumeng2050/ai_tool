"""原始资料落盘。

把抓取到的 :class:`~src.models.domain.RawDocument` 写成 Markdown 文件存入
``data/raw/``，并在台账中记录相对路径，便于后续溯源。
"""
from __future__ import annotations

from pathlib import Path

from src.config.settings import AppSettings
from src.models.domain import RawDocument
from src.storage.paths import raw_document_path


def save_raw_document(settings: AppSettings, doc: RawDocument) -> Path:
    """保存原始资料到 ``data/raw/``，返回文件路径。

    保存后 ``doc.file_path`` 记录相对于 ``data_dir`` 的 POSIX 路径。
    """
    path = raw_document_path(settings, doc.site_url, doc.title, doc.collected_at)
    body = (
        f"# {doc.title}\n\n"
        f"- 网址: {doc.site_url}\n"
        f"- 对象: {doc.target or '-'}\n"
        f"- 类型: {doc.category or '-'}\n"
        f"- 采集时间: {doc.collected_at:%Y-%m-%d %H:%M:%S}\n\n"
        f"---\n\n{doc.content}\n"
    )
    path.write_text(body, encoding="utf-8")
    doc.file_path = path.relative_to(settings.data_dir).as_posix()
    return path
