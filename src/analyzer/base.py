"""资料分析抽象。

分两类场景：

- **首次分析**：对未分析的资料做归纳整理；
- **增量（二次）分析**：只处理某站点自上次分析时间之后的更新内容。

实现可替换：不同提示词模板、不同模型、规则 + 模型混合等。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.domain import AnalysisResult, RawDocument, SiteRecord


class DocumentAnalyzer(ABC):
    """资料分析接口。"""

    @abstractmethod
    def analyze(self, documents: list[RawDocument]) -> AnalysisResult:
        """对一批资料做归纳整理，结果需可溯源到来源文件。"""

    @abstractmethod
    def analyze_incremental(
        self,
        site: SiteRecord,
        documents: list[RawDocument],
    ) -> AnalysisResult:
        """增量分析：仅针对上次分析时间之后的新资料。"""
