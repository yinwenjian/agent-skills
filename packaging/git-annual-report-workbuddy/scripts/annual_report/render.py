"""把 ReportData 组装成单文件 HTML 字符串（架构 D6/D7/D8，技术设计 §2.6）。

- 空态（is_empty=True）只渲染 封面 / 空态屏 / 尾屏，统计屏全部跳过（R11）；
- 所有来自用户数据的字符串（subject、项目名、关键词）经 ``html.escape``
  后再代入模板（D8）；提交说明中的 URL 文本按纯文本展示，不剥除、不生成
  链接元素（D8 的 R7 口径裁决）；
- 柱高、条宽、字号等按最大值归一为内联 style（无 JS 依赖即可见，D6/D7）；
- 不做任何文件 I/O（落盘归 CLI，便于单测直接断言字符串）。
"""

from __future__ import annotations

import html

from . import __version__
from . import assets
from .models import ReportData

_SOURCE_LABELS = {"git": "真实 git 数据", "demo": "示例数据"}

_KW_MIN_PX = 14
_KW_MAX_PX = 44

# 数字卡自适应字号：网格最窄列 150px − 左右 padding 24px − 边框 2px ≈ 124px 可用宽，
# 粗体等宽数字每位约占 0.62em，故 em 预算 ≈ 124 / 0.62 ≈ 200；按位数折算并夹紧。
_NUM_FIT_BUDGET = 200
_NUM_MAX_PX = 52
_NUM_MIN_PX = 20


def _sub(template, mapping: dict | None = None, **kwargs) -> str:
    """safe_substitute 不适用于本场景：缺占位符应当场暴露，用 substitute。"""
    values = dict(mapping or {})
    values.update(kwargs)
    return template.substitute(values)


def _num_font_px(*values: int) -> int:
    """同一组数字卡共用一个字号：按最长数字的位数折算，保证最窄列不溢出。"""
    digits = max(len(str(v)) for v in values)
    return max(_NUM_MIN_PX, min(_NUM_MAX_PX, round(_NUM_FIT_BUDGET / digits)))


def _num_card(value: int, label: str, size_px: int) -> str:
    return _sub(
        assets.NUM_CARD,
        value=str(value),
        label=label,
        size=size_px,
        neg=" neg" if value < 0 else "",
    )


def _overview_section(data: ReportData) -> str:
    ov = data.overview
    size = _num_font_px(
        ov.total_commits, ov.insertions, ov.deletions,
        ov.net_lines, ov.active_days, ov.project_count,
    )
    cards = "\n    ".join(
        [
            _num_card(ov.total_commits, "总提交数", size),
            _num_card(ov.insertions, "新增行数", size),
            _num_card(ov.deletions, "删除行数", size),
            _num_card(ov.net_lines, "净增行数", size),
            _num_card(ov.active_days, "活跃天数", size),
            _num_card(ov.project_count, "参与项目数", size),
        ]
    )
    return _sub(assets.SECTION_OVERVIEW, year=data.year, cards=cards)


def _hourly_section(data: ReportData) -> str:
    hourly = data.hourly
    max_count = max(hourly.bins)
    cols = []
    for hour, count in enumerate(hourly.bins):
        pct = round(count / max_count * 100) if max_count > 0 else 0
        cols.append(
            _sub(assets.HOUR_COL, hour=str(hour), count=str(count), pct=str(pct))
        )
    bars = "\n    ".join(cols)
    return _sub(
        assets.SECTION_HOURLY,
        bars=bars,
        label=html.escape(hourly.label),
        peak_desc=html.escape(hourly.peak_desc),
        owl_pct=f"{round(hourly.owl_ratio * 100)}%",
    )


def _monthly_section(data: ReportData) -> str:
    max_lines = max(max(m.insertions, m.deletions) for m in data.months)
    rows = []
    for m in data.months:
        ins_pct = round(m.insertions / max_lines * 100) if max_lines > 0 else 0
        del_pct = round(m.deletions / max_lines * 100) if max_lines > 0 else 0
        rows.append(
            _sub(
                assets.MONTH_ROW,
                {
                    "name": f"{m.month}月",
                    "ins_pct": str(ins_pct),
                    "del_pct": str(del_pct),
                    "ins": str(m.insertions),
                    "del": str(m.deletions),
                },
            )
        )
    return _sub(assets.SECTION_MONTHLY, rows="\n    ".join(rows))


def _projects_section(data: ReportData) -> str:
    rows = []
    for rank, p in enumerate(data.projects, start=1):
        share_pct = round(p.share * 100)
        rows.append(
            _sub(
                assets.PROJECT_ROW,
                champ=" champion" if rank == 1 else "",
                rank=str(rank),
                name=html.escape(p.name),
                commits=str(p.commits),
                lines=str(p.lines),
                share_pct=str(share_pct),
            )
        )
    return _sub(assets.SECTION_PROJECTS, rows="\n    ".join(rows))


