"""资料分析提示词模板。

集中管理归纳整理与增量分析的提示词，便于后续调优。
"""
from __future__ import annotations

from src.models.domain import RawDocument, SiteRecord

SYSTEM_PROMPT = (
    "你是严谨的资料整理助手，基于提供的原始资料做归纳总结，"
    "不编造资料中没有的信息；结论应尽量可追溯到来源文件。"
)


def _format_document(doc: RawDocument) -> str:
    source = doc.file_path or doc.site_url
    return (
        f"【来源：{source}】\n"
        f"标题：{doc.title}\n"
        f"网址：{doc.site_url}\n"
        f"正文：\n{doc.content}"
    )


def build_analyze_prompt(documents: list[RawDocument]) -> str:
    """全量归纳提示词。"""
    target = documents[0].target or "未指定"
    category = documents[0].category or "未指定"
    blocks = "\n\n---\n\n".join(_format_document(doc) for doc in documents)
    return (
        f"关注对象：{target}\n"
        f"资料类型：{category}\n\n"
        f"以下是原始资料：\n\n{blocks}\n\n"
        "请归纳整理这些资料：\n"
        "1. 分点总结关键事实与结论；\n"
        "2. 尽量标注每条信息来自哪个来源文件；\n"
        "3. 条理清晰，保留重要数据、时间、名称等细节。\n"
        "直接输出整理结果，不要复述原始资料全文。"
    )


def build_incremental_prompt(site: SiteRecord, documents: list[RawDocument]) -> str:
    """增量分析提示词：仅针对某站点上次分析之后的新资料。"""
    since = (
        site.last_analyzed_at.strftime("%Y-%m-%d %H:%M")
        if site.last_analyzed_at
        else "首次分析"
    )
    blocks = "\n\n---\n\n".join(_format_document(doc) for doc in documents)
    return (
        f"站点：{site.url}\n"
        f"上次分析时间：{since}\n\n"
        f"以下为该站点的新增资料：\n\n{blocks}\n\n"
        "请在已有结论基础上补充本次新增/更新的内容，标注来源文件；"
        "没有新增有效信息时明确说明。"
    )
