"""基于 LLM 的资料分析实现。

把一批原始资料交给模型归纳整理，产出带来源文件清单的
:class:`~src.models.domain.AnalysisResult`；增量分析复用同一模型，
提示词区分全量与增量场景。
"""
from __future__ import annotations

import logging

from src.analyzer.base import DocumentAnalyzer
from src.analyzer.prompts import (
    SYSTEM_PROMPT,
    build_analyze_prompt,
    build_incremental_prompt,
)
from src.config.settings import AppSettings
from src.llm import LLMProvider, make_message
from src.models.domain import AnalysisResult, RawDocument, SiteRecord

logger = logging.getLogger(__name__)


class LLMDocumentAnalyzer(DocumentAnalyzer):
    """调用 LLM 归纳整理资料。"""

    def __init__(self, llm: LLMProvider, settings: AppSettings) -> None:
        self.llm = llm
        self.settings = settings

    def analyze(self, documents: list[RawDocument]) -> AnalysisResult:
        if not documents:
            raise ValueError("待分析资料为空")

        messages = [
            make_message("system", SYSTEM_PROMPT),
            make_message("user", build_analyze_prompt(documents)),
        ]
        summary = self.llm.chat(messages, temperature=self.settings.temperature)
        source_files = [doc.file_path for doc in documents if doc.file_path]
        first = documents[0]
        return AnalysisResult(
            target=first.target or "",
            category=first.category or "",
            summary=summary.strip(),
            source_files=source_files,
        )

    def analyze_incremental(
        self,
        site: SiteRecord,
        documents: list[RawDocument],
    ) -> AnalysisResult:
        if not documents:
            return AnalysisResult(
                target=site.target,
                category=site.category,
                summary="（无新增资料）",
                source_files=[],
            )

        messages = [
            make_message("system", SYSTEM_PROMPT),
            make_message("user", build_incremental_prompt(site, documents)),
        ]
        summary = self.llm.chat(messages, temperature=self.settings.temperature)
        source_files = [doc.file_path for doc in documents if doc.file_path]
        return AnalysisResult(
            target=site.target,
            category=site.category,
            summary=summary.strip(),
            source_files=source_files,
        )
