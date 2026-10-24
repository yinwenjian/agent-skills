---
name: "git-annual-report"
display_name: "git代码提交年度报告生成器"
display_name_en: "Git Commit Annual Report"
description: "Load when the user asks for an annual or year-end code report, git year in review, a recap or summary of their commits, \"how much code did I write\", or repo/git statistics — or says 年度报告 / 年度总结 / 年报 / 代码年报 / 提交统计 — even if they only mention one repo and a year."
description_zh: "把本地 git 仓库的提交历史生成为一份 16 屏、网易云年报风格的单文件离线 HTML 年度报告：年度总览、全年逐日热力图、时段与星期分布、技术栈构成、劳模文件、提交类型人设（创造者 vs 消防员）与年度判词。纯 Python 标准库零依赖，只读 git、不联网。"
description_en: "Generate a 16-screen, Spotify-Wrapped-style single-file offline HTML year-in-code report from local git history: overview, daily heatmap, hour and weekday rhythm, tech-stack mix, hottest files, commit-type persona and a final verdict. Pure Python stdlib, zero dependencies, read-only git, never touches the network."
category: "development"
version: "1.2.0"
author: "yinwenjian"
license: "MIT"
compatibility: "WorkBuddy with local git repository read access and Python 3.10+; the bundled tool runs read-only git commands and writes one HTML file to the workspace, never touches the network"
---

# Git Annual Report（代码年度报告生成器）

把本地 git 历史变成一份滚动动效、可直接分享的单文件 HTML 年度报告——「网易云年度总结」的开发者版。报告正文为中文；工具在 macOS/Linux 上运行，仅需 Python 3.10+（纯标准库）与 git，全程离线，只执行**只读** git 命令。

## 报告包含什么

年度总览 · 全年逐日热力图 · 24 小时分布 · 星期分布 · 逐月增删行 · 最活跃项目 · 技术栈构成（按改动行数）· 关键词云 · 时间线彩蛋 · 极值里程碑 · 提交类型人设（feat/fix 配比：创造者 vs 消防员）· 提交文风与深夜独白 · 开工时间表 · 提交节奏（中位间隔 / 最长空窗 / 爆发日）· 劳模文件与目录 · 三徽章年度判词。

## 工具位置与运行

工具打包在本技能目录的 `scripts/annual_report/`，无需安装，用 `python3 -m` 从 `scripts/` 目录运行：

```bash
cd <技能目录>/scripts

# 30 秒示例，不需要任何 git 仓库（确定性示例数据）：
python3 -m annual_report --demo --output demo-report.html

# 真实数据——一个或多个仓库 + 年份：
python3 -m annual_report /path/to/repo --year 2026 --output report.html
python3 -m annual_report ~/work/api ~/work/app --year 2026

# 多人共用仓库——只统计某个人：
python3 -m annual_report /path/to/repo --year 2026 --author zhang@example.com
```

参数全集：`repos`（位置参数，可多个）· `--year`（默认当前年）· `--demo` · `--seed N`（示例数据种子，同种子结果完全一致）· `--output PATH`（默认 `./annual-report.html`，父目录须存在）· `--author`（姓名或邮箱，大小写不敏感包含匹配）。

退出码：`0` 成功——**包括空年份**（有效仓库当年无提交会生成空态报告，属预期行为）；`2` 路径不存在 / 不是 git 仓库 / 输出目录不存在（错误信息在 stderr）。

## 调用实例

**实例 1 · 30 秒看效果（无需任何仓库）**

```bash
cd <技能目录>/scripts
python3 -m annual_report --demo --output demo-report.html
# → 报告已生成：…/demo-report.html（约 64KB，16 屏完整报告）
```

**实例 2 · 真实仓库年度报告**

```bash
python3 -m annual_report ~/develop/yunran/oms --year 2026
# → 报告已生成：…/annual-report.html
# 该仓库真实产出：169 次提交、单日之王 21 次、劳模文件 OceanEngineSchedule.java
#（46 次改动）、年度判词「日光工作者 · 创造者 · 清道夫」
```

**实例 3 · 多仓库合并 + 只统计自己**

```bash
python3 -m annual_report ~/work/api ~/work/app --year 2025 \
  --author zhang@example.com --output my-2025.html
```

**实例 4 · 对话触发样例（代理该做的事）**

> 用户：「给我的 oms 仓库出一份 2025 年的代码年报」

代理动作：进入本技能 `scripts/` 目录 → 执行实例 2 形式的命令（年份换 2025）→ 校验退出码 0 且输出文件 ≥ 40KB → 告诉用户双击打开 HTML 滚动浏览。若用户没给仓库，先跑实例 1 的 `--demo` 演示效果。

## 工作流程

1. 拿输入：仓库路径与年份。用户没给仓库又想看效果时，先跑 `--demo`；
2. 生成报告（命令见上），大仓库也没问题，每个仓库只跑一次 `git log`；
3. 自检：退出码 0、输出文件存在且不小于 40KB；文件很小通常是年份不对或 author 过滤没匹配到，看 stderr；
4. 提示用户双击用浏览器打开 HTML（全部内联，断网可用），滚动浏览。

## 数字口径（必要时向用户解释）

- 行数来自 `git log --numstat` 非 merge 提交；二进制文件按 0 行；时间用每条提交的**原始时区**，不做 UTC 归一；按作者时间年份过滤；
- 某个月出现近乎对等的百万级增删，通常是换行符批量转换或全量格式化——那是真实 git 数据，不是 bug，先安抚用户；
- 不同路径的同名仓库分开统计，绝不静默合并；
- 「新建/终结文件」是 numstat 特征启发式（首秀纯增≈新建、谢幕纯删≈终结），页面上已标注近似口径。

## 定制扩展

流水线刻意分层：`stats.py`（纯函数，一屏一个）→ `models.py`（frozen dataclass）→ `render.py`/`assets.py`（HTML 组装，样式全内联）。加一屏的正确姿势：`stats.py` 加纯函数 → `cli.py:build_report_data` 接线 → `assets.py` 加模板 → `render.py` 加区块函数。守住三条惯例：所有排序确定（频次降序、同值名称升序）；用户来源字符串一律 `html.escape`；空输入渲染为空而不是崩溃。
