"""git log 采集与解析（架构 D2/D3/D4/D5/D13/D14，技术设计 §2.2）。

git 仅只读调用：``git log`` 与两级 ``git rev-parse`` 预检，不写仓库。
年份过滤与作者过滤都在 Python 侧完成（D3/D4），git 命令不带任何日期参数。
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from dataclasses import replace
from datetime import datetime
from typing import Iterable

from .models import Commit, FileChange


class GitLogError(Exception):
    """仓库不可用或输出不可解析。message 必含仓库路径与原因。"""


# 架构 D2：US（\x1f）是控制字符，不会出现在哈希/人名/邮箱/ISO 时间/正常提交说明中。
_LOG_PRETTY = "%H%x1f%an%x1f%ae%x1f%aI%x1f%s"

# numstat 行：新增 TAB 删除 TAB 路径；二进制文件两列为 '-'（按 0 计，R1）。
_NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.*)$")

_GIT_TIMEOUT = 120


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    """运行一个只读 git 子进程（本模块唯一的子进程出口）。"""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_GIT_TIMEOUT,
    )


def is_git_repo(path: str) -> bool:
    """预检 A（D13）：路径是否为 git 工作树。"""
    if not os.path.isdir(path):
        return False
    proc = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _has_any_commit(path: str) -> bool:
    """预检 B（D13）：仓库是否已有提交（空仓库上 git log 退出码 128，须先分流）。"""
    proc = _run_git(["rev-parse", "-q", "--verify", "HEAD"], cwd=path)
    return proc.returncode == 0


def _shorten_parent(parent: str, home: str) -> str:
    """父目录的家目录前缀缩写为 ~（例：/Users/me/work → ~/work）。"""
    if home and parent == home:
        return "~"
    if home and parent.startswith(home + os.sep):
        return "~" + parent[len(home):]
    return parent


def project_names(paths: list[str], home: str | None = None) -> dict[str, str]:
    """路径 → 项目名（同名消歧，架构 D14 / PRD v1.2）。

    - 输入先按绝对路径去重（保序），同一绝对路径重复传入不产生自撞名；
    - 项目名默认取 basename；
    - basename 在本次输入中撞名的仓库**不合并**：展示名取
      ``basename (父目录)``，父目录为仓库绝对路径的父目录、家目录前缀缩写为 ``~``；
    - 返回 dict 的键为展开 ~ 后的绝对路径。
    """
    if home is None:
        home = os.path.expanduser("~")

    abs_paths: list[str] = []
    seen: set[str] = set()
    for p in paths:
        ap = os.path.abspath(os.path.expanduser(p))
        if ap not in seen:
            seen.add(ap)
            abs_paths.append(ap)

    basenames = [os.path.basename(ap.rstrip(os.sep)) or os.sep for ap in abs_paths]
    counter = Counter(basenames)

    result: dict[str, str] = {}
    for ap, base in zip(abs_paths, basenames):
        if counter[base] > 1:
            parent = _shorten_parent(os.path.dirname(ap), home)
            result[ap] = f"{base} ({parent})"
        else:
            result[ap] = base
    return result


def parse_log_output(
    text: str,
    project: str,
    repo_path: str,
    year: int,
    author: str | None = None,
) -> list[Commit]:
    """纯函数：解析 ``git log --pretty=format:... --numstat`` 输出文本。

    - 头行含 ``\\x1f`` → ``split('\\x1f', 4)`` 得 5 段；段数 ≠ 5 抛 GitLogError；
    - numstat 行归入最近一条提交；``-``（二进制）按 0 计（R1）；
      重命名行（path 含 ``=>``）路径保留原样、行数照常计入（文档即口径）；
    - 空行是块边界，忽略；其余行视为输出格式意外，抛 GitLogError；
    - 过滤（D3/D4）：``author_time.year == year``；author 非空时按
      name/email 大小写不敏感包含匹配；
    - 空文本 → ``[]``（防御性行为；空仓库已由预检 B 分流）。
    """
    commits: list[Commit] = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if not line:
            continue
        if "\x1f" in line:
            parts = line.split("\x1f", 4)
            if len(parts) != 5:
                raise GitLogError(
                    f"{repo_path}: 提交头行字段数不为 5，无法解析: {line[:60]!r}"
                )
            sha, name, email, iso_time, subject = parts
            try:
                author_time = datetime.fromisoformat(iso_time)
            except ValueError as exc:
                raise GitLogError(
                    f"{repo_path}: 无法解析作者时间 {iso_time!r}: {exc}"
                ) from exc
            commits.append(
                Commit(
                    project=project,
                    repo_path=repo_path,
                    sha=sha,
                    author_name=name,
                    author_email=email,
                    author_time=author_time,
                    subject=subject,
                    files=(),
                )
            )
            continue
        m = _NUMSTAT_RE.match(line)
        if m is None:
            raise GitLogError(f"{repo_path}: 输出格式意外，无法解析的行: {line[:60]!r}")
        if not commits:
            raise GitLogError(f"{repo_path}: numstat 行出现在任何提交之前: {line[:60]!r}")
        ins, dels, path = m.group(1), m.group(2), m.group(3)
        change = FileChange(
            path=path,
            insertions=0 if ins == "-" else int(ins),
            deletions=0 if dels == "-" else int(dels),
        )
        commits[-1] = replace(commits[-1], files=commits[-1].files + (change,))

    result = [c for c in commits if c.author_time.year == year]
    if author:
        needle = author.lower()
        result = [
            c
            for c in result
            if needle in c.author_name.lower() or needle in c.author_email.lower()
        ]
    return result


def collect_commits(
    repo_paths: Iterable[str],
    year: int,
    author: str | None = None,
) -> list[Commit]:
    """采集多个仓库在指定年份（按作者时间）的提交，合并为稳定拼接的列表。

    流程（技术设计 §2.2）：
    1. ``project_names`` 确定各仓库项目名（同名不合并，D14）；
    2. 逐仓库两级预检（D13）：
       - 预检 A ``rev-parse --is-inside-work-tree``：非 git 仓库 → GitLogError；
         路径不存在先以 os.path.isdir 判定，给出「路径不存在」消息（R11）；
       - 预检 B ``rev-parse -q --verify HEAD``：非零 → 空仓库，贡献 0 条、
         跳过并继续下一仓库，不报错（R1/R11）；
    3. ``git log --no-merges --pretty=format:... --numstat``（无任何日期参数），
       退出码非零 → GitLogError（附 stderr 首行）——经预检 B 分流后必是真实故障；
    4. 解析结果跨仓库合并：保持仓库传入顺序，仓库内保持 log 顺序。
    """
    paths = list(repo_paths)
    names = project_names(paths)

    # 同一绝对路径重复传入时先去重（保序，D14）。
    ordered: list[str] = []
    seen: set[str] = set()
    for p in paths:
        ap = os.path.abspath(os.path.expanduser(p))
        if ap not in seen:
            seen.add(ap)
            ordered.append(p)

    all_commits: list[Commit] = []
    for p in ordered:
        ap = os.path.abspath(os.path.expanduser(p))
        if not os.path.isdir(ap):
            raise GitLogError(f"{p}: 路径不存在")
        if not is_git_repo(ap):
            raise GitLogError(f"{p}: 不是有效的 git 仓库")
        if not _has_any_commit(ap):
            continue  # 空仓库：空态路径素材，不报错（R11）
        proc = _run_git(
            ["log", "--no-merges", f"--pretty=format:{_LOG_PRETTY}", "--numstat"],
            cwd=ap,
        )
        if proc.returncode != 0:
            first_line = (proc.stderr or "").strip().split("\n")[0]
            raise GitLogError(f"{p}: git log 失败（退出码 {proc.returncode}）: {first_line}")
        all_commits.extend(parse_log_output(proc.stdout, names[ap], ap, year, author))
    return all_commits