def _keywords_section(data: ReportData) -> str:
    counts = [k.count for k in data.keywords]
    spans = []
    for idx, k in enumerate(data.keywords):
        if not counts:
            size = (_KW_MIN_PX + _KW_MAX_PX) // 2
        elif max(counts) == min(counts):
            size = (_KW_MIN_PX + _KW_MAX_PX) // 2
        else:
            ratio = (k.count - min(counts)) / (max(counts) - min(counts))
            size = round(_KW_MIN_PX + ratio * (_KW_MAX_PX - _KW_MIN_PX))
        spans.append(
            _sub(
                assets.KEYWORD_SPAN,
                top=" kw-top" if idx < 3 else "",
                size=str(size),
                term=html.escape(k.term),
            )
        )
    return _sub(assets.SECTION_KEYWORDS, cloud="\n    ".join(spans))


def _timeline_section(data: ReportData) -> str:
    tl = data.timeline
    assert tl.latest is not None and tl.streak_anchor is not None  # 非空数据不变式
    return _sub(
        assets.SECTION_TIMELINE,
        streak=str(tl.longest_streak),
        streak_anchor=html.escape(tl.streak_anchor),
        latest_time=tl.latest.author_time.strftime("%H:%M"),
        latest_subject=html.escape(tl.latest.subject),
    )


def _heatmap_section(data: ReportData) -> str:
    hm = data.heatmap
    by_month: dict[int, list[str]] = {m: [] for m in range(1, 13)}
    for cell in hm.cells:
        month = int(cell.date[5:7])
        day = int(cell.date[8:10])
        by_month[month].append(
            _sub(assets.HEAT_CELL, level=str(cell.level), title=f"{month}月{day}日：{cell.count} 次")
        )
    cols = "\n    ".join(
        _sub(assets.HEAT_COL, month=f"{m}月", cells="\n    ".join(by_month[m]))
        for m in range(1, 13)
    )
    return _sub(assets.SECTION_HEATMAP, cols=cols, max_count=str(hm.max_count))


_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _weekday_section(data: ReportData) -> str:
    w = data.weekday
    peak = max(w.bins) if w.bins else 0
    cols = "\n    ".join(
        _sub(
            assets.WEEKDAY_COL,
            name=name,
            count=str(count),
            pct=str(round(count / peak * 100) if peak > 0 else 0),
        )
        for name, count in zip(_WEEKDAY_NAMES, w.bins)
    )
    return _sub(
        assets.SECTION_WEEKDAY,
        cols=cols,
        peak_desc=html.escape(w.peak_desc),
        weekend_pct=f"{round(w.weekend_ratio * 100)}%",
    )


def _filetypes_section(data: ReportData) -> str:
    rows = "\n    ".join(
        _sub(
            assets.FT_ROW,
            name=html.escape(f.name),
            lines=str(f.lines),
            share_pct=str(round(f.share * 100)),
        )
        for f in data.filetypes
    )
    return _sub(assets.SECTION_FILETYPES, rows=rows)


def _superlatives_section(data: ReportData) -> str:
    s = data.superlatives
    assert s.first is not None and s.busiest_day is not None and s.biggest_subject is not None
    return _sub(
        assets.SECTION_SUPERLATIVES,
        busiest_count=str(s.busiest_count),
        busiest_day=html.escape(s.busiest_day),
        biggest_lines=str(s.biggest_lines),
        biggest_subject=html.escape(s.biggest_subject),
        first_date=s.first.author_time.strftime("%m-%d"),
        first_time=s.first.author_time.strftime("%H:%M"),
        avg_lines=str(s.avg_lines),
    )


def _types_section(data: ReportData) -> str:
    tp = data.type_profile
    peak = tp.bins[0][1] if tp.bins else 0
    rows = "\n    ".join(
        _sub(
            assets.TYPE_ROW,
            name=html.escape(name),
            count=str(count),
            pct=str(round(count / peak * 100) if peak > 0 else 0),
        )
        for name, count in tp.bins
    )
    del_pct = f"{round(data.delete_ratio.ratio * 100)}%"
    return _sub(
        assets.SECTION_TYPES,
        rows=rows,
        persona=html.escape(tp.persona),
        feat_fix=f"在 feat 与 fix 之中，feat 占 {tp.feat_fix_ratio:.0%}" if tp.feat_fix_ratio else "本年没有 feat / fix 提交",
        conv_pct=f"{round(tp.convention_rate * 100)}%",
        del_pct=del_pct,
        del_persona=html.escape(data.delete_ratio.persona or "无改动"),
    )


