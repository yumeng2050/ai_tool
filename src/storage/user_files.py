"""读取用户自备资料目录（``data/user_files/``）。

用户把自己收集到的资料放进该目录，分析阶段会与网页抓取资料一起
交给模型归纳。支持格式：

- 纯文本：``.txt`` / ``.md``
- PDF：``.pdf``（优先 pypdf，其次 PyPDF2 / pdfminer）
- Word：``.docx``（python-docx）

解析失败的文件只记录日志跳过，不影响其余资料。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.config.settings import AppSettings
from src.models.domain import RawDocument

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = (".txt", ".md", ".pdf", ".docx")


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="ignore")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            logger.warning("未安装 PDF 解析库，跳过：%s", path.name)
            return ""

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document  # type: ignore
    except ImportError:
        logger.warning("未安装 python-docx，跳过：%s", path.name)
        return ""

    document = Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)


def _extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return _read_text_file(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    return ""


def load_user_documents(settings: AppSettings) -> list[RawDocument]:
    """读取用户资料目录下所有支持的文件。"""
    documents: list[RawDocument] = []
    directory = settings.user_files_dir
    if not directory.exists():
        return documents

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        # 跳过 Office 临时文件与隐藏文件
        if path.name.startswith(("~$", ".")):
            continue

        try:
            content = _extract(path).strip()
        except Exception as exc:  # noqa: BLE001 - 单个文件失败不影响整体
            logger.warning("读取用户资料失败 %s: %s", path.name, exc)
            continue

        if not content:
            logger.info("用户资料为空或解析失败，跳过：%s", path.name)
            continue

        documents.append(
            RawDocument(
                site_url=f"本地文件：{path.name}",
                title=path.stem,
                content=content,
                collected_at=datetime.fromtimestamp(path.stat().st_mtime),
                file_path=path.relative_to(settings.data_dir).as_posix(),
            )
        )
    return documents
