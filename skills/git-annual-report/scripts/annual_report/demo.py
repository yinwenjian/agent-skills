"""内置示例数据生成器（R2，技术设计 §2.3）。

确定性铁律（架构 D10）：随机数**只**来自 ``random.Random(seed)`` 实例，
不调用模块级 ``random.*``、不读系统时间——同 seed 两次调用产出逐字段
相等的 ``list[Commit]``。产物与 gitlog 同构，走完全相同的统计与渲染管线。
"""

from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta, timezone

from .models import Commit, FileChange

# 中国标准时区（固定偏移，符合目标用户画像）。
_TZ = timezone(timedelta(hours=8))

_AUTHOR_NAME = "银杏"
_AUTHOR_EMAIL = "yinxing@example.com"

_PROJECT_POOL = ("spark-api", "notes-app", "data-pipeline", "dotfiles", "tiny-db", "blog-engine")

_PREFIXES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "chore")
_SCOPES = ("api", "ui", "db", "auth", "core", "cli", None, None)

# 英文语料：动词 + 名词（动词多为停用词，名词进入关键词统计）。
_EN_VERBS = (
    "add", "fix", "refactor", "tune", "clean", "wire", "guard", "split",
    "drop", "polish", "track", "cache", "scope", "seed", "ship",
)
_EN_NOUNS = (
    "login flow", "cache layer", "api client", "config loader", "db migration",
    "rate limiter", "retry policy", "test harness", "ci pipeline", "docs page",
    "session store", "health check", "query planner", "auth token",
)

# 中文语料：动词（泛动词，进停用词）+ 名词（含技术词典词）。
_CN_VERBS = ("新增", "优化", "修复", "调整", "重构", "完善", "清理", "移除", "补充", "加固")
_CN_NOUNS = (
    "登录流程", "缓存策略", "数据库索引", "接口鉴权", "配置加载", "部署脚本",
    "定时任务", "分页查询", "错误处理", "日志监控", "上传下载", "队列重试",
    "会话超时", "路由校验", "搜索排序", "内存压缩",
)

_FILE_DIRS = ("src/api", "src/core", "web/src", "internal/db", "scripts", "docs")
_FILE_STEMS = ("user", "order", "cache", "client", "server", "handler", "schema", "router", "util", "report")
_FILE_EXTS = (".py", ".ts", ".tsx", ".go", ".sql", ".sh", ".md")

# 双峰加权：深夜（22–1）与午后（14–17）各一个高峰，其余时段低权重。
_HOUR_WEIGHTS = tuple(
    4.0 if h in (22, 23, 0, 1) else (3.5 if 14 <= h <= 17 else 0.6)
    for h in range(24)
)

_WEEKDAY_KEEP = 0.75  # 抽到周末时保留（即不重抽成工作日）的概率上界


def _pick_day(rng: random.Random, year: int, month: int) -> date:
    """随机取日：工作日偏多（约 0.75 概率落在工作日）。"""
    last = calendar.monthrange(year, month)[1]
    chosen = date(year, month, rng.randint(1, last))
    for _ in range(8):
        if chosen.weekday() < 5 or rng.random() < _WEEKDAY_KEEP:
            return chosen
        chosen = date(year, month, rng.randint(1, last))
    return chosen


def _pick_hour(rng: random.Random) -> int:
    return rng.choices(range(24), weights=_HOUR_WEIGHTS, k=1)[0]


def _make_subject(rng: random.Random) -> str:
    prefix = rng.choice(_PREFIXES)
    scope = rng.choice(_SCOPES)
    head = f"{prefix}({scope})" if scope else prefix
    if rng.random() < 0.5:  # 中文说明
        body = f"{rng.choice(_CN_VERBS)}{rng.choice(_CN_NOUNS)}"
        if rng.random() < 0.3:
            body = f"{body}，并补充 {rng.choice(_EN_NOUNS)} 的说明"
    else:  # 英文说明
        body = f"{rng.choice(_EN_VERBS)} {rng.choice(_EN_NOUNS)}"
        if rng.random() < 0.3:
            body = f"{body} and refine {rng.choice(_CN_NOUNS)}"
    return f"{head}: {body}"


def _make_files(rng: random.Random) -> tuple[FileChange, ...]:
    return tuple(
        FileChange(
            path=f"{rng.choice(_FILE_DIRS)}/{rng.choice(_FILE_STEMS)}{rng.choice(_FILE_EXTS)}",
            insertions=rng.randint(1, 200),
            deletions=rng.randint(1, 200),
        )
        for _ in range(rng.randint(1, 5))
    )


def generate_demo_commits(seed: int = 2026, year: int = 2026) -> list[Commit]:
    """生成确定性的模拟提交记录集（R2）。

    规模约 400–600 条；3–5 个模拟项目；12 个月全覆盖；小时按深夜/午后
    双峰加权；工作日偏多；每条挂固定 +08:00 偏移；中英文混合 conventional
    commits 说明；每条带 1–5 个 FileChange。
    """
    rng = random.Random(seed)

    projects = rng.sample(_PROJECT_POOL, rng.randint(3, 5))
    total = rng.randint(420, 580)

    # 月份覆盖保证：每月先垫 5 条，其余按随机权重分配（月份权重随机但覆盖兜底）。
    month_counts = [5] * 12
    month_weights = [1.0 + rng.random() * 3.0 for _ in range(12)]
    for _ in range(total - sum(month_counts)):
        month_counts[rng.choices(range(12), weights=month_weights, k=1)[0]] += 1

    # 项目分配也加权：制造主次分明的项目榜。
    proj_weights = [1.0 + rng.random() * 4.0 for _ in projects]

    commits: list[Commit] = []
    for month, count in enumerate(month_counts, start=1):
        for _ in range(count):
            day = _pick_day(rng, year, month)
            when = datetime(
                day.year, day.month, day.day,
                _pick_hour(rng), rng.randint(0, 59), rng.randint(0, 59),
                tzinfo=_TZ,
            )
            project = rng.choices(projects, weights=proj_weights, k=1)[0]
            commits.append(
                Commit(
                    project=project,
                    repo_path=f"/demo/{project}",
                    sha="%040x" % rng.getrandbits(160),
                    author_name=_AUTHOR_NAME,
                    author_email=_AUTHOR_EMAIL,
                    author_time=when,
                    subject=_make_subject(rng),
                    files=_make_files(rng),
                )
            )
    return commits