def _style_section(data: ReportData) -> str:
    st = data.subject_style
    nd = data.night_day
    assert st.longest is not None and st.shortest is not None

    def terms(items) -> str:
        if not items:
            return assets.ND_EMPTY
        return "\n        ".join(
            _sub(assets.ND_TERM, term=html.escape(t.term), count=str(t.count)) for t in items
        )

    return _sub(
        assets.SECTION_STYLE,
        avg_len=str(st.avg_len),
        cn_pct=f"{round(st.cn_ratio * 100)}%",
        longest_len=str(len(st.longest)),
        longest=html.escape(st.longest),
        shortest_len=str(len(st.shortest)),
        shortest=html.escape(st.shortest),
        night_count=str(nd.night_count),
        day_count=str(nd.day_count),
        night_terms=terms(nd.night_terms),
        day_terms=terms(nd.day_terms),
    )


def _daystart_section(data: ReportData) -> str:
    ds = data.day_start
    peak = max(ds.bins) if ds.bins else 0
    bars = "\n    ".join(
        _sub(
            assets.DAYSTART_COL,
            hour=str(hour),
            count=str(count),
            pct=str(round(count / peak * 100) if peak > 0 else 0),
        )
        for hour, count in enumerate(ds.bins)
    )
    return _sub(
        assets.SECTION_DAYSTART,
        bars=bars,
        peak_desc=html.escape(ds.peak_desc),
        before_ten_pct=f"{round(ds.before_ten * 100)}%",
        earliest_time=html.escape(ds.earliest_time or "—"),
    )


def _rhythm_section(data: ReportData) -> str:
    r = data.rhythm
    return _sub(
        assets.SECTION_RHYTHM,
        median_h=f"{r.median_gap_h:g}",
        gap_days=str(r.longest_gap_days),
        gap_from=html.escape(r.gap_from or "——"),
        gap_to=html.escape(r.gap_to or "——"),
        burst_days=str(r.burst_days),
    )


def _files_section(data: ReportData) -> str:
    files = "\n    ".join(
        _sub(
            assets.FILE_ROW,
            path=html.escape(f.path),
            touches=str(f.touches),
            lines=str(f.lines),
        )
        for f in data.hot_files
    )
    dirs = "\n    ".join(
        _sub(
            assets.FT_ROW,
            name=html.escape(d.name),
            lines=str(d.lines),
            share_pct=str(round(d.share * 100)),
        )
        for d in data.hot_dirs
    )
    return _sub(
        assets.SECTION_FILES,
        files=files,
        dirs=dirs,
        born=str(data.file_life.born),
        died=str(data.file_life.died),
    )


def _verdict_section(data: ReportData) -> str:
    badges = "\n      ".join(
        _sub(assets.VERDICT_BADGE, badge=html.escape(b)) for b in data.verdict.badges
    )
    return _sub(assets.SECTION_VERDICT, badges=badges, text=html.escape(data.verdict.text))


def render_report(data: ReportData) -> str:
    """渲染完整单文件 HTML（R7/R8/R11）。"""
    source_label = _SOURCE_LABELS.get(data.source, data.source)

    sections = [
        _sub(
            assets.SECTION_COVER,
            year=str(data.year),
            source_label=html.escape(source_label),
        )
    ]
    if data.is_empty:
        sections.append(_sub(assets.SECTION_EMPTY, year=str(data.year)))
    else:
        sections.append(_overview_section(data))
        sections.append(_heatmap_section(data))
        sections.append(_hourly_section(data))
        sections.append(_weekday_section(data))
        sections.append(_monthly_section(data))
        sections.append(_projects_section(data))
        if data.filetypes:  # R16：无文件变更（行数全 0）时整区不渲染
            sections.append(_filetypes_section(data))
        sections.append(_keywords_section(data))
        sections.append(_timeline_section(data))
        sections.append(_superlatives_section(data))
        sections.append(_types_section(data))
        sections.append(_style_section(data))
        sections.append(_daystart_section(data))
        sections.append(_rhythm_section(data))
        if data.hot_files or data.hot_dirs:  # R25–R27：无文件变更时整区不渲染
            sections.append(_files_section(data))
        sections.append(_verdict_section(data))
    sections.append(
        _sub(
            assets.SECTION_FOOTER,
            generated_at=data.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
            version=__version__,
            source_label=html.escape(source_label),
        )
    )

    return _sub(
        assets.HTML_SHELL,
        title=f"{data.year} · 我的代码年度报告",
        styles=assets.STYLES,
        body="\n".join(sections),
        script=assets.SCRIPT,
    )
