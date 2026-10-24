"""报告的内联 CSS、JS、HTML 骨架常量（架构 D6/D7/D8，技术设计 §2.5）。

这是唯一"前端资产"存放地：
- 无任何外部资源引用（无外链 src/href、无 @import、无 CSS url(...)、无字体/图标 CDN）；
- 全部初始隐藏样式以 ``html.js`` 为前缀（渐进增强，D7）：禁用 JS 时内容完整可见；
- 三类动效（R8）：① 区块渐入上移（IntersectionObserver）、② 核心数字滚动增长
  （requestAnimationFrame）、③ 封面大标题滚动视差位移（原生 scroll +
  requestAnimationFrame + transform）。
"""

from __future__ import annotations

from string import Template

# ---------------------------------------------------------------------------
# 页面骨架（string.Template：$title / $styles / $body / $script）

HTML_SHELL = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
$styles
</style>
</head>
<body>
$body
<script>
$script
</script>
</body>
</html>
"""
)

# ---------------------------------------------------------------------------
# CSS：暗色沉浸式、分屏叙事；隐藏规则一律 html.js 前缀（D7）

STYLES = """
:root { color-scheme: dark; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  background: linear-gradient(180deg, #0b0e17 0%, #171130 55%, #0b0e17 100%);
  color: #e8e6f0;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
section.screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 72px 24px;
  position: relative;
}
.screen-title { font-size: clamp(24px, 4vw, 40px); font-weight: 700; }
.screen-desc { color: #9c97c0; margin: 10px 0 30px; font-size: 15px; }
.js .reveal {
  opacity: 0;
  transform: translateY(28px);
  transition: opacity .8s ease-out, transform .8s ease-out;
}
.js .reveal.visible { opacity: 1; transform: translateY(0); }

/* 封面 */
.cover-kicker {
  letter-spacing: .38em; color: #8f8ab3; font-size: 13px;
  margin-bottom: 20px; text-transform: uppercase;
}
.cover-title {
  font-size: clamp(38px, 9vw, 92px);
  font-weight: 800;
  line-height: 1.15;
  text-align: center;
  background: linear-gradient(120deg, #8be9fd, #bd93f9 55%, #ff79c6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  will-change: transform, opacity;
}
.cover-sub { margin-top: 24px; color: #9c97c0; font-size: 16px; }

/* 年度总览：大数字 */
.num-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 24px;
  width: min(880px, 92vw);
}
.num-card {
  text-align: center; padding: 26px 12px;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 16px;
  background: rgba(255,255,255,.03);
}
.num {
  font-size: clamp(30px, 5vw, 52px);
  font-weight: 800;
  color: #8be9fd;
  font-variant-numeric: tabular-nums;
}
.num.neg { color: #ff79c6; }
.num-label { margin-top: 8px; color: #9c97c0; font-size: 14px; }

/* 时段分布：24 小时柱状图 */
.hour-chart {
  display: flex; align-items: flex-end; gap: 4px;
  width: min(880px, 92vw); height: 230px;
}
.hour-col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
.hour-bar {
  width: 100%; min-height: 2px;
  background: linear-gradient(180deg, #bd93f9, #8be9fd);
  border-radius: 3px 3px 0 0;
}
.hour-tick { text-align: center; color: #7a749d; font-size: 10px; margin-top: 6px; }
.persona { margin-top: 34px; text-align: center; }
.persona-tag {
  display: inline-block; padding: 10px 26px;
  border-radius: 999px; border: 1px solid rgba(189,147,249,.55);
  color: #bd93f9; font-size: 19px; font-weight: 600;
}
.persona-peak { margin-top: 14px; color: #c8c4de; font-size: 16px; }
.owl-note { margin-top: 8px; color: #7a749d; font-size: 13px; }

/* 星期分布（R15）：7 柱 */
.week-chart {
  display: flex; align-items: flex-end; gap: 10px;
  width: min(560px, 92vw); height: 200px;
}
.week-col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
.week-bar {
  width: 100%; min-height: 2px;
  background: linear-gradient(180deg, #50fa7b, #8be9fd);
  border-radius: 3px 3px 0 0;
}

/* 全年逐日热力图（R17） */
.heat-scroll {
  width: min(880px, 92vw);
  display: flex; gap: 4px; align-items: flex-start;
}
.heat-col { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.heat-month { text-align: center; color: #7a749d; font-size: 10px; margin-bottom: 6px; }
.heat-cell { aspect-ratio: 1; width: 100%; border-radius: 2px; background: rgba(255,255,255,.05); }
.heat-1 { background: rgba(139,233,253,.22); }
.heat-2 { background: rgba(139,233,253,.42); }
.heat-3 { background: rgba(139,233,253,.65); }
.heat-4 { background: #8be9fd; }
.heat-note { margin-top: 14px; color: #7a749d; font-size: 13px; }

/* 技术栈构成（R16） */
.ft-rows { width: min(760px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.ft-row {
  display: grid; grid-template-columns: 110px 1fr 128px;
  align-items: center; gap: 12px;
}
.ft-name { color: #d6d2ea; font-size: 14px; font-weight: 600; }
.ft-line {
  height: 10px; border-radius: 5px;
  background: rgba(255,255,255,.06); overflow: hidden;
}
.ft-line-fill { height: 100%; background: linear-gradient(90deg, #bd93f9, #ff79c6); }
.ft-meta {
  color: #9c97c0; font-size: 12px; text-align: right;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}

/* 极值里程碑（R18） */
.mile-grid {
  width: min(880px, 92vw);
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 18px;
}
.mile-card {
  padding: 22px 20px;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 16px; background: rgba(255,255,255,.03);
  text-align: center;
}
.mile-big {
  font-size: clamp(24px, 4vw, 40px); font-weight: 800; color: #50fa7b;
  font-variant-numeric: tabular-nums;
}
.mile-text { margin-top: 10px; color: #9c97c0; font-size: 13px; line-height: 1.6; word-break: break-all; }

/* 提交类型分布（R20）：复用 ft- 行结构 */
.type-fill { height: 100%; background: linear-gradient(90deg, #50fa7b, #8be9fd); }

/* 文风与深夜独白（R21/R22） */
.nd-wrap {
  width: min(760px, 92vw); display: flex; gap: 20px; margin-top: 30px;
}
.nd-col {
  flex: 1; padding: 20px 22px; border-radius: 14px;
  border: 1px solid rgba(255,255,255,.08);
}
.nd-col.night { border-color: rgba(189,147,249,.4); background: rgba(189,147,249,.06); }
.nd-col.day { border-color: rgba(139,233,253,.4); background: rgba(139,233,253,.06); }
.nd-title { font-size: 15px; font-weight: 700; color: #d6d2ea; margin-bottom: 12px; }
.nd-terms { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.nd-term { color: #c8c4de; font-size: 15px; }
.nd-count { color: #7a749d; font-size: 12px; margin-left: 4px; }

/* 劳模文件（R25） */
.file-rows { width: min(760px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.file-row {
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 12px;
  padding: 12px 16px;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 12px; background: rgba(255,255,255,.03);
}
.file-path { color: #d6d2ea; font-size: 14px; word-break: break-all; font-family: ui-monospace, Menlo, monospace; }
.file-meta { color: #9c97c0; font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.dir-block { margin-top: 28px; }

/* 年度判词（R29） */
.verdict-wrap { width: min(760px, 92vw); text-align: center; }
.verdict-badges { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.verdict-badge {
  padding: 12px 26px; border-radius: 999px;
  border: 1px solid rgba(255,121,198,.55);
  color: #ff79c6; font-size: 20px; font-weight: 700;
}
.verdict-text { margin-top: 28px; color: #c8c4de; font-size: 17px; line-height: 2; }

/* 逐月代码量 */
.month-rows { width: min(760px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.month-row {
  display: grid; grid-template-columns: 46px 1fr 118px;
  align-items: center; gap: 12px;
}
.month-name { color: #9c97c0; font-size: 13px; }
.month-bars { display: flex; flex-direction: column; gap: 3px; }
.mbar { height: 8px; border-radius: 4px; }
.mbar-ins { background: linear-gradient(90deg, #50fa7b, #8be9fd); }
.mbar-del { background: linear-gradient(90deg, #ff79c6, #bd93f9); }
.month-nums {
  color: #9c97c0; font-size: 12px; text-align: right;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}

/* 最活跃项目榜 */
.proj-rows { width: min(760px, 92vw); display: flex; flex-direction: column; gap: 12px; }
.proj-row {
  display: grid; grid-template-columns: 46px 1fr auto;
  align-items: center; gap: 14px; padding: 14px 18px;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 14px; background: rgba(255,255,255,.03);
}
.proj-row.champion {
  border-color: rgba(255,121,198,.6);
  background: rgba(255,121,198,.08);
}
.proj-rank { font-size: 22px; font-weight: 800; color: #7a749d; }
.champion .proj-rank { color: #ff79c6; }
.proj-name { font-size: 17px; font-weight: 600; word-break: break-all; }
.proj-line {
  margin-top: 8px; height: 6px; border-radius: 3px;
  background: rgba(255,255,255,.06); overflow: hidden;
}
.proj-line-fill { height: 100%; background: linear-gradient(90deg, #8be9fd, #bd93f9); }
.proj-meta { color: #9c97c0; font-size: 13px; text-align: right; }
.proj-share { color: #8be9fd; }

/* 关键词云 */
.kw-cloud {
  width: min(880px, 92vw); display: flex; flex-wrap: wrap;
  gap: 14px 20px; justify-content: center; align-items: baseline;
}
.kw { color: #d6d2ea; line-height: 1.25; word-break: break-all; }
.kw-top { color: #8be9fd; }

/* 时间线彩蛋 */
.story { width: min(760px, 92vw); display: flex; flex-direction: column; gap: 26px; }
.story-card {
  padding: 26px 30px;
  border-left: 3px solid #bd93f9;
  background: rgba(255,255,255,.03);
  border-radius: 0 16px 16px 0;
}
.story-big {
  font-size: clamp(26px, 4vw, 44px); font-weight: 800; color: #ff79c6;
  font-variant-numeric: tabular-nums;
}
.story-text { margin-top: 10px; color: #c8c4de; line-height: 1.7; }
.story-quote { color: #e8e6f0; }

/* 空态（R11） */
.empty-box { text-align: center; max-width: 560px; }
.empty-icon { font-size: 64px; }
.empty-text { margin-top: 18px; color: #c8c4de; font-size: 17px; line-height: 1.8; }
.empty-hint { margin-top: 8px; color: #7a749d; font-size: 14px; }

/* 尾屏 */
.screen-footer { color: #7a749d; font-size: 13px; text-align: center; }
.footer-line { margin-top: 8px; }
"""

# ---------------------------------------------------------------------------
# JS：三段职责（技术设计 §2.5）
# ① documentElement.classList.add('js')（渐进增强标记，D7）
# ② IntersectionObserver 渐入上移 + 大数字滚动（requestAnimationFrame）
# ③ 封面大标题滚动视差位移（原生 scroll + requestAnimationFrame 节流）
# 无 IntersectionObserver 的旧浏览器整体降级为静态展示（内容完整可见）。

SCRIPT = """
document.documentElement.classList.add('js');

(function () {
  'use strict';

  function animateNumber(el) {
    var target = parseInt(el.getAttribute('data-target'), 10) || 0;
    var duration = 1400;
    var started = null;
    el.textContent = '0';
    function frame(ts) {
      if (started === null) { started = ts; }
      var p = Math.min((ts - started) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) { requestAnimationFrame(frame); }
    }
    requestAnimationFrame(frame);
  }

  var reveals = document.querySelectorAll('.reveal');

  function revealAll(nodes) {
    for (var i = 0; i < nodes.length; i++) { nodes[i].classList.add('visible'); }
  }

  if (!('IntersectionObserver' in window)) {
    revealAll(reveals);
  } else {
    var ioSilent = true;  // 保险丝：IO 构造器存在却从不派发回调的异常环境
    var io = new IntersectionObserver(function (entries) {
      ioSilent = false;
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        var box = entry.target;
        box.classList.add('visible');
        io.unobserve(box);
        var nums = box.querySelectorAll('.num');
        for (var j = 0; j < nums.length; j++) { animateNumber(nums[j]); }
      });
    }, { threshold: 0.25 });
    for (var k = 0; k < reveals.length; k++) { io.observe(reveals[k]); }
    // 保险丝兜底：IO 一直沉默时降级为静态展示（内容完整可见优先，同 D7 原则）。
    function ioFuse() {
      if (!ioSilent) { return; }
      revealAll(reveals);
    }
    window.addEventListener('scroll', ioFuse, { passive: true });
    setTimeout(ioFuse, 1200);
  }

  var coverBox = document.querySelector('.screen-cover');
  var coverTitle = document.querySelector('.cover-title');
  if (coverBox && coverTitle) {
    var ticking = false;
    function parallax() {
      var rect = coverBox.getBoundingClientRect();
      var vh = window.innerHeight || rect.height || 1;
      var progress = Math.min(Math.max(-rect.top / vh, 0), 1);
      var shift = progress * 0.32 * rect.height;
      coverTitle.style.transform = 'translateY(' + (-shift).toFixed(1) + 'px)';
      coverTitle.style.opacity = String(Math.max(1 - progress * 1.15, 0));
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (ticking) { return; }
      ticking = true;
      requestAnimationFrame(parallax);
    }, { passive: true });
    parallax();
  }
})();
"""

# ---------------------------------------------------------------------------
# 各屏模板（string.Template；用户数据由 render 层 html.escape 后代入，D8）

SECTION_COVER = Template(
    """<section class="screen screen-cover reveal">
  <div class="cover-kicker">Annual Code Report</div>
  <h1 class="cover-title">$year · 我的代码年度报告</h1>
  <p class="cover-sub">数据来源：$source_label</p>
</section>"""
)

SECTION_OVERVIEW = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">$year 年度总览</h2>
  <p class="screen-desc">一年下来，你的键盘留下了这些</p>
  <div class="num-grid">
    $cards
  </div>
</section>"""
)

NUM_CARD = Template(
    """<div class="num-card">
  <div class="num$neg" style="font-size:${size}px" data-target="$value">$value</div>
  <div class="num-label">$label</div>
</div>"""
)

SECTION_HOURLY = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你最活跃的时段</h2>
  <p class="screen-desc">24 小时提交分布，按时区原样统计</p>
  <div class="hour-chart">
    $bars
  </div>
  <div class="persona">
    <div class="persona-tag">$label</div>
    <div class="persona-peak">$peak_desc</div>
    <div class="owl-note">夜猫子指数：$owl_pct（0:00–6:00 提交占比）</div>
  </div>
</section>"""
)

HOUR_COL = Template(
    """<div class="hour-col" title="$hour 点：$count 次">
  <div class="hour-bar" style="height:$pct%"></div>
  <div class="hour-tick">$hour</div>
</div>"""
)

SECTION_MONTHLY = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">逐月代码量</h2>
  <p class="screen-desc">绿色为新增行，粉色为删除行</p>
  <div class="month-rows">
    $rows
  </div>
</section>"""
)

MONTH_ROW = Template(
    """<div class="month-row">
  <div class="month-name">$name</div>
  <div class="month-bars">
    <div class="mbar mbar-ins" style="width:$ins_pct%"></div>
    <div class="mbar mbar-del" style="width:$del_pct%"></div>
  </div>
  <div class="month-nums">+$ins / -$del</div>
</div>"""
)

SECTION_PROJECTS = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">最活跃项目</h2>
  <p class="screen-desc">按提交数排序的 Top 榜</p>
  <div class="proj-rows">
    $rows
  </div>
</section>"""
)

PROJECT_ROW = Template(
    """<div class="proj-row$champ">
  <div class="proj-rank">$rank</div>
  <div>
    <div class="proj-name">$name</div>
    <div class="proj-line"><div class="proj-line-fill" style="width:$share_pct%"></div></div>
  </div>
  <div class="proj-meta">$commits 次提交 · $lines 行代码<br><span class="proj-share">占代码量 $share_pct%</span></div>
</div>"""
)

SECTION_KEYWORDS = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的高频关键词</h2>
  <p class="screen-desc">提交说明里出现最多的词</p>
  <div class="kw-cloud">
    $cloud
  </div>
</section>"""
)

KEYWORD_SPAN = Template('<span class="kw$top" style="font-size:${size}px">$term</span>')

SECTION_TIMELINE = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">时间线彩蛋</h2>
  <p class="screen-desc">属于你的两个小故事</p>
  <div class="story">
    <div class="story-card">
      <div class="story-big">$streak 天</div>
      <div class="story-text">你最长的连续提交纪录，从 $streak_anchor 开始</div>
    </div>
    <div class="story-card">
      <div class="story-big">$latest_time</div>
      <div class="story-text">你最晚的一次提交：<span class="story-quote">“$latest_subject”</span></div>
    </div>
  </div>
</section>"""
)

SECTION_HEATMAP = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你这一年的形状</h2>
  <p class="screen-desc">12 个月逐日提交热力图，越亮的日子越高产</p>
  <div class="heat-scroll">
    $cols
  </div>
  <div class="heat-note">全年单日最高 $max_count 次</div>
</section>"""
)

HEAT_COL = Template(
    """<div class="heat-col">
  <div class="heat-month">$month</div>
  $cells
</div>"""
)

HEAT_CELL = Template('<div class="heat-cell heat-$level" title="$title"></div>')

SECTION_WEEKDAY = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的一周</h2>
  <p class="screen-desc">周一到周日的提交分布</p>
  <div class="week-chart">
    $cols
  </div>
  <div class="persona">
    <div class="persona-tag">$peak_desc</div>
    <div class="owl-note">周末提交占比：$weekend_pct</div>
  </div>
</section>"""
)

WEEKDAY_COL = Template(
    """<div class="week-col" title="$name：$count 次">
  <div class="week-bar" style="height:$pct%"></div>
  <div class="hour-tick">$name</div>
</div>"""
)

SECTION_FILETYPES = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的技术栈构成</h2>
  <p class="screen-desc">按改动行数统计的语言占比</p>
  <div class="ft-rows">
    $rows
  </div>
</section>"""
)

FT_ROW = Template(
    """<div class="ft-row">
  <div class="ft-name">$name</div>
  <div class="ft-line"><div class="ft-line-fill" style="width:$share_pct%"></div></div>
  <div class="ft-meta">$lines 行 · $share_pct%</div>
</div>"""
)

SECTION_SUPERLATIVES = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">极值里程碑</h2>
  <p class="screen-desc">属于你的四个年度纪录</p>
  <div class="mile-grid">
    <div class="mile-card">
      <div class="mile-big">$busiest_count 次</div>
      <div class="mile-text">单日提交之王<br>$busiest_day</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$biggest_lines 行</div>
      <div class="mile-text">最大的一笔提交<br><span class="story-quote">“$biggest_subject”</span></div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$first_date</div>
      <div class="mile-text">年度第一击<br>$first_time，一切从这里开始</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">±$avg_lines 行</div>
      <div class="mile-text">平均每笔提交的改动量</div>
    </div>
  </div>
</section>"""
)

SECTION_TYPES = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">创造者，还是消防员？</h2>
  <p class="screen-desc">按 conventional commits 前缀统计的提交类型分布</p>
  <div class="ft-rows">
    $rows
  </div>
  <div class="persona">
    <div class="persona-tag">$persona</div>
    <div class="persona-peak">$feat_fix</div>
    <div class="owl-note">规范使用率：$conv_pct · 删码率 $del_pct（$del_persona）</div>
  </div>
</section>"""
)

TYPE_ROW = Template(
    """<div class="ft-row">
  <div class="ft-name">$name</div>
  <div class="ft-line"><div class="type-fill" style="width:$pct%"></div></div>
  <div class="ft-meta">$count 次</div>
</div>"""
)

SECTION_STYLE = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的提交文风与深夜独白</h2>
  <p class="screen-desc">说明长度与中英偏好，深夜 / 白天的关键词对照</p>
  <div class="mile-grid">
    <div class="mile-card">
      <div class="mile-big">$avg_len 字</div>
      <div class="mile-text">提交说明的平均长度</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$cn_pct</div>
      <div class="mile-text">说明里含中文的占比</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$longest_len 字</div>
      <div class="mile-text">最长的一条<br><span class="story-quote">“$longest”</span></div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$shortest_len 字</div>
      <div class="mile-text">最简短的一条<br><span class="story-quote">“$shortest”</span></div>
    </div>
  </div>
  <div class="nd-wrap">
    <div class="nd-col night">
      <div class="nd-title">深夜 0–6 点 · $night_count 次提交</div>
      <div class="nd-terms">
        $night_terms
      </div>
    </div>
    <div class="nd-col day">
      <div class="nd-title">白天 6–24 点 · $day_count 次提交</div>
      <div class="nd-terms">
        $day_terms
      </div>
    </div>
  </div>
</section>"""
)

ND_TERM = Template('<span class="nd-term">$term<span class="nd-count">×$count</span></span>')
ND_EMPTY = '<span class="nd-term">本年度没有记录</span>'

SECTION_DAYSTART = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的开工时间表</h2>
  <p class="screen-desc">每个活跃日第一次提交的时刻分布</p>
  <div class="hour-chart">
    $bars
  </div>
  <div class="persona">
    <div class="persona-tag">$peak_desc</div>
    <div class="owl-note">10 点前开工的日子占 $before_ten_pct，全年最早一次打卡 $earliest_time</div>
  </div>
</section>"""
)

DAYSTART_COL = Template(
    """<div class="hour-col" title="$hour 点开工：$count 天">
  <div class="hour-bar" style="height:$pct%"></div>
  <div class="hour-tick">$hour</div>
</div>"""
)

SECTION_RHYTHM = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你的提交节奏</h2>
  <p class="screen-desc">间隔、空窗与爆发</p>
  <div class="mile-grid">
    <div class="mile-card">
      <div class="mile-big">$median_h 小时</div>
      <div class="mile-text">两次提交之间的中位间隔</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$gap_days 天</div>
      <div class="mile-text">最长的连续空窗<br>$gap_from → $gap_to</div>
    </div>
    <div class="mile-card">
      <div class="mile-big">$burst_days 天</div>
      <div class="mile-text">单日 ≥10 次提交的爆发日</div>
    </div>
  </div>
</section>"""
)

SECTION_FILES = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">你最常出没的代码现场</h2>
  <p class="screen-desc">劳模文件、常驻目录与文件的生与死</p>
  <div class="file-rows">
    $files
  </div>
  <div class="ft-rows dir-block">
    $dirs
  </div>
  <div class="heat-note">这一年你新建了约 $born 个文件、亲手终结了约 $died 个文件（按 numstat 特征近似）</div>
</section>"""
)

FILE_ROW = Template(
    """<div class="file-row">
  <div class="file-path">$path</div>
  <div class="file-meta">$touches 次改动 · $lines 行</div>
</div>"""
)

SECTION_VERDICT = Template(
    """<section class="screen reveal">
  <h2 class="screen-title">年度判词</h2>
  <p class="screen-desc">把一年的数据念给你听</p>
  <div class="verdict-wrap">
    <div class="verdict-badges">
      $badges
    </div>
    <div class="verdict-text">$text</div>
  </div>
</section>"""
)

VERDICT_BADGE = Template('<span class="verdict-badge">$badge</span>')

SECTION_EMPTY = Template(
    """<section class="screen reveal">
  <div class="empty-box">
    <div class="empty-icon">🌙</div>
    <div class="empty-text">$year 年还没有留下任何提交记录。</div>
    <div class="empty-hint">换一个 --year 试试，或用 --demo 先看示例报告。</div>
  </div>
</section>"""
)

SECTION_FOOTER = Template(
    """<section class="screen screen-footer reveal">
  <div class="footer-line">生成于 <span class="gen-at">$generated_at</span></div>
  <div class="footer-line">个人年度报告生成器 annual-report v$version · 数据来源：$source_label</div>
  <div class="footer-line">本报告为自包含单文件，可离线打开与分享</div>
</section>"""
)
