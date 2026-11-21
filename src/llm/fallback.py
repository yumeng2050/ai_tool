"""带自动切换的模型调用。

主模型（``.env`` 配置）失败时，按顺序尝试 ``data/providers.json`` 中的备用来源，
第一个成功的返回。用于“某个免费额度用完了就自动换下一个”的场景。
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

from src.config.providers import ExtraProvider
from src.config.settings import AppSettings
from src.llm.base import LLMProvider
from src.llm.lm_studio import LMStudioProvider

logger = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    """主模型 + 备用来源的串联调用。"""

    name = "fallback"

    def __init__(
        self,
        primary: LLMProvider,
        settings: AppSettings,
        extras: list[ExtraProvider] | None = None,
    ) -> None:
        self.primary = primary
        self.settings = settings
        self.extras = extras or []

    # ===== 调用 =====

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        errors: list[str] = []

        try:
            return self.primary.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001 - 任一来源失败都切下一个
            reason = f"主模型：{type(exc).__name__}: {exc}"
            logger.warning("主模型调用失败，尝试备用来源 —— %s", reason)
            errors.append(reason)

        for extra in self.extras:
            provider = LMStudioProvider(
                replace(
                    self.settings,
                    llm_base_url=extra.base_url,
                    llm_api_key=extra.api_key or "none",
                    llm_model=extra.model or self.settings.llm_model,
                )
            )
            try:
                result = provider.chat(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=extra.model or None,
                )
                logger.info("已切换到备用来源：%s", extra.name)
                return result
            except Exception as exc:  # noqa: BLE001
                reason = f"{extra.name}：{type(exc).__name__}: {exc}"
                logger.warning("备用来源失败 —— %s", reason)
                errors.append(reason)

        raise RuntimeError("所有模型来源均调用失败：" + "；".join(errors))

    def list_models(self) -> list[str]:
        try:
            return self.primary.list_models()
        except Exception:  # noqa: BLE001 - 主模型不可用时尝试备用
            for extra in self.extras:
                if not extra.model:
                    continue
                provider = LMStudioProvider(
                    replace(
                        self.settings,
                        llm_base_url=extra.base_url,
                        llm_api_key=extra.api_key or "none",
                    )
                )
                try:
                    return provider.list_models()
                except Exception:  # noqa: BLE001
                    continue
            raise
