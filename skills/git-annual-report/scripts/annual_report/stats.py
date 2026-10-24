"""统计器纯函数（R3–R6、R15–R18，技术设计 §2.4）。

共同契约：无 I/O、无副作用、空列表不抛异常（空态值见各规格）；
返回的集合均已排序（架构 D10：频次降序，同频按名称字典序升序——
保证跨 ``PYTHONHASHSEED`` 可重复）。
"""

from __future__ import annotations

import calendar
import math
import re
import statistics
from collections import Counter
from datetime import date, datetime, timedelta

from .models import (
    Commit,
    DailyHeatmap,
    DayCell,
    DayStart,
    DeleteRatio,
    DirStat,
    FileLife,
    FileStat,
    FiletypeStat,
    HourlyProfile,
    KeywordStat,
    MonthLines,
    NightDayKeywords,
    Overview,
    ProjectStat,
    RhythmFacts,
    SubjectStyle,
    Superlatives,
    TimelineFacts,
    TypeProfile,
    Verdict,
    WeekdayProfile,
)

# ---------------------------------------------------------------------------
# 关键词提取素材（R6，技术设计 §2.4 第 3/4 步：实现时定稿并连同测试样例固化）

# 常见技术词词典：先于 bigram 整词匹配（具体技术词留词典）。
_TECH_DICT = (
    "定时任务",  # 4 字词优先于 2 字词
    "数据库", "接口", "登录", "缓存", "部署", "鉴权", "索引", "迁移",
    "配置", "路由", "会话", "队列", "日志", "监控", "分页", "搜索",
    "加密", "压缩", "上传", "下载", "回滚", "校验", "解析", "渲染",
    "查询", "重试", "超时", "内存", "并发", "网络", "鉴权",
)
_TECH_DICT_SORTED = tuple(sorted(set(_TECH_DICT), key=lambda w: (-len(w), w)))

# 泛动词等停用词（中英各一份）：具体技术词不在此列。
EN_STOPWORDS = frozenset({
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "with",
    "is", "are", "be", "by", "from", "at", "it", "this", "that", "not",
    "all", "new", "up", "into", "use", "using", "used", "add", "adds",
    "update", "updates", "fix", "fixes", "remove", "removes", "make",
    "makes", "some", "more", "when", "then", "else", "if", "no", "do",
    "does", "done", "via", "as", "and", "refine",
})
CN_STOPWORDS = frozenset({
    "的", "了", "和", "与", "及", "或", "在", "为", "对", "被", "把",
    "是", "不", "有", "这", "那", "一个", "一些", "进行", "实现", "支持",
    "调整", "修改", "新增", "添加", "修复", "更新", "删除", "移除",
    "优化", "完善", "处理", "使用", "通过", "可以", "无法", "问题",
    "错误", "导致", "出现", "之后", "之前", "以及", "说明", "补充", "清理", "加固",
})

# conventional commits 前缀（覆盖 feat / feat(scope) / feat! 三种形态，含中文冒号）。
_PREFIX_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\([^)]*\))?!?[:：]\s*"
)
# 英文 token：至少 2 个字符，字母开头。
_EN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]+")
# 连续汉字段。
_CN_SEG_RE = re.compile(r"[\u4e00-\u9fff]+")


# ---------------------------------------------------------------------------
# R3 · 年度总览


def overview(commits: list[Commit]) -> Overview:
    insertions = sum(c.insertions for c in commits)
    deletions = sum(c.deletions for c in commits)
    return Overview(
        total_commits=len(commits),
        insertions=insertions,
        deletions=deletions,
        net_lines=insertions - deletions,
        active_days=len({c.day for c in commits}),
        project_count=len({c.project for c in commits}),
    )


# ---------------------------------------------------------------------------
# 逐月代码量


def monthly_lines(commits: list[Commit]) -> tuple[MonthLines, ...]:
    ins = [0] * 12
    dels = [0] * 12
    for c in commits:
        ins[c.month - 1] += c.insertions
        dels[c.month - 1] += c.deletions
    return tuple(MonthLines(m + 1, ins[m], dels[m]) for m in range(12))


# ---------------------------------------------------------------------------
# R4 · 时段分布（含夜猫子指数与人格化标签）


