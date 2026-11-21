"""模型提供方抽象接口。

新增模型接入（云端 API、其他本地后端、嵌入模型等）时，实现本接口
并在 :mod:`src.llm.factory` 注册即可，上层调用无需改动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


def make_message(role: str, content: str) -> dict:
    """构造一条聊天消息。"""
    return {"role": role, "content": content}


class LLMProvider(ABC):
    """大模型调用统一接口。"""

    name: str = "base"

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步对话，返回模型输出的文本内容。"""

    # ===== 预留扩展点 =====

    def chat_stream(self, messages: list[dict], **kwargs):
        """流式输出（预留）。"""
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        """向量化（预留，用于后续相似度去重 / 语义检索）。"""
        raise NotImplementedError
