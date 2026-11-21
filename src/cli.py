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

from src.config.settings import AppSettings
from src.models.domain import SiteRecord
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
    sub.add_parser("analyze", help="分析已收集资料")
    sub.add_parser("incremental", help="增量分析已有站点更新")
    return parser


def cmd_doctor(settings: AppSettings) -> int:
    """打印当前配置、目录就绪情况与台账概况（模型连通性测试预留）。"""
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
    # 预留：创建 LLMProvider 并发送一条短消息验证连通性
    # llm = create_llm_provider(settings)
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = AppSettings.load()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.command == "doctor":
        return cmd_doctor(settings)
    if args.command == "add-site":
        return cmd_add_site(settings, args)
    if args.command == "list-sites":
        return cmd_list_sites(settings)

    # 其余命令待具体组件实现后，在此装配 Pipeline 并调用对应阶段
    print(f"命令 '{args.command}' 骨架已预留，具体流程待组件实现后接入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