def _peak_of(bins: tuple[int, ...]) -> int:
    """argmax(bins)，并列取最小小时。"""
    return max(range(24), key=lambda h: (bins[h], -h))


def hourly_profile(commits: list[Commit]) -> HourlyProfile:
    bins_list = [0] * 24
    for c in commits:
        bins_list[c.hour] += 1
    bins = tuple(bins_list)
    total = len(commits)

    if total == 0:
        return HourlyProfile(bins=bins, owl_ratio=0.0, label="", peak_desc="")

    owl_ratio = sum(bins[0:6]) / total
    peak = _peak_of(bins)

    if owl_ratio >= 0.35:
        label = "深夜型选手"
    elif 5 <= peak <= 9:
        label = "早八战士"
    elif 10 <= peak <= 16:
        label = "日光工作者"
    else:
        label = "夜幕输出者"

    # 24 个 3 小时环形窗口，取计数和最大者（并列取起始小时最小）。
    best_h, best_sum = 0, -1
    for h in range(24):
        window_sum = bins[h] + bins[(h + 1) % 24] + bins[(h + 2) % 24]
        if window_sum > best_sum:
            best_h, best_sum = h, window_sum
    peak_desc = f"{best_h:02d}:00–{(best_h + 3) % 24:02d}:00 是你的主场"

    return HourlyProfile(bins=bins, owl_ratio=owl_ratio, label=label, peak_desc=peak_desc)


# ---------------------------------------------------------------------------
# R5 · 最活跃项目（同名不合并：Commit.project 已是消歧名）


def top_projects(commits: list[Commit], limit: int = 5) -> tuple[ProjectStat, ...]:
    by_project: dict[str, tuple[int, int]] = {}
    for c in commits:
        commits_n, lines = by_project.get(c.project, (0, 0))
        by_project[c.project] = (commits_n + 1, lines + c.insertions + c.deletions)

    total_lines = sum(lines for _, lines in by_project.values())

    stats = [
        ProjectStat(
            name=name,
            commits=commits_n,
            lines=lines,
            share=(lines / total_lines) if total_lines > 0 else 0.0,
        )
        for name, (commits_n, lines) in by_project.items()
    ]
    # share 按截断前全量计算（同频降序 → 同频名称字典序升序）。
    stats.sort(key=lambda s: (-s.commits, s.name))
    return tuple(stats[:limit])


# ---------------------------------------------------------------------------
# R6 · 高频关键词


def _chinese_terms(seg: str) -> list[str]:
    """一个连续汉字段 → 词典词 + 剩余部分的 bigram。"""
    terms: list[str] = []
    rest = seg
    for word in _TECH_DICT_SORTED:
        if word in rest:
            terms.extend([word] * rest.count(word))
            rest = rest.replace(word, "\x00")  # 占位，避免拼出新的词
    for piece in rest.split("\x00"):
        for i in range(len(piece) - 1):
            terms.append(piece[i : i + 2])
    return terms


def _keyword_counter(commits: list[Commit]) -> Counter[str]:
    """R6 关键词提取：供 top_keywords 与深夜/白天对照（R22）复用。"""
    counter: Counter[str] = Counter()
    for c in commits:
        subject = _PREFIX_RE.sub("", c.subject, count=1).strip()
        if not subject:
            continue
        for token in _EN_TOKEN_RE.findall(subject):
            token = token.lower()
            if token not in EN_STOPWORDS:
                counter[token] += 1
        for seg in _CN_SEG_RE.findall(subject):
            for term in _chinese_terms(seg):
                if term not in CN_STOPWORDS:
                    counter[term] += 1
    return counter


def _top_terms(counter: Counter[str], limit: int) -> tuple[KeywordStat, ...]:
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(KeywordStat(term, count) for term, count in ranked[:limit])


def top_keywords(commits: list[Commit], limit: int = 20) -> tuple[KeywordStat, ...]:
    return _top_terms(_keyword_counter(commits), limit)


# ---------------------------------------------------------------------------
# PRD 2.3 · 时间线彩蛋


