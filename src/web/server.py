"""本地 Web 服务入口。

复用现有 :mod:`src.cli` 的组件装配与 :mod:`src.pipeline` 流程，对外暴露
一组简易 JSON 接口，由 ``static/index.html`` 单页调用。仅绑定本机回环地址。

启动::

    python -m src.web.server
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from src.cli import build_pipeline
from src.config.settings import AppSettings
from src.llm import create_llm_provider, make_message
from src.models.domain import SiteRecord, Target
from src.storage import build_sqlite_repository

settings = AppSettings.load()
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI 信息收集工具")


# ===== 序列化辅助 =====

def _site_to_dict(site: SiteRecord) -> dict:
    return {
        "url": site.url,
        "target": site.target,
        "category": site.category,
        "status": site.status.value,
        "first_found_at": site.first_found_at.strftime("%Y-%m-%d %H:%M"),
        "last_analyzed_at": (
            site.last_analyzed_at.strftime("%Y-%m-%d %H:%M")
            if site.last_analyzed_at
            else None
        ),
        "source_files": site.source_files,
        "note": site.note,
    }


# ===== 请求模型 =====

class DiscoverRequest(BaseModel):
    """发现站点请求：对象名必填，类型与线索可选。"""

    target: str
    category: str = ""
    hints: list[str] = Field(default_factory=list)


# ===== 模型状态检查（结构化版 doctor）=====

def _check_doctor() -> dict:
    info: dict = {
        "provider": settings.provider,
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "data_dir": str(settings.data_dir),
        "dirs": {
            "raw": settings.raw_dir.exists(),
            "output": settings.output_dir.exists(),
            "sites": settings.sites_dir.exists(),
        },
        "site_count": len(build_sqlite_repository(settings).list_all()),
        "reachable": False,
        "models": [],
        "model_matched": False,
        "chat_ok": False,
        "elapsed": None,
        "reply": "",
        "message": "",
    }

    try:
        provider = create_llm_provider(settings)
        models = provider.list_models()
    except RuntimeError as exc:
        info["message"] = f"模型服务不可用：{exc}"
        return info
    except httpx.ConnectError:
        info["message"] = "无法连接：请确认 LM Studio 已启动、已加载模型，且 Local Server 已开启。"
        return info
    except httpx.TimeoutException:
        info["message"] = "连接超时，请检查本地服务是否响应。"
        return info
    except httpx.HTTPStatusError as exc:
        info["message"] = f"接口返回错误 HTTP {exc.response.status_code}"
        return info
    except Exception as exc:  # noqa: BLE001 - 自检场景统一兜底
        info["message"] = f"未知错误 {type(exc).__name__}: {exc}"
        return info

    info["reachable"] = True
    info["models"] = models
    info["model_matched"] = settings.llm_model in models
    if not info["model_matched"]:
        info["message"] = f"配置模型 '{settings.llm_model}' 不在可用列表中，请在 .env 中核对 LLM_MODEL。"
        return info

    started = time.perf_counter()
    try:
        reply = provider.chat(
            [make_message("user", "你好，请用一句话简单回复。")],
            max_tokens=64,
        )
        info["elapsed"] = round(time.perf_counter() - started, 2)
        info["chat_ok"] = True
        info["reply"] = reply.strip()[:100]
        info["message"] = "对话测试成功。"
    except Exception as exc:  # noqa: BLE001
        info["message"] = f"对话测试失败 {type(exc).__name__}: {exc}"
    return info


# ===== 接口 =====

@app.get("/api/doctor")
def api_doctor() -> dict:
    """模型与环境状态检查。"""
    return {"ok": True, "data": _check_doctor()}


@app.post("/api/discover")
def api_discover(req: DiscoverRequest) -> JSONResponse:
    """根据对象名（必填）与可选类型、线索，让模型推荐候选站点并入台账。"""
    target_name = req.target.strip()
    if not target_name:
        return JSONResponse(
            {"ok": False, "message": "对象名必填。"}, status_code=400
        )

    category = req.category.strip() or "未分类"
    hints = [h.strip() for h in req.hints if h and h.strip()]

    pipeline = build_pipeline(settings)
    target = Target(name=target_name, category=category, keywords=hints)
    sites = pipeline.discover_sites(target, hints)
    return {
        "ok": True,
        "message": f"发现 {len(sites)} 个候选站点。",
        "data": [_site_to_dict(site) for site in sites],
    }


@app.get("/api/sites")
def api_sites() -> dict:
    """列出站点台账。"""
    repo = build_sqlite_repository(settings)
    return {"ok": True, "data": [_site_to_dict(site) for site in repo.list_all()]}


@app.post("/api/collect")
def api_collect() -> dict:
    """抓取所有待分析站点，保存原始资料并更新台账。"""
    pipeline = build_pipeline(settings)
    saved = pipeline.collect_and_save()
    data = [
        {"site_url": doc.site_url, "title": doc.title, "file_path": doc.file_path}
        for doc in saved
    ]
    return {"ok": True, "message": f"共保存 {len(saved)} 份原始资料。", "data": data}


@app.post("/api/analyze")
def api_analyze() -> dict:
    """读取原始资料归纳整理，保存结果并更新台账状态。"""
    pipeline = build_pipeline(settings)
    result = pipeline.analyze_all()
    if result is None:
        return {
            "ok": False,
            "message": "data/raw/ 下暂无原始资料，可先点击「抓取收集」。",
            "data": None,
        }
    data = {
        "target": result.target,
        "category": result.category,
        "summary": result.summary,
        "source_files": result.source_files,
        "file_path": result.extra.get("file_path"),
    }
    return {"ok": True, "message": "分析完成。", "data": data}


@app.get("/api/results")
def api_results() -> dict:
    """列出历史分析结果文件（按文件名倒序）。"""
    files = [p.name for p in sorted(settings.output_dir.glob("*.md"), reverse=True)]
    return {"ok": True, "data": files}


@app.get("/api/result")
def api_result(name: str) -> JSONResponse:
    """读取指定历史结果文件正文（限制在 output 目录内，防目录穿越）。"""
    base = settings.output_dir.resolve()
    path = (base / name).resolve()
    if not str(path).startswith(str(base)) or not path.exists():
        return JSONResponse(
            {"ok": False, "message": "结果文件不存在。"}, status_code=404
        )
    return {
        "ok": True,
        "data": {"name": path.name, "content": path.read_text(encoding="utf-8")},
    }


@app.get("/")
def index() -> HTMLResponse:
    """返回单页前端。"""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.exception_handler(Exception)
def _on_error(_request, exc: Exception) -> JSONResponse:
    """统一异常兜底，前端按 ok 标志展示。"""
    return JSONResponse(
        {"ok": False, "message": f"{type(exc).__name__}: {exc}"},
        status_code=500,
    )


def main() -> None:
    """启动本机 Web 服务。"""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
