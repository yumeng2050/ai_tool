"""分步模型选择的持久化配置。

每个阶段（渠道发现 / 归纳分析 / 对话）可以指定不同的模型，
选择结果保存在 ``data/model_choice.json``，重启后仍生效。

未指定的阶段回退到 ``.env`` 中的 ``LLM_MODEL``。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)

STEPS = ("discover", "analyze", "chat")

STEP_LABELS = {
    "discover": "渠道发现",
    "analyze": "归纳分析",
    "chat": "对话",
}


def _config_path(settings: AppSettings) -> Path:
    return settings.data_dir / "model_choice.json"


def load_choices(settings: AppSettings) -> dict[str, str]:
    """读取各阶段已记录的模型选择。"""
    path = _config_path(settings)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取模型选择配置失败：%s", exc)
        return {}
    return {k: v for k, v in data.items() if k in STEPS and isinstance(v, str) and v}


def save_choice(settings: AppSettings, step: str, model: str) -> dict[str, str]:
    """记录某个阶段使用的模型。"""
    if step not in STEPS:
        raise ValueError(f"未知阶段：{step}")

    choices = load_choices(settings)
    if model:
        choices[step] = model
    else:
        choices.pop(step, None)

    path = _config_path(settings)
    path.write_text(
        json.dumps(choices, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return choices


def model_for_step(settings: AppSettings, step: str) -> str:
    """取某阶段应使用的模型：优先已记录的选择，否则用默认配置。"""
    return load_choices(settings).get(step) or settings.llm_model
