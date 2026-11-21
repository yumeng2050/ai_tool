"""命令行入口。

用法示例::

    python -m src.cli doctor                 # 检查配置与环境
    python -m src.cli discover --target "某国" --category "财政"
    python -m src.cli collect                # 抓取未分析站点
    python -m src.cli analyze                # 分析已收集资料
    python -m src.cli incremental            # 增量分析站点更新
    python -m src.cli list-sites             # 列出站点台账
"""
from __future__ import annotations

import argparse
import logging
import sys

from src.config.settings import AppSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai_tool", description="AI 信息收集工具"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="检查配置与运行环境")

    p_discover = sub.add_parser("discover", help="发现信息渠道")
    p_discover.add_argument("--target", required=True, help="关注对象：国家 / 人物 / 机构")
    p_discover.add_argument("--category", required=True, help="资料类型：财政 / 结构 / 历史")
    p_discover.add_argument("--hint", action="append", help="额外站点线索，可重复传入")

    sub.add_parser("collect", help="抓取未分析站点")
    sub.add_parser("analyze", help="分析已收集资料")
    sub.add_parser("incremental", help="增量分析已有站点更新")
    sub.add_parser("list-sites", help="列出站点台账")
    return parser


def cmd_doctor(settings: AppSettings) -> int:
    """打印当前配置并检查目录就绪情况（模型连通性测试预留）。"""
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
    # 预留：创建 LLMProvider 并发送一条短消息验证连通性
    # llm = create_llm_provider(settings)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = AppSettings.load()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.command == "doctor":
        return cmd_doctor(settings)

    # 其余命令待具体组件实现后，在此装配 Pipeline 并调用对应阶段
    print(f"命令 '{args.command}' 骨架已预留，具体流程待组件实现后接入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
