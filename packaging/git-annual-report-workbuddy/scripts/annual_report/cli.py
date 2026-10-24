"""CLI 参数与流水线编排（架构 §2、技术设计 §2.7）。

CLI 是唯一入口：参数解析、编排、错误信息与退出码全部集中在此。
错误处理（D9）：采集层 ``GitLogError`` → stderr + 退出码 2；
空数据不是错误 → 空态报告 + 退出码 0（R11）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from .demo import generate_demo_commits
from .gitlog import GitLogError, collect_commits
from .models import Commit, ReportData
from .render import render_report
from .stats import (
    daily_heatmap,
    day_start_profile,
    deletion_persona,
    file_life,
    filetype_stats,
    hourly_profile,
    monthly_lines,
    night_day_keywords,
    overview,
    rhythm_facts,
    subject_style,
    superlatives,
    timeline_facts,
    top_dirs,
    top_files,
    top_keywords,
    top_projects,
    type_profile,
    verdict,
    weekday_profile,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="annual-report",
        description=(
            "个人年度报告生成器：解析本地 git 仓库的提交历史"
            "（或使用 --demo 示例数据），生成单文件离线 HTML 年度报告。"
        ),
    )
    parser.add_argument(
        "repos",
        nargs="*",
        metavar="repos",
        help="待统计的本地 git 仓库路径（可多个；仅真实数据模式需要）",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=date.today().year,
        help="目标年份，按提交的作者时间年份过滤（默认：当前年份）",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用内置示例数据生成报告（忽略 repos，不依赖真实仓库）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="示例数据随机种子，仅 --demo 模式生效（默认：2026）",
    )
    parser.add_argument(
        "--output",
        default="annual-report.html",
        help="输出 HTML 文件路径（默认：./annual-report.html）",
    )
    parser.add_argument(
        "--author",
        default=None,
        help="按作者姓名或邮箱过滤（大小写不敏感包含匹配，用于多人共用仓库）",
    )
    return parser


def build_report_data(commits: list[Commit], year: int, source: str) -> ReportData:
    """编排全部统计器，组装渲染层唯一输入（架构 §1 流水线第②③阶段）。"""
    return ReportData(
        year=year,
        source=source,
        generated_at=datetime.now(),
        overview=overview(commits),
        months=monthly_lines(commits),
        hourly=hourly_profile(commits),
        projects=top_projects(commits),
        keywords=top_keywords(commits),
        timeline=timeline_facts(commits),
        weekday=weekday_profile(commits),
        filetypes=filetype_stats(commits),
        heatmap=daily_heatmap(commits, year),
        superlatives=superlatives(commits),
        type_profile=type_profile(commits),
        subject_style=subject_style(commits),
        night_day=night_day_keywords(commits),
        day_start=day_start_profile(commits),
        rhythm=rhythm_facts(commits),
        hot_files=top_files(commits),
        hot_dirs=top_dirs(commits),
        file_life=file_life(commits),
        delete_ratio=deletion_persona(commits),
        verdict=verdict(commits),
        is_empty=not commits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.demo and not args.repos:
        parser.error("需要至少一个仓库路径，或使用 --demo 生成示例报告")

    output = Path(args.output)
    if not output.parent.exists():
        print(f"错误：输出目录不存在：{output.parent}", file=sys.stderr)
        return 2

    try:
        if args.demo:
            commits = generate_demo_commits(seed=args.seed, year=args.year)
            source = "demo"
        else:
            commits = collect_commits(args.repos, year=args.year, author=args.author)
            source = "git"
    except GitLogError as exc:
        print(exc, file=sys.stderr)
        return 2

    data = build_report_data(commits, year=args.year, source=source)
    output.write_text(render_report(data), encoding="utf-8")
    print(f"报告已生成：{output.resolve()}")
    return 0
