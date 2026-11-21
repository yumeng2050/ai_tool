"""命令行入口。

用法示例::

    python -m src.cli doctor                 # 检查配置与环境
    python -m src.cli list-sites             # 列出站点台账
    python -m src.cli add-site --url <网址> --target <对象> --category <类型>
    python -m src.cli discover --target "某国" --category "财政"
    python -m src.cli collect                # 抓取未分析站点
    python -m src.cli analyze                # 分析已收集资料
    python -m src.cli incremental            # 增量分析站点更新
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

import httpx

from src.analyzer import LLMDocumentAnalyzer
from src.collector import LLMChannelCollector
from src.config.settings import AppSettings
from src.crawler import HTTPCrawler
from src.llm import create_llm_provider, make_message
from src.models.domain import SiteRecord, Target
from src.pipeline import Pipeline
from src.storage import build_sqlite_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai_tool", description="AI 信息收集工具"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="检查配置与运行环境")

    p_add = sub.add_parser("add-site", help="手工登记一个信息源站点")
    p_add.add_argument("--url", required=True, help="站点网址")
    p_add.add_argument("--target", required=True, help="关注对象：国家 / 人物 / 机构")
    p_add.add_argument("--category", required=True, help="资料类型：财政 / 结构 / 历史")
    p_add.add_argument("--note", help="备注（可选）")

    sub.add_parser("list-sites", help="列出站点台账")

    p_discover = sub.add_parser("discover", help="发现信息渠道")
    p_discover.add_argument("--target", required=True, help="关注对象：国家 / 人物 / 机构")
    p_discover.add_argument("--category", required=True, help="资料类型：财政 / 结构 / 历史")
    p_discover.add_argument("--hint", action="append", help="额外站点线索，可重复传入")

    sub.add_parser("collect", help="抓取未分析站点")
    p_analyze = sub.add_parser("analyze", help="分析已收集资料")
    p_analyze.add_argument(
        "--instructions", help="归纳要求，如关注重点、输出格式（可选）", default=""
    )
    sub.add_parser("incremental", help="增量分析已有站点更新")
    return parser


def cmd_check_llm(settings: AppSettings) -> None:
    """检查模型服务可达性、模型名匹配情况，并做一次最小对话测试。"""
    print("\n=== 模型连通性 ===")
    try:
        provider = create_llm_provider(settings)
        models = provider.list_models()
    except RuntimeError as exc:
        print(f"模型服务: 不可用（{exc}）")
        return
    except httpx.ConnectError:
        print("模型服务: 无法连接。请确认 LM Studio 已启动、已加载模型，")
        print("          且 Local Server 已开启，端口与 LLM_BASE_URL 一致。")
        return
    except httpx.TimeoutException:
        print("模型服务: 连接超时，请检查本地服务是否响应。")
        return
    except httpx.HTTPStatusError as exc:
        print(f"模型服务: 接口返回错误 HTTP {exc.response.status_code}")
        return
    except Exception as exc:  # noqa: BLE001 - 自检场景下统一兜底展示
        print(f"模型服务: 未知错误 {type(exc).__name__}: {exc}")
        return

    print("模型服务: 可达")
    print("可用模型:")
    for model in models:
        print(f"  - {model}")

    if settings.llm_model not in models:
        print(
            f"\n配置模型 '{settings.llm_model}' 不在可用列表中，跳过对话测试。"
            "\n请在 .env 的 LLM_MODEL 中填写上方列表里的模型 id。"
        )
        return

    print(f"\n配置模型 '{settings.llm_model}': 匹配，开始对话测试 ...")
    started = time.perf_counter()
    try:
        reply = provider.chat(
            [make_message("user", "你好，请用一句话简单回复。")],
            max_tokens=64,
        )
        elapsed = time.perf_counter() - started
        print(f"对话测试: 成功（{elapsed:.2f}s）")
        if reply.strip():
            print(f"回复: {reply.strip()[:100]}")
        else:
            print("回复: （模型尚未产出正式文本，可能仍处于思考阶段）")
    except Exception as exc:  # noqa: BLE001
        print(f"对话测试: 失败 {type(exc).__name__}: {exc}")


def cmd_doctor(settings: AppSettings) -> int:
    """打印当前配置、目录就绪情况、台账概况，并检查模型连通性。"""
    print(f"provider      : {settings.provider}")
    print(f"llm_base_url  : {settings.llm_base_url}")
    print(f"llm_model     : {settings.llm_model}")
    print(f"data_dir      : {settings.data_dir}")
    print(
        "数据目录就绪  : "
        f"raw={settings.raw_dir.exists()} "
        f"output={settings.output_dir.exists()} "
        f"sites={settings.sites_dir.exists()}"
    )
    repo = build_sqlite_repository(settings)
    print(f"台账站点数    : {len(repo.list_all())}")

    cmd_check_llm(settings)
    return 0


def cmd_add_site(settings: AppSettings, args: argparse.Namespace) -> int:
    """登记一个新站点到台账。"""
    repo = build_sqlite_repository(settings)
    if repo.get(args.url) is not None:
        print(f"该站点已在台账中：{args.url}")
        return 0

    site = SiteRecord(
        url=args.url,
        target=args.target,
        category=args.category,
        note=args.note,
    )
    repo.add(site)
    print(f"已登记站点：{args.url}（{args.target} / {args.category}）")
    return 0


def cmd_list_sites(settings: AppSettings) -> int:
    """列出台账中的全部站点。"""
    repo = build_sqlite_repository(settings)
    sites = repo.list_all()
    if not sites:
        print("台账为空，可使用 add-site 登记站点。")
        return 0

    print(f"共 {len(sites)} 个站点：")
    print(f"{'状态':<10} {'对象':<12} {'类型':<10} 最近分析时间 网址")
    for site in sites:
        last = site.last_analyzed_at.strftime("%Y-%m-%d %H:%M") if site.last_analyzed_at else "-"
        print(
            f"{site.status.value:<10} {site.target:<12} {site.category:<10} "
            f"{last:<12} {site.url}"
        )
    return 0


def build_llm(settings: AppSettings, step: str | None = None):
    """按阶段选择模型，并挂上备用来源（主模型失败自动切换）。"""
    from dataclasses import replace

    from src.config.model_choice import model_for_step
    from src.config.providers import enabled_extras
    from src.llm import FallbackProvider

    if step:
        settings = replace(settings, llm_model=model_for_step(settings, step))

    primary = create_llm_provider(settings)
    extras = enabled_extras(settings)
    if extras:
        return FallbackProvider(primary, settings, extras)
    return primary


def build_pipeline(settings: AppSettings, step: str | None = None) -> Pipeline:
    """装配当前已实现的组件：模型、仓储、抓取器、渠道发现器、分析器。

    ``step`` 指定本流程阶段（discover / analyze），用于选用该阶段已记录的模型。
    """
    from dataclasses import replace

    from src.config.model_choice import model_for_step

    if step:
        model = model_for_step(settings, step)
        settings = replace(settings, llm_model=model)

    llm = build_llm(settings, step)
    return Pipeline(
        settings=settings,
        llm=llm,
        repository=build_sqlite_repository(settings),
        crawler=HTTPCrawler(settings),
        collector=LLMChannelCollector(llm, settings),
        analyzer=LLMDocumentAnalyzer(llm, settings),
    )


def cmd_discover(settings: AppSettings, args: argparse.Namespace) -> int:
    """调用 LLM 发现候选站点，验证网址后登记入台账。"""
    pipeline = build_pipeline(settings, "discover")
    target = Target(
        name=args.target,
        category=args.category,
        keywords=args.hint or [],
    )
    sites, rejected = pipeline.discover_with_report(target, args.hint)
    if not sites:
        print("未发现可用站点（候选地址均未通过真实可达性验证）。")
    else:
        print(f"发现并入库 {len(sites)} 个站点：")
        for site in sites:
            note = f"（{site.note}）" if site.note else ""
            print(f"  - {site.url}{note}")

    if rejected:
        print(f"\n丢弃 {len(rejected)} 个候选：")
        for item in rejected:
            print(f"  - {item['url']}：{item['reason']}")
    return 0


def cmd_collect(settings: AppSettings) -> int:
    """抓取所有待分析站点，保存原始资料并更新台账。"""
    pipeline = build_pipeline(settings)
    saved = pipeline.collect_and_save()
    if not saved:
        print("没有可抓取的待分析站点（台账为空或站点均已分析）。")
        return 0

    print(f"共保存 {len(saved)} 份原始资料：")
    for doc in saved:
        print(f"  - {doc.title} -> {doc.file_path}")
    return 0


def cmd_analyze(settings: AppSettings, args: argparse.Namespace | None = None) -> int:
    """读取原始资料归纳整理，保存结果并更新台账状态。"""
    pipeline = build_pipeline(settings, "analyze")
    instructions = getattr(args, "instructions", "") or ""
    result = pipeline.analyze_all(instructions)
    if result is None:
        print("data/raw/ 下暂无原始资料，可先运行 collect 抓取。")
        return 0

    print(f"分析完成：{result.target} / {result.category}")
    print(f"结果文件：{result.extra.get('file_path', '-')}")
    print(f"来源文件 {len(result.source_files)} 份")
    print("\n----- 整理结果 -----")
    print(result.summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = AppSettings.load()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "doctor":
        return cmd_doctor(settings)
    if args.command == "add-site":
        return cmd_add_site(settings, args)
    if args.command == "list-sites":
        return cmd_list_sites(settings)
    if args.command == "discover":
        return cmd_discover(settings, args)
    if args.command == "collect":
        return cmd_collect(settings)
    if args.command == "analyze":
        return cmd_analyze(settings, args)

    # 其余命令待具体组件实现后，在此装配 Pipeline 并调用对应阶段
    print(f"命令 '{args.command}' 骨架已预留，具体流程待组件实现后接入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
