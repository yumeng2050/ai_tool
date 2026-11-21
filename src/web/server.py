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

from src.cli import build_llm, build_pipeline
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


class AddSitesRequest(BaseModel):
    """手工添加网址：支持一次粘贴多条（换行分隔）。"""

    target: str
    category: str = ""
    urls: list[str] = Field(default_factory=list)


class ModelChoiceRequest(BaseModel):
    """记录某阶段使用的模型。"""

    step: str
    model: str = ""


class ChatRequest(BaseModel):
    """与分析前的对话请求。"""

    messages: list[dict] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    """归纳分析请求：可带用户提出的具体要求。"""

    instructions: str = ""


class ProviderRequest(BaseModel):
    """备用模型来源：OpenAI 兼容服务。"""

    name: str
    base_url: str
    api_key: str = ""
    model: str = ""


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
        "min_content_chars": settings.min_content_chars,
        "user_files_dir": str(settings.user_files_dir),
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

    pipeline = build_pipeline(settings, "discover")
    target = Target(name=target_name, category=category, keywords=hints)
    sites, rejected = pipeline.discover_with_report(target, hints)
    return {
        "ok": True,
        "message": f"验证通过并入库 {len(sites)} 个站点，丢弃 {len(rejected)} 个（地址不存在或不可访问）。",
        "data": [_site_to_dict(site) for site in sites],
        "rejected": rejected,
    }


@app.get("/api/models")
def api_models() -> dict:
    """列出可用模型与各阶段已记录的模型选择。"""
    from src.config.model_choice import STEP_LABELS, load_choices, model_for_step

    choices = load_choices(settings)
    try:
        provider = create_llm_provider(settings)
        models = provider.list_models()
        reachable = True
        message = ""
    except Exception as exc:  # noqa: BLE001
        models = []
        reachable = False
        message = f"{type(exc).__name__}: {exc}"

    return {
        "ok": True,
        "data": {
            "models": models,
            "reachable": reachable,
            "message": message,
            "default_model": settings.llm_model,
            "choices": {step: model_for_step(settings, step) for step in STEP_LABELS},
            "step_labels": STEP_LABELS,
        },
    }


@app.post("/api/model-choice")
def api_model_choice(req: ModelChoiceRequest) -> JSONResponse:
    """保存某阶段使用的模型（自动记录，重启后仍生效）。"""
    from src.config.model_choice import STEP_LABELS, save_choice

    if req.step not in STEP_LABELS:
        return JSONResponse({"ok": False, "message": "未知阶段。"}, status_code=400)

    try:
        choices = save_choice(settings, req.step, req.model.strip())
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)

    label = STEP_LABELS[req.step]
    model = req.model.strip() or "（默认）"
    return {"ok": True, "message": f"{label}阶段已记录模型：{model}", "data": choices}


@app.post("/api/chat")
def api_chat(req: ChatRequest) -> JSONResponse:
    """整理分析前的对话：用户先提出要求，模型可反问澄清。"""
    from src.config.model_choice import model_for_step

    history = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in req.messages
        if m.get("content")
    ]
    if not history:
        return JSONResponse({"ok": False, "message": "消息为空。"}, status_code=400)

    system = (
        "你是资料整理助手。用户正在提出他对接下来资料整理的要求，"
        "请理解并帮他澄清：可以指出要求中不清楚的地方、给出更具体的整理维度建议，"
        "回复简洁，不要直接开始整理资料。"
    )
    messages = [make_message("system", system)] + [
        make_message(m["role"], m["content"]) for m in history
    ]

    try:
        provider = build_llm(settings, "chat")
        reply = provider.chat(
            messages,
            model=model_for_step(settings, "chat"),
            max_tokens=max(settings.max_tokens, 1024),
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"ok": False, "message": f"{type(exc).__name__}: {exc}"}, status_code=500
        )

    return {"ok": True, "message": "已回复。", "data": {"reply": reply.strip()}}


