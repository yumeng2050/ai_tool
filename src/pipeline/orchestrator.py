"""流程编排。

串联「渠道发现 -> 抓取收集 -> 分析归纳」三个阶段。具体组件通过构造函数
注入，便于替换实现，也便于在测试中传入替身（mock）。

扩展点：
- 新增阶段：在本类中增加对应方法，并在 CLI 挂载子命令；
- 阶段前后钩子：可在各方法内预留 ``before_*`` / ``after_*`` 回调；
- 替换组件：只要实现对应抽象接口，无需改动编排逻辑。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from src.analyzer import DocumentAnalyzer
from src.collector import ChannelCollector
from src.config.settings import AppSettings
from src.crawler import Crawler, probe_url
from src.llm import LLMProvider
from src.models.domain import (
    AnalysisResult,
    RawDocument,
    SiteRecord,
    SiteStatus,
    Target,
)
from src.storage import (
    SiteRepository,
    load_raw_documents,
    load_user_documents,
    save_analysis_result,
    save_raw_document,
)

logger = logging.getLogger(__name__)


class Pipeline:
    """主流程编排器。"""

    def __init__(
        self,
        settings: AppSettings,
        llm: Optional[LLMProvider] = None,
        collector: Optional[ChannelCollector] = None,
        crawler: Optional[Crawler] = None,
        analyzer: Optional[DocumentAnalyzer] = None,
        repository: Optional[SiteRepository] = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.collector = collector
        self.crawler = crawler
        self.analyzer = analyzer
        self.repository = repository

    @staticmethod
    def _require(component, name: str):
        if component is None:
            raise NotImplementedError(f"组件 {name} 尚未实现，待后续补齐")
        return component

    # ===== 阶段一：渠道发现 =====

    def discover_sites(
        self,
        target: Target,
        hints: list[str] | None = None,
    ) -> list[SiteRecord]:
        """发现候选站点并把新站点写入台账。"""
        accepted, _rejected = self.discover_with_report(target, hints)
        return accepted

    def discover_with_report(
        self,
        target: Target,
        hints: list[str] | None = None,
    ) -> tuple[list[SiteRecord], list[dict]]:
        """发现候选站点，逐个验证网址真实可达后再入库。

        模型可能凭记忆编造网址，这里对每个候选地址做一次真实探测，
        不可访问、非网页或疑似占位地址直接丢弃，并返回丢弃原因。

        :return: ``(已入库站点, 被丢弃站点与原因)``
        """
        collector = self._require(self.collector, "ChannelCollector")
        repo = self._require(self.repository, "SiteRepository")

        sites = collector.discover(target, hints)
        accepted: list[SiteRecord] = []
        rejected: list[dict] = []

        for site in sites:
            ok, reason = probe_url(site.url)
            if not ok:
                logger.info("网址验证未通过，丢弃 %s：%s", site.url, reason)
                rejected.append({"url": site.url, "reason": reason})
                continue

            if repo.get(site.url) is not None:
                rejected.append({"url": site.url, "reason": "台账中已存在"})
                continue

            repo.add(site)
            accepted.append(site)

        return accepted, rejected

    # ===== 阶段二：抓取收集 =====

    def collect_pending(self) -> list[RawDocument]:
        """抓取所有未分析站点，返回原始资料列表。"""
        crawler = self._require(self.crawler, "Crawler")
        repo = self._require(self.repository, "SiteRepository")

        documents: list[RawDocument] = []
        for site in repo.list_by_status(SiteStatus.PENDING):
            document = crawler.fetch(site)
            if document is not None:
                documents.append(document)
        return documents

    def collect_and_save(self) -> list[RawDocument]:
        """抓取所有待抓取站点，落盘原始资料并更新台账来源文件清单。"""
        saved, _skipped = self.collect_with_report()
        return saved

    def collect_with_report(
        self,
    ) -> tuple[list[RawDocument], list[dict]]:
        """抓取待分析站点，同时返回被跳过的站点与原因。

        - 已有来源文件的站点视为已抓取，不再重复抓取；
        - 抓取失败或内容校验未通过的站点记录原因，便于前端展示。
        """
        crawler = self._require(self.crawler, "Crawler")
        repo = self._require(self.repository, "SiteRepository")

        saved: list[RawDocument] = []
        skipped: list[dict] = []
        for site in repo.list_by_status(SiteStatus.PENDING):
            if site.source_files:
                skipped.append({"url": site.url, "reason": "已抓取过，跳过重复抓取"})
                continue

            document = crawler.fetch(site)
            if document is None:
                reason = getattr(crawler, "last_skip_reason", "") or "无可提取正文"
                skipped.append({"url": site.url, "reason": reason})
                continue

            save_raw_document(self.settings, document)
            if document.file_path and document.file_path not in site.source_files:
                site.source_files.append(document.file_path)
            repo.update(site)
            saved.append(document)
        return saved, skipped

    # ===== 阶段三：分析归纳 =====

    def run_analysis(self, documents: list[RawDocument], instructions: str = ""):
        """对一批原始资料做归纳整理。"""
        analyzer = self._require(self.analyzer, "DocumentAnalyzer")
        return analyzer.analyze(documents, instructions)

    def analyze_all(self, instructions: str = "") -> Optional[AnalysisResult]:
        """读取 ``data/raw/`` 与用户自备资料，归纳整理并保存结果，更新台账状态。

        网页抓取资料与 ``data/user_files/`` 下的用户资料会一起参与归纳；
        本地文件不对应台账站点，只做来源标注。

        :return: 分析结果；没有可分析资料时返回 ``None``
        """
        analyzer = self._require(self.analyzer, "DocumentAnalyzer")
        repo = self._require(self.repository, "SiteRepository")

        web_documents = load_raw_documents(self.settings)
        user_documents = load_user_documents(self.settings)
        documents = web_documents + user_documents
        if not documents:
            return None

        result = analyzer.analyze(documents, instructions)
        save_analysis_result(self.settings, result)

        # 只把网页抓取资料对应的站点标记为已分析，本地文件不涉及台账
        analyzed_urls = {doc.site_url for doc in web_documents}
        for url in analyzed_urls:
            site = repo.get(url)
            if site is not None:
                site.status = SiteStatus.ANALYZED
                site.last_analyzed_at = datetime.now()
                repo.update(site)

        return result

    def run_incremental(self) -> list:
        """增量分析：对已分析站点处理其上次分析时间之后的更新。"""
        analyzer = self._require(self.analyzer, "DocumentAnalyzer")
        repo = self._require(self.repository, "SiteRepository")

        results = []
        for site in repo.list_by_status(SiteStatus.ANALYZED):
            # 具体增量抓取由 Crawler 按 last_analyzed_at 过滤，此处仅编排
            results.append(analyzer.analyze_incremental(site, []))
        return results