def timeline_facts(commits: list[Commit]) -> TimelineFacts:
    if not commits:
        return TimelineFacts(longest_streak=0, streak_anchor=None, latest=None)

    days = sorted({c.day for c in commits})
    best_len, best_start = 1, days[0]
    run_len, run_start = 1, days[0]
    for prev, cur in zip(days, days[1:]):
        if cur - prev == timedelta(days=1):
            run_len += 1
        else:
            run_len, run_start = 1, cur
        if run_len > best_len:
            best_len, best_start = run_len, run_start

    latest = max(commits, key=lambda c: c.author_time)
    return TimelineFacts(
        longest_streak=best_len,
        streak_anchor=best_start.isoformat(),
        latest=latest,
    )


# ---------------------------------------------------------------------------
# R15 · 星期分布

_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def weekday_profile(commits: list[Commit]) -> WeekdayProfile:
    bins_list = [0] * 7
    for c in commits:
        bins_list[c.author_time.weekday()] += 1  # 0=周一 … 6=周日
    bins = tuple(bins_list)
    total = len(commits)
    if total == 0:
        return WeekdayProfile(bins=bins, weekend_ratio=0.0, peak_desc="")
    weekend_ratio = (bins[5] + bins[6]) / total
    peak = max(range(7), key=lambda w: (bins[w], -w))  # 并列取最靠前的工作日序
    return WeekdayProfile(
        bins=bins,
        weekend_ratio=weekend_ratio,
        peak_desc=f"{_WEEKDAY_NAMES[peak]}是你的爆发日",
    )


# ---------------------------------------------------------------------------
# R16 · 技术栈构成（按扩展名→语言映射聚合改动行数）

_LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".swift": "Swift",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
    ".sql": "SQL", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".md": "Markdown", ".markdown": "Markdown", ".rst": "reStructuredText",
    ".txt": "Text", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".ini": "INI", ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".xml": "XML", ".gradle": "Gradle",
}

_FT_OTHER = "其他"
_FT_LIMIT = 6


def _lang_of(path: str) -> str:
    m = re.search(r"\.[A-Za-z0-9]+$", path)
    lang = _LANG_BY_EXT.get(m.group(0).lower()) if m else None
    return lang if lang else _FT_OTHER


def filetype_stats(commits: list[Commit], limit: int = _FT_LIMIT) -> tuple[FiletypeStat, ...]:
    by_lang: Counter[str] = Counter()
    for c in commits:
        for f in c.files:
            by_lang[_lang_of(f.path)] += f.insertions + f.deletions

    total = sum(by_lang.values())
    if total == 0:
        return ()

    # 「其他」不参与 Top 竞争：无扩展名/未映射 + 榜外语言统一并入末行（R16）。
    other_lines = by_lang.pop(_FT_OTHER, 0)
    ranked = sorted(by_lang.items(), key=lambda kv: (-kv[1], kv[0]))
    other_lines += sum(lines for _, lines in ranked[limit:])

    stats = [
        FiletypeStat(name=name, lines=lines, share=lines / total)
        for name, lines in ranked[:limit]
    ]
    if other_lines > 0:
        stats.append(FiletypeStat(name=_FT_OTHER, lines=other_lines, share=other_lines / total))
    return tuple(stats)


# ---------------------------------------------------------------------------
# R17 · 全年逐日热力图


def daily_heatmap(commits: list[Commit], year: int) -> DailyHeatmap:
    counts: Counter[str] = Counter(c.day.isoformat() for c in commits)
    max_count = max(counts.values(), default=0)

    cells: list[DayCell] = []
    for month in range(1, 13):
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            iso = date(year, month, day).isoformat()
            count = counts.get(iso, 0)
            level = 0 if count == 0 else max(1, math.ceil(count / max_count * 4))
            cells.append(DayCell(date=iso, count=count, level=level))
    return DailyHeatmap(cells=tuple(cells), max_count=max_count)


# ---------------------------------------------------------------------------
# R18 · 极值里程碑


