---
name: git-annual-report
description: >-
  Generate a beautiful, shareable, offline single-file HTML "year in code"
  annual report from any local git repositories — commit totals, monthly
  lines, 24h & weekday rhythm, day-by-day heatmap, tech-stack mix, top
  projects/files/dirs, commit-type persona (creator vs firefighter),
  night-vs-day keywords, and a final verdict screen. Pure Python stdlib,
  zero dependencies, never touches the network. Use whenever the user asks
  for an annual / year-end code report, git year in review, a recap or
  summary of their commits, "how much code did I write", repo/git
  statistics, or says 年度报告 / 年度总结 / 年报 / 代码年报 / 提交统计 —
  even if they only mention one repo and a year.
---

# Git Annual Report（代码年度报告生成器）

Turn local git history into a polished, scroll-animated, single-file HTML
annual report in the style of "Spotify Wrapped" — 16 screens of stats and
personality, fully offline, ready to send to friends. The report content is
in Chinese; the tool works on macOS/Linux with Python 3.10+ (stdlib only)
and git. It only ever runs **read-only** git commands.

## What the report contains

Overview cards · full-year daily heatmap · 24-hour distribution · weekday
distribution · monthly insertions/deletions · top projects · tech-stack mix
by changed lines · keyword cloud · timeline easter eggs · superlatives ·
commit-type persona (feat/fix balance) · subject style & night-vs-day
keywords · daily start-time table · commit rhythm (median gap, longest gap,
burst days) · hottest files/dirs · final 3-badge verdict.

## Bundled tool

Everything lives in `scripts/annual_report/` (relative to this skill's base
directory). No installation step: run it with `python3 -m` from the
`scripts/` directory.

```bash
cd <skill-base-dir>/scripts

# 30-second demo, no git repo needed (deterministic sample data):
python3 -m annual_report --demo --output demo-report.html

# Real data — one or more repos, a year:
python3 -m annual_report /path/to/repo --year 2026 --output report.html
python3 -m annual_report ~/work/api ~/work/app --year 2026

# Shared/multi-author repo — keep only one person's commits:
python3 -m annual_report /path/to/repo --year 2026 --author zhang@example.com
```

Full CLI: `repos` (positional, multiple) · `--year` (default: current year)
· `--demo` · `--seed N` (demo randomness; same seed = identical report) ·
`--output PATH` (default `./annual-report.html`; parent dir must exist) ·
`--author` (name or email, case-insensitive substring).

Exit codes: `0` success — **including an empty year** (a valid repo with no
commits that year produces an empty-state report, by design); `2` bad path /
not a git repo / missing output dir (error goes to stderr).

## Invocation examples

**Example 1 · 30-second demo (no repo needed)**

```bash
cd <skill-base-dir>/scripts
python3 -m annual_report --demo --output demo-report.html
# → 报告已生成：…/demo-report.html (~64KB, all 16 screens)
```

**Example 2 · real repository**

```bash
python3 -m annual_report ~/develop/yunran/oms --year 2026
# → 报告已生成：…/annual-report.html
# Real output for that repo: 169 commits, busiest day 21 commits,
# hottest file OceanEngineSchedule.java (46 touches),
# verdict badges「日光工作者 · 创造者 · 清道夫」
```

**Example 3 · multiple repos + author filter**

```bash
python3 -m annual_report ~/work/api ~/work/app --year 2025 \
  --author zhang@example.com --output my-2025.html
```

**Example 4 · conversational trigger (what the agent should do)**

> User: "给我的 oms 仓库出一份 2025 年的代码年报"

Agent actions: `cd` into the skill's `scripts/` dir → run the Example-2
command with `--year 2025` → verify exit code 0 and output ≥ 40KB → tell the
user to open the HTML in a browser. No repo given? Run the `--demo` first.

## Workflow

1. Get the inputs: repo path(s) and year. If the user gives none and just
   wants to see what this is, run the `--demo` command first — it needs
   nothing.
2. Generate the report with the commands above. Large repos are fine; the
   tool streams one `git log` per repo.
3. Verify: exit code 0 and the output file exists and is non-trivially
   sized (a full report is typically > 40 KB). If the file is small, check
   stderr — usually a wrong year or an author filter that matched nothing.
4. Tell the user to open the HTML file in a browser (double-click works;
   everything is inlined, no network needed) and scroll.

## Interpreting the numbers (tell the user when relevant)

- Lines are `git log --numstat` insertions/deletions of non-merge commits;
  binary files count as 0. Times use each commit's **original timezone**,
  no UTC normalization; year filtering is by author-time year.
- A mass reformat or line-ending change (CRLF↔LF) shows up as one month
  with near-balanced millions of added/removed lines. That is real git
  data, not a bug — warn the user before they panic.
- Same-name repos from different paths are counted separately (never
  silently merged).
- "New/deleted files" are numstat-feature heuristics (first appearance
  purely additive ≈ born; last appearance purely subtractive ≈ killed),
  labeled as approximate on the page itself.

## Customizing

The pipeline is deliberately split: `stats.py` (pure functions, one per
screen) → `models.py` (frozen dataclasses) → `render.py`/`assets.py`
(HTML assembly, all styles inline). To add a screen: new pure function in
`stats.py`, wire it in `cli.py:build_report_data`, add a template in
`assets.py` and a section function in `render.py`. Keep the conventions:
sort everything (frequency desc, then name asc) so output stays
deterministic, escape user-derived strings with `html.escape`, and make
empty input render nothing rather than crash.
