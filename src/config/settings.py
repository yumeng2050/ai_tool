"""应用配置加载。

配置来源优先级：显式传入的 env > 系统环境变量 > ``.env`` 文件
（``.env`` 依赖可选包 python-dotenv，未安装时静默跳过）。

当前用 dataclass 承载配置，后续如需校验可平滑替换为 pydantic-settings。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _load_dotenv() -> None:
    """可选加载 ``.env``；未安装 python-dotenv 时静默跳过。"""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)


@dataclass
class AppSettings:
    """全局配置。"""

    # ===== 模型接入 =====
    provider: str = "lm_studio"
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "qwen-9b"
    llm_api_key: str = "lm-studio"
    temperature: float = 0.3
    max_tokens: int = 2048
    request_timeout: float = 60.0

    # ===== 存储路径 =====
    data_dir: Path = DEFAULT_DATA_DIR
    raw_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    sites_dir: Path = field(init=False)

    # ===== 抓取策略（预留）=====
    rate_limit_seconds: float = 1.5
    max_depth: int = 1

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.output_dir = self.data_dir / "output"
        self.sites_dir = self.data_dir / "sites"
        for directory in (self.raw_dir, self.output_dir, self.sites_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, env: Optional[Mapping[str, str]] = None) -> "AppSettings":
        """从环境变量 / 可选 ``.env`` 读取配置。"""
        _load_dotenv()
        source = dict(os.environ)
        if env:
            source.update(env)

        def get(key: str, default: Optional[str] = None) -> Optional[str]:
            return source.get(key, default)

        return cls(
            provider=get("LLM_PROVIDER", "lm_studio") or "lm_studio",
            llm_base_url=get("LLM_BASE_URL", "http://localhost:1234/v1")
            or "http://localhost:1234/v1",
            llm_model=get("LLM_MODEL", "qwen-9b") or "qwen-9b",
            llm_api_key=get("LLM_API_KEY", "lm-studio") or "lm-studio",
            temperature=float(get("LLM_TEMPERATURE", "0.3") or 0.3),
            max_tokens=int(get("LLM_MAX_TOKENS", "2048") or 2048),
            request_timeout=float(get("LLM_REQUEST_TIMEOUT", "60") or 60),
            data_dir=Path(get("DATA_DIR", str(DEFAULT_DATA_DIR)) or DEFAULT_DATA_DIR),
            rate_limit_seconds=float(get("RATE_LIMIT_SECONDS", "1.5") or 1.5),
            max_depth=int(get("MAX_DEPTH", "1") or 1),
        )
