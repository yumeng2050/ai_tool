"""模型提供方工厂。

通过配置 ``provider`` 选择具体实现；新增 Provider 时，
在 :data:`_REGISTRY` 注册映射，或运行时调用 :func:`register_provider`。
"""
from __future__ import annotations

from src.config.settings import AppSettings
from src.llm.base import LLMProvider
from src.llm.lm_studio import LMStudioProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    LMStudioProvider.name: LMStudioProvider,
}


def create_llm_provider(settings: AppSettings) -> LLMProvider:
    """根据配置创建模型提供方实例。"""
    provider_cls = _REGISTRY.get(settings.provider)
    if provider_cls is None:
        raise ValueError(
            f"未知 LLM provider: {settings.provider!r}，"
            f"可选: {', '.join(_REGISTRY)}"
        )
    return provider_cls(settings)


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """运行时注册新的提供方（扩展点，便于插件化接入）。"""
    _REGISTRY[name] = cls