def superlatives(commits: list[Commit]) -> Superlatives:
    if not commits:
        return Superlatives(
            busiest_day=None, busiest_count=0,
            biggest_subject=None, biggest_lines=0,
            first=None, avg_lines=0,
        )

    per_day: Counter[str] = Counter(c.day.isoformat() for c in commits)
    busiest_day = sorted(per_day.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    biggest = sorted(
        commits,
        key=lambda c: (-(c.insertions + c.deletions), c.sha),
    )[0]

    first = min(commits, key=lambda c: c.author_time)
    total_lines = sum(c.insertions + c.deletions for c in commits)

    return Superlatives(
        busiest_day=busiest_day,
        busiest_count=per_day[busiest_day],
        biggest_subject=biggest.subject,
        biggest_lines=biggest.insertions + biggest.deletions,
        first=first,
        avg_lines=round(total_lines / len(commits)),
    )


# ---------------------------------------------------------------------------
# R20 · 提交类型分布（创造者 / 消防员人设）


def type_profile(commits: list[Commit]) -> TypeProfile:
    counter: Counter[str] = Counter()
    prefixed = 0
    for c in commits:
        m = _PREFIX_RE.match(c.subject)
        if m:
            prefixed += 1
            counter[m.group(1)] += 1

    total = len(commits)
    if total == 0:
        return TypeProfile(bins=(), convention_rate=0.0, feat_fix_ratio=0.0, persona="")

    feat, fix = counter.get("feat", 0), counter.get("fix", 0)
    if feat + fix == 0:
        persona, ratio = "未知型", 0.0
    else:
        ratio = feat / (feat + fix)
        persona = "创造者" if ratio >= 0.6 else ("消防员" if ratio <= 0.35 else "平衡手")

    bins = tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))
    return TypeProfile(bins=bins, convention_rate=prefixed / total, feat_fix_ratio=ratio, persona=persona)


# ---------------------------------------------------------------------------
# R21 · 提交说明文风


def subject_style(commits: list[Commit]) -> SubjectStyle:
    if not commits:
        return SubjectStyle(avg_len=0, cn_ratio=0.0, longest=None, shortest=None)
    lens = [len(c.subject) for c in commits]
    longest = min(commits, key=lambda c: (-len(c.subject), c.sha)).subject
    shortest = min(commits, key=lambda c: (len(c.subject), c.sha)).subject
    cn = sum(1 for c in commits if _CN_SEG_RE.search(c.subject))
    return SubjectStyle(
        avg_len=round(sum(lens) / len(lens)),
        cn_ratio=cn / len(commits),
        longest=longest,
        shortest=shortest,
    )


# ---------------------------------------------------------------------------
# R22 · 深夜与白天的关键词


def night_day_keywords(commits: list[Commit], limit: int = 5) -> NightDayKeywords:
    night = [c for c in commits if c.hour < 6]
    day = [c for c in commits if c.hour >= 6]
    return NightDayKeywords(
        night_count=len(night),
        day_count=len(day),
        night_terms=_top_terms(_keyword_counter(night), limit),
        day_terms=_top_terms(_keyword_counter(day), limit),
    )


# ---------------------------------------------------------------------------
# R23 · 开工时间表（每个活跃日的第一次提交）


def day_start_profile(commits: list[Commit]) -> DayStart:
    first_per_day: dict[date, datetime] = {}
    for c in commits:
        d = c.day
        if d not in first_per_day or c.author_time < first_per_day[d]:
            first_per_day[d] = c.author_time

    bins_list = [0] * 24
    for t in first_per_day.values():
        bins_list[t.hour] += 1
    bins = tuple(bins_list)

    total_days = len(first_per_day)
    if total_days == 0:
        return DayStart(bins=bins, before_ten=0.0, earliest_time="", peak_desc="")

    before_ten = sum(bins[0:10]) / total_days
    earliest = min(t.time() for t in first_per_day.values())  # 各日最早时刻再取最早（时刻，不是日期）
    peak = _peak_of(bins)
    return DayStart(
        bins=bins,
        before_ten=before_ten,
        earliest_time=earliest.strftime("%H:%M"),
        peak_desc=f"开工高峰 {peak:02d}:00",
    )


# ---------------------------------------------------------------------------
# R24 · 提交节奏（中位间隔 / 最长空窗 / 爆发日）


