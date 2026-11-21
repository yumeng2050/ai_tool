"""原始资料与分析结果的落盘 / 读取。

- 原始资料：抓取到的 :class:`~src.models.domain.RawDocument` 写入 ``data/raw/``；
- 分析结果：:class:`~src.models.domain.AnalysisResult` 写入 ``data/output/``；
- 读取时把 Markdown 文件头中的元信息还原为领域模型，便于溯源。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from src.config.settings import AppSettings
from src.models.domain import AnalysisResult, RawDocument
from src.storage.paths import analysis_result_path, raw_document_path

logger = logging.getLogger(__name__)

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


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
        f"- 采集时间: {doc.collected_at:{_TIME_FORMAT}}\n\n"
        f"---\n\n{doc.content}\n"
    )
    path.write_text(body, encoding="utf-8")
    doc.file_path = path.relative_to(settings.data_dir).as_posix()
    return path


def _parse_raw_file(path: Path, rel_path: str) -> RawDocument | None:
    """解析单个原始资料 Markdown 文件为 :class:`RawDocument`。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = url = target = category = ""
    collected_at: datetime | None = None
    body_start = 0

    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("- 网址:"):
            url = line.split(":", 1)[1].strip()
        elif line.startswith("- 对象:"):
            target = line.split(":", 1)[1].strip()
        elif line.startswith("- 类型:"):
            category = line.split(":", 1)[1].strip()
        elif line.startswith("- 采集时间:"):
            value = line.split(":", 1)[1].strip()
            try:
                collected_at = datetime.strptime(value, _TIME_FORMAT)
            except ValueError:
                collected_at = None
        elif line.strip() == "---":
            body_start = index + 1
            break

    content = "\n".join(lines[body_start:]).strip()
    if not url or not content:
        logger.warning("原始资料缺少网址或正文，跳过：%s", rel_path)
        return None

    return RawDocument(
        site_url=url,
        title=title or url,
        content=content,
        collected_at=collected_at or datetime.now(),
        file_path=rel_path,
        target=target or None,
        category=category or None,
    )


def load_raw_documents(settings: AppSettings) -> list[RawDocument]:
    """读取 ``data/raw/`` 下全部原始资料，按文件名排序。"""
    documents: list[RawDocument] = []
    for path in sorted(settings.raw_dir.glob("*.md")):
        rel_path = path.relative_to(settings.data_dir).as_posix()
        document = _parse_raw_file(path, rel_path)
        if document is not None:
            documents.append(document)
    return documents


def save_analysis_result(settings: AppSettings, result: AnalysisResult) -> Path:
    """保存分析结果到 ``data/output/``，返回文件路径。

    结果文件记录来源清单；路径写入 ``result.extra["file_path"]``。
    """
    path = analysis_result_path(
        settings, result.target, result.category, result.created_at
    )
    sources = "\n".join(f"  - {item}" for item in result.source_files) or "  - （无）"
    body = (
        f"# 整理结果：{result.target} / {result.category}\n\n"
        f"- 生成时间: {result.created_at:{_TIME_FORMAT}}\n"
        f"- 来源文件:\n{sources}\n\n"
        f"---\n\n{result.summary}\n"
    )
    path.write_text(body, encoding="utf-8")
    rel_path = path.relative_to(settings.data_dir).as_posix()
    result.extra["file_path"] = rel_path
    return path
