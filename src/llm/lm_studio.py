"""LM Studio / OpenAI 兼容接口实现。

LM Studio 开启 Local Server 后暴露 OpenAI 兼容的
``/v1/chat/completions`` 接口；其他兼容该协议的本地或云端服务
也可复用本实现，仅需修改配置中的地址与模型名。

HTTP 客户端 ``httpx`` 在首次调用时延迟导入，未安装时给出明确提示。
"""
from __future__ import annotations

from typing import Optional

from src.config.settings import AppSettings
from src.llm.base import LLMProvider


class LMStudioProvider(LLMProvider):
    """通过 OpenAI 兼容协议调用本地 LM Studio 模型。"""

    name = "lm_studio"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "缺少依赖 httpx，请先执行 pip install -r requirements.txt"
            ) from exc

        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature or self.settings.temperature,
            "max_tokens": max_tokens or self.settings.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}

        response = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.settings.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        # 推理模型可能把内容放在 reasoning_content，content 暂时为空，做兜底
        return message.get("content") or message.get("reasoning_content") or ""

    def list_models(self) -> list[str]:
        """获取本地服务当前可用的模型 id 列表。"""
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "缺少依赖 httpx，请先执行 pip install -r requirements.txt"
            ) from exc

        url = f"{self.settings.llm_base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        response = httpx.get(
            url, headers=headers, timeout=self.settings.request_timeout
        )
        response.raise_for_status()
        data = response.json()
        return [model["id"] for model in data.get("data", [])]
