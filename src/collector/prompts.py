"""渠道发现提示词模板。

集中管理提示词，后续调整输出格式或措辞只改这里。
"""
from __future__ import annotations

from src.models.domain import Target

SYSTEM_PROMPT = (
    "你是一名资料收集助手，擅长根据给定的关注对象和资料类型，"
    "推荐可查阅的公开网站。必须只输出 JSON 数组，不要输出解释、思考过程或 Markdown 代码块。"
)


def build_discover_prompt(target: Target, hints: list[str] | None = None) -> str:
    """构造渠道发现的用户提示词。"""
    hint_text = "、".join(hints) if hints else "无"
    keyword_text = "、".join(target.keywords) if target.keywords else "无"
    return (
        f"关注对象：{target.name}\n"
        f"资料类型：{target.category}\n"
        f"关键词：{keyword_text}\n"
        f"补充线索：{hint_text}\n\n"
        "请推荐 3-8 个与上述主题相关的公开网站，返回 JSON 数组，每个元素包含：\n"
        "- url: 网站链接，必须以 http:// 或 https:// 开头\n"
        "- title: 网站或站点名称\n"
        "- note: 一句话说明该网站与主题的关系\n\n"
        "只输出 JSON 数组，格式示例：\n"
        '[{"url":"https://example.com","title":"示例站点","note":"用于查阅相关财政资料"}]'
    )
