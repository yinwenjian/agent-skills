"""核心数据结构（架构 §3）。

全部为 frozen dataclass：统计结果可直接比较相等——这是 R2「同一 seed
两次运行核心统计完全一致」断言的实现基础。本模块不依赖任何兄弟模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class FileChange:
    """一个提交中的一个文件变更（numstat 行）。"""

    path: str
    insertions: int  # numstat 为 '-'（二进制）时按 0 记（R1）
    deletions: int  # 同上


@dataclass(frozen=True)
class Commit:
    """一条结构化提交记录（gitlog 与 demo 的共同产物）。"""

    project: str  # 项目名：basename；同名冲突时附加路径标识消歧（D14）
    repo_path: str  # 仓库绝对路径，仅溯源/报错提示用
    sha: str
    author_name: str
    author_email: str
    author_time: datetime  # fromisoformat(%aI)，保留原始 tzinfo，绝不转 UTC（R10）
    subject: str
    files: tuple[FileChange, ...] = ()

    @property
    def insertions(self) -> int:
        return sum(f.insertions for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def hour(self) -> int:
        """原始时区小时（R4/R10），不做 UTC 归一。"""
        return self.author_time.hour

    @property
    def month(self) -> int:
        """1–12，原始时区月份。"""
        return self.author_time.month

    @property
    def day(self) -> date:
        """原始时区日期（活跃天 / streak 用）。"""
        return self.author_time.date()


@dataclass(frozen=True)
class Overview:
    """年度总览（R3）。"""

    total_commits: int
    insertions: int
    deletions: int
    net_lines: int  # insertions - deletions
    active_days: int  # 去重日期数
    project_count: int  # 按消歧后项目名去重的个数（D14 / PRD v1.2）


@dataclass(frozen=True)
class MonthLines:
    """逐月代码量（12 个月条形对比）。"""

    month: int  # 1–12
    insertions: int
    deletions: int


@dataclass(frozen=True)
class HourlyProfile:
    """24 小时提交分布（R4）。"""

    bins: tuple[int, ...]  # 恒为 24 项，bins[h] = h 时提交数；总和恒等于 total_commits
    owl_ratio: float  # 0.0–1.0，bins[0..5] 之和 / total_commits；total=0 时为 0.0
    label: str  # 人格化标签；空数据为 ""
    peak_desc: str  # 如「22:00–01:00 是你的主场」；空数据为 ""


@dataclass(frozen=True)
class ProjectStat:
    """最活跃项目榜中的一行（R5）。"""

    name: str
    commits: int
    lines: int  # 该项目 insertions + deletions
    share: float  # lines / 全部项目 lines 之和（按截断前全量计算）；总量为 0 时为 0.0


@dataclass(frozen=True)
class KeywordStat:
    """高频关键词中的一条（R6）。"""

    term: str
    count: int


@dataclass(frozen=True)
class TimelineFacts:
    """时间线彩蛋（PRD 2.3）。"""

    longest_streak: int  # 最长连续提交天数；无提交为 0
    streak_anchor: str | None  # 最长连续段首日 "YYYY-MM-DD"；无提交为 None
    latest: Commit | None  # 按 author_time（绝对时刻）最大的提交；无提交为 None


@dataclass(frozen=True)
class WeekdayProfile:
    """星期分布（R15）。"""

    bins: tuple[int, ...]  # 恒为 7 项，bins[0]=周一 … bins[6]=周日；总和恒等于 total_commits
    weekend_ratio: float  # 0.0–1.0，(周六+周日)/总提交数；无提交为 0.0
    peak_desc: str  # 「周三是你的爆发日」；空数据为 ""


@dataclass(frozen=True)
class FiletypeStat:
    """技术栈构成榜中的一行（R16）。"""

    name: str  # 语言名（映射后），未映射聚合行为「其他」
    lines: int  # 该语言 insertions + deletions
    share: float  # lines / 全部改动行数；总量为 0 时为 0.0


@dataclass(frozen=True)
class DayCell:
    """热力图中的一个日历格（R17）。"""

    date: str  # "YYYY-MM-DD"
    count: int  # 当日提交数
    level: int  # 0–4；0 次=0 档，非零日至少 1 档


@dataclass(frozen=True)
class DailyHeatmap:
    """全年逐日提交热力图（R17）。"""

    cells: tuple[DayCell, ...]  # 覆盖该年全部日期（按日期升序），空档日 count=0
    max_count: int  # 全年单日最大提交数（分档基准）；无提交为 0


@dataclass(frozen=True)
class Superlatives:
    """极值里程碑（R18）。"""

    busiest_day: str | None  # 单日提交之王 "YYYY-MM-DD"；无提交为 None
    busiest_count: int
    biggest_subject: str | None  # 最大一笔提交的说明；无提交为 None
    biggest_lines: int  # 该笔 insertions + deletions
    first: Commit | None  # 按作者时间绝对时刻最早的提交；无提交为 None
    avg_lines: int  # 总改动行数 / 总提交数，四舍五入；无提交为 0


@dataclass(frozen=True)
class TypeProfile:
    """提交类型分布与人设（R20）。"""

    bins: tuple[tuple[str, int], ...]  # (前缀, 次数) 按次数降序、同值名称字典序升序
    convention_rate: float  # 带 conventional 前缀的提交 ÷ 总提交数
    feat_fix_ratio: float  # feat / (feat + fix)；两者皆 0 时为 0.0
    persona: str  # 创造者 / 消防员 / 平衡手 / 未知型；空数据为 ""


@dataclass(frozen=True)
class SubjectStyle:
    """提交说明文风（R21）。"""

    avg_len: int  # 平均字符数，四舍五入；无提交为 0
    cn_ratio: float  # 含汉字说明占比；无提交为 0.0
    longest: str | None  # 最长说明（并列取 sha 字典序最小）；无提交为 None
    shortest: str | None  # 最短说明（并列取 sha 字典序最小）；无提交为 None


@dataclass(frozen=True)
class NightDayKeywords:
    """深夜与白天的关键词对照（R22）。"""

    night_count: int  # 0–5 时提交数
    day_count: int  # 6–23 时提交数
    night_terms: tuple[KeywordStat, ...]  # 深夜 Top N，已按 R6 口径排序
    day_terms: tuple[KeywordStat, ...]  # 白天 Top N


@dataclass(frozen=True)
class DayStart:
    """开工时间表（R23）。"""

    bins: tuple[int, ...]  # 恒 24 项：各活跃日最早提交小时的分布；桶和 = 活跃天数
    before_ten: float  # 10 点前开工的活跃日占比
    earliest_time: str  # 全年最早打卡 "HH:MM"；空数据为 ""
    peak_desc: str  # 「开工高峰 10:00」；空数据为 ""


@dataclass(frozen=True)
class RhythmFacts:
    """提交节奏（R24）。"""

    median_gap_h: float  # 相邻提交间隔中位数（小时，1 位小数）；不足 2 条为 0.0
    longest_gap_days: int  # 最长空窗天数（下取整）
    gap_from: str | None  # 空窗起始日 "YYYY-MM-DD"（空窗前最后提交日）；无提交为 None
    gap_to: str | None  # 空窗结束日（空窗后首个提交日）
    burst_days: int  # 单日提交 ≥ 10 次的天数


@dataclass(frozen=True)
class FileStat:
    """年度劳模文件榜中的一行（R25）。"""

    path: str
    touches: int  # 被改动次数（按提交计）
    lines: int  # 累计改动行数


@dataclass(frozen=True)
class DirStat:
    """最常出没目录榜中的一行（R26）。"""

    name: str  # 路径首段；根级文件为 "."
    lines: int
    share: float  # lines / 全部改动行数；总量为 0 时为 0.0


@dataclass(frozen=True)
class FileLife:
    """文件生杀簿（R27，numstat 特征启发式）。"""

    born: int  # 首秀纯增（ins>0 且 del=0）的路径数 ≈ 新建
    died: int  # 谢幕纯删（ins=0 且 del>0）的路径数 ≈ 终结


@dataclass(frozen=True)
class DeleteRatio:
    """删码率人设（R28）。"""

    ratio: float  # 删除行 / 总改动行
    persona: str  # 清道夫 / 平衡型 / 建造师；无行数变更或空数据为 ""


@dataclass(frozen=True)
class Verdict:
    """年度判词（R29）。"""

    badges: tuple[str, ...]  # 三枚徽章：时段标签 × 类型人设 × 删码人设
    text: str  # 确定性判词；空数据为 ""


@dataclass(frozen=True)
class ReportData:
    """渲染层唯一输入。"""

    year: int
    source: str  # "git" | "demo"（尾页数据来源标识）
    generated_at: datetime  # 渲染时刻本地时间，仅展示用（不参与确定性断言）
    overview: Overview
    months: tuple[MonthLines, ...]  # 恒为 12 项（1–12 月，缺数据为 0）
    hourly: HourlyProfile
    projects: tuple[ProjectStat, ...]  # 已按 commits 降序排好
    keywords: tuple[KeywordStat, ...]  # 已按 count 降序排好
    timeline: TimelineFacts
    weekday: WeekdayProfile
    filetypes: tuple[FiletypeStat, ...]  # 已按 lines 降序排好，末行为「其他」（仅当有归入时）
    heatmap: DailyHeatmap
    superlatives: Superlatives
    type_profile: TypeProfile
    subject_style: SubjectStyle
    night_day: NightDayKeywords
    day_start: DayStart
    rhythm: RhythmFacts
    hot_files: tuple[FileStat, ...]  # 劳模文件 Top 3
    hot_dirs: tuple[DirStat, ...]  # 最常出没目录 Top 5
    file_life: FileLife
    delete_ratio: DeleteRatio
    verdict: Verdict
    is_empty: bool  # commits 为空时 True，触发空态渲染（R11）
