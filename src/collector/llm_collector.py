"""基于 LLM 的渠道发现实现。

调用模型根据关注对象与资料类型推荐候选网站，并把回复中的 JSON 数组
解析为 :class:`~src.models.domain.SiteRecord`。解析做了容错：
- 容忍 JSON 被 Markdown 代码块或思考文字包裹；
- 过滤非法 URL；
- 解析失败时返回空列表并记录日志，不中断主流程。
"""
from __future__ import annotations

import json
import logging
import re

from src.collector.base import ChannelCollector
from src.collector.prompts import SYSTEM_PROMPT, build_discover_prompt
from src.config.settings import AppSettings
from src.llm import LLMProvider, make_message
from src.models.domain import SiteRecord, Target

logger = logging.getLogger(__name__)

URL_PREFIX = ("http://", "https://")


class LLMChannelCollector(ChannelCollector):
    """调用 LLM 推荐候选网站。"""

    def __init__(self, llm: LLMProvider, settings: AppSettings) -> None:
        self.llm = llm
        self.settings = settings

    def discover(
        self,
        target: Target,
        hints: list[str] | None = None,
    ) -> list[SiteRecord]:
        messages = [
            make_message("system", SYSTEM_PROMPT),
            make_message("user", build_discover_prompt(target, hints)),
        ]
        reply = self.llm.chat(
            messages,
            temperature=self.settings.temperature,
        )
        return parse_sites(reply, target)


def parse_sites(reply: str, target: Target) -> list[SiteRecord]:
    """从模型回复中提取 JSON 数组并转换为站点记录。"""
    match = re.search(r"\[.*\]", reply, re.S)
    if not match:
        logger.warning("模型回复中未找到 JSON 数组")
        return []

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("站点 JSON 解析失败: %s", exc)
        return []

    if not isinstance(data, list):
        logger.warning("模型返回的不是 JSON 数组")
        return []

    records: list[SiteRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url.startswith(URL_PREFIX):
            continue
        title = str(item.get("title", "")).strip()
        note = str(item.get("note", "")).strip() or title
        records.append(
            SiteRecord(
                url=url,
                target=target.name,
                category=target.category,
                note=note or None,
            )
        )
    return records