@app.post("/api/add-sites")
def api_add_sites(req: AddSitesRequest) -> JSONResponse:
    """手工登记一个或多个网址到站点台账。"""
    target_name = req.target.strip()
    if not target_name:
        return JSONResponse({"ok": False, "message": "对象名必填。"}, status_code=400)

    category = req.category.strip() or "未分类"
    repo = build_sqlite_repository(settings)

    added, duplicated, invalid = [], [], []
    for raw in req.urls:
        url = (raw or "").strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            invalid.append(url)
            continue
        if repo.get(url) is not None:
            duplicated.append(url)
            continue

        repo.add(
            SiteRecord(url=url, target=target_name, category=category, note="手工添加")
        )
        added.append(url)

    message = f"新增 {len(added)} 个站点。"
    if duplicated:
        message += f" 已有 {len(duplicated)} 个，跳过。"
    if invalid:
        message += f" {len(invalid)} 个网址格式不正确，已忽略。"

    return {
        "ok": True,
        "message": message,
        "data": {
            "added": added,
            "duplicated": duplicated,
            "invalid": invalid,
        },
    }


@app.get("/api/user-files")
def api_user_files() -> dict:
    """列出用户自备资料目录中的文件。"""
    directory = settings.user_files_dir
    files = []
    if directory.exists():
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.name.startswith(("~$", ".")):
                files.append({"name": path.name, "size": path.stat().st_size})
    return {
        "ok": True,
        "data": {
            "dir": str(directory),
            "files": files,
            "supported": [".txt", ".md", ".pdf", ".docx"],
        },
    }


@app.post("/api/open-user-files")
def api_open_user_files() -> JSONResponse:
    """在本机文件管理器中打开用户资料目录。"""
    import os

    directory = settings.user_files_dir
    directory.mkdir(parents=True, exist_ok=True)
    os.startfile(str(directory))  # noqa: S606 - 仅本机打开资源管理器
    return {"ok": True, "message": f"已打开目录：{directory}"}


@app.get("/api/providers")
def api_providers() -> dict:
    """列出备用模型来源（密钥做脱敏）。"""
    from src.config.providers import load_extra_providers

    def mask(key: str) -> str:
        if not key:
            return ""
        return key[:4] + "…" + key[-4:] if len(key) > 8 else "…"

    items = [
        {
            "name": p.name,
            "base_url": p.base_url,
            "model": p.model,
            "enabled": p.enabled,
            "api_key_masked": mask(p.api_key),
            "has_key": bool(p.api_key),
        }
        for p in load_extra_providers(settings)
    ]
    return {"ok": True, "data": items}


@app.post("/api/providers")
def api_add_provider(req: ProviderRequest) -> JSONResponse:
    """新增（或覆盖同名）备用模型来源。"""
    from src.config.providers import ExtraProvider, add_extra_provider

    if not req.name.strip() or not req.base_url.strip():
        return JSONResponse(
            {"ok": False, "message": "名称与接口地址必填。"}, status_code=400
        )
    if not req.base_url.startswith(("http://", "https://")):
        return JSONResponse(
            {"ok": False, "message": "接口地址需以 http:// 或 https:// 开头。"},
            status_code=400,
        )

    add_extra_provider(
        settings,
        ExtraProvider(
            name=req.name.strip(),
            base_url=req.base_url.strip().rstrip("/"),
            api_key=req.api_key.strip(),
            model=req.model.strip(),
        ),
    )
    return {"ok": True, "message": f"已保存备用来源：{req.name.strip()}（主模型失败时自动切换）"}


@app.delete("/api/providers")
def api_delete_provider(name: str) -> JSONResponse:
    """删除指定备用来源。"""
    from src.config.providers import remove_extra_provider

    remove_extra_provider(settings, name)
    return {"ok": True, "message": f"已删除：{name}"}


@app.get("/api/sites")
def api_sites() -> dict:
    """列出站点台账。"""
    repo = build_sqlite_repository(settings)
    return {"ok": True, "data": [_site_to_dict(site) for site in repo.list_all()]}


@app.post("/api/collect")
def api_collect() -> dict:
    """抓取所有待分析站点，保存原始资料并更新台账。"""
    pipeline = build_pipeline(settings)
    saved, skipped = pipeline.collect_with_report()
    data = [
        {"site_url": doc.site_url, "title": doc.title, "file_path": doc.file_path}
        for doc in saved
    ]
    return {
        "ok": True,
        "message": f"共保存 {len(saved)} 份原始资料，跳过 {len(skipped)} 个站点。",
        "data": data,
        "skipped": skipped,
    }


@app.post("/api/analyze")
def api_analyze(req: AnalyzeRequest | None = None) -> dict:
    """读取原始资料归纳整理，保存结果并更新台账状态。"""
    instructions = (req.instructions if req else "") or ""
    pipeline = build_pipeline(settings, "analyze")
    result = pipeline.analyze_all(instructions)
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
