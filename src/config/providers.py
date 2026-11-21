"""备用模型来源配置（``data/providers.json``）。

主模型来自 ``.env``；这里保存额外的 OpenAI 兼容服务（如免费额度的云端模型），
主模型调用失败时按顺序自动切换过去。

每个条目的字段：

- ``name``：显示名称
- ``base_url``：OpenAI 兼容地址，如 ``https://api.xxx.com/v1``
- ``api_key``：密钥
- ``model``：该服务上的模型 id
- ``enabled``：是否启用
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


@dataclass
class ExtraProvider:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    enabled: bool = True


def _path(settings: AppSettings) -> Path:
    return settings.data_dir / "providers.json"


def load_extra_providers(settings: AppSettings) -> list[ExtraProvider]:
    path = _path(settings)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取备用模型配置失败：%s", exc)
        return []

    items = data.get("providers", []) if isinstance(data, dict) else []
    result: list[ExtraProvider] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("base_url"):
            continue
        result.append(
            ExtraProvider(
                name=item.get("name") or item["base_url"],
                base_url=item["base_url"],
                api_key=item.get("api_key", ""),
                model=item.get("model", ""),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return result


def save_extra_providers(settings: AppSettings, providers: list[ExtraProvider]) -> None:
    path = _path(settings)
    path.write_text(
        json.dumps(
            {"providers": [asdict(p) for p in providers]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def add_extra_provider(settings: AppSettings, provider: ExtraProvider) -> list[ExtraProvider]:
    """新增或按 name 覆盖一条备用来源。"""
    providers = [p for p in load_extra_providers(settings) if p.name != provider.name]
    providers.append(provider)
    save_extra_providers(settings, providers)
    return providers


def remove_extra_provider(settings: AppSettings, name: str) -> list[ExtraProvider]:
    providers = [p for p in load_extra_providers(settings) if p.name != name]
    save_extra_providers(settings, providers)
    return providers


def enabled_extras(settings: AppSettings) -> list[ExtraProvider]:
    return [p for p in load_extra_providers(settings) if p.enabled and p.model]