def rhythm_facts(commits: list[Commit], burst_threshold: int = 10) -> RhythmFacts:
    if not commits:
        return RhythmFacts(0.0, 0, None, None, 0)

    times = sorted(c.author_time for c in commits)
    gaps_s = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    median_gap_h = round(statistics.median(gaps_s) / 3600, 1) if gaps_s else 0.0

    best_i, best_s = 0, -1.0
    for i, g in enumerate(gaps_s):
        if g > best_s:
            best_i, best_s = i, g
    gap_from = times[best_i].date().isoformat() if gaps_s else None
    gap_to = times[best_i + 1].date().isoformat() if gaps_s else None

    per_day: Counter[str] = Counter(c.day.isoformat() for c in commits)
    burst = sum(1 for v in per_day.values() if v >= burst_threshold)
    return RhythmFacts(
        median_gap_h=median_gap_h,
        longest_gap_days=int(best_s // 86400) if gaps_s else 0,
        gap_from=gap_from,
        gap_to=gap_to,
        burst_days=burst,
    )


# ---------------------------------------------------------------------------
# R25 · 年度劳模文件


def top_files(commits: list[Commit], limit: int = 3) -> tuple[FileStat, ...]:
    touches: Counter[str] = Counter()
    lines: Counter[str] = Counter()
    for c in commits:
        for f in c.files:
            touches[f.path] += 1
            lines[f.path] += f.insertions + f.deletions
    ranked = sorted(touches, key=lambda p: (-touches[p], -lines[p], p))[:limit]
    return tuple(FileStat(path=p, touches=touches[p], lines=lines[p]) for p in ranked)


# ---------------------------------------------------------------------------
# R26 · 最常出没目录（路径首段）


def top_dirs(commits: list[Commit], limit: int = 5) -> tuple[DirStat, ...]:
    by_dir: Counter[str] = Counter()
    for c in commits:
        for f in c.files:
            name = f.path.split("/")[0] if "/" in f.path else "."
            by_dir[name] += f.insertions + f.deletions

    total = sum(by_dir.values())
    if total == 0:
        return ()
    ranked = sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return tuple(DirStat(name=n, lines=v, share=v / total) for n, v in ranked)


# ---------------------------------------------------------------------------
# R27 · 文件生杀簿（numstat 特征启发式：首秀纯增≈新建，谢幕纯删≈终结）


def file_life(commits: list[Commit]) -> FileLife:
    first_change: dict[str, tuple[int, int]] = {}
    last_change: dict[str, tuple[int, int]] = {}
    for c in sorted(commits, key=lambda c: c.author_time):
        for f in c.files:
            change = (f.insertions, f.deletions)
            first_change.setdefault(f.path, change)
            last_change[f.path] = change
    born = sum(1 for i, d in first_change.values() if i > 0 and d == 0)
    died = sum(1 for i, d in last_change.values() if i == 0 and d > 0)
    return FileLife(born=born, died=died)


# ---------------------------------------------------------------------------
# R28 · 删码率人设


def deletion_persona(commits: list[Commit]) -> DeleteRatio:
    ins = sum(c.insertions for c in commits)
    dels = sum(c.deletions for c in commits)
    total = ins + dels
    if total == 0:
        return DeleteRatio(ratio=0.0, persona="")
    ratio = dels / total
    persona = "清道夫" if ratio >= 0.35 else ("平衡型" if ratio >= 0.2 else "建造师")
    return DeleteRatio(ratio=ratio, persona=persona)


# ---------------------------------------------------------------------------
# R29 · 年度判词（聚合 R4/R20/R28）


def verdict(commits: list[Commit]) -> Verdict:
    if not commits:
        return Verdict(badges=(), text="")
    hp = hourly_profile(commits)
    tp = type_profile(commits)
    dp = deletion_persona(commits)
    badges = (hp.label, tp.persona, dp.persona)
    owl_pct = round(hp.owl_ratio * 100)
    del_pct = round(dp.ratio * 100)
    text = (
        f"你是「{hp.label}」的「{tp.persona}」，也是代码库的「{dp.persona}」。"
        f"这一年 {owl_pct}% 的提交发生在 0–6 点；每 100 行改动里有 {del_pct} 行是在做减法。"
        "新的一年，继续带着这份节奏写下去。"
    )
    return Verdict(badges=badges, text=text)
