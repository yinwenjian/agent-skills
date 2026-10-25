---
name: itra-runner-score
version: 1.3.2
icon: assets/icon.png
display_name: ITRA 跑者分数查询
display_name_en: ITRA Runner Score
description: Query a trail runner's ITRA Performance Index (ITRA 分数/积分/跑者等级) and full race history from itra.run by name or ITRA ID. This skill should be used when the user asks for someone's ITRA score, ITRA PI, trail-running world ranking, or "查一下某人的 ITRA 积分/越野跑世界排名", or wants a runner's race results from ITRA. Works without any login or API key.
description_zh: 按姓名或 ITRA ID 查询越野跑者的 ITRA 表现指数（PI）、跑者等级、世界/洲际/国家排名与完整完赛记录。零依赖、免登录、无需 API Key，直接抓取 itra.run 公开页面。
description_en: Look up a trail runner's ITRA Performance Index (PI), level, world/continent/country rankings and full race history by name or ITRA ID, scraped from itra.run public pages with no login, API key or third-party dependencies.
examples_zh:
  - 帮我查一下 Kilian Jornet 的 ITRA 分数
  - 我的 ITRA ID 是 123456，看看 PI 和世界排名
  - Kilian Jornet 和 Jim Walmsley 谁更强？对比一下 ITRA PI
examples_en:
  - Look up the ITRA score of Kilian Jornet
  - My ITRA ID is 123456, show my PI and world ranking
  - Who is stronger, Kilian Jornet or Jim Walmsley? Compare their ITRA PI
agent_created: true
---

# ITRA 跑者分数查询

## 用途

在 itra.run 上定位一名越野跑者，输出其 **ITRA 表现指数（PI）**与完整完赛记录。全程只走普通 HTTP，无需 API Key、无需登录，也不依赖任何第三方 Python 包。

## 何时使用

出现下列任一情况时触发本 skill：

- 询问某人的 ITRA 分数 / PI / Performance Index / ITRA 积分 / 世界排名
- "查一下 <姓名> 的 ITRA 分数"、"这个跑者 ITRA 多少分"、"他的越野跑世界排名"
- 需要某人的 ITRA 完赛记录、完赛积分或 ITRA 主页地址
- 对比两名及以上跑者的 ITRA 等级

不适用于：赛事报名、赛历查询，以及非 ITRA 体系（UTMB Index、Betrail 等）。

## 工作流程

1. **先判断输入形态。**
   - 含数字（ITRA ID 或 `itra.run/RunnerSpace/...` 主页链接）→ 直接跳到第 3 步。
   - 只有姓名 → 走第 2 步。
2. **按姓名搜索**，读候选列表。若返回多个可能人选，先把候选摊开、问清是哪一个再往下走；国籍或年龄段对不上时，不许静默取第一条。
3. **抓取档案**，输出 PI、等级、排名与完赛记录。
4. **用中文汇报**，数字原样照抄。不许估算 Performance Index，也不许编造单场 Race Score。

用自带脚本，不要自己重写抓取逻辑。

```bash
# 姓名 → 候选（含 PI），适合先消歧
python3 scripts/itra.py search "Example Runner" --country CZE --limit 10

# 姓名 → 自动取排序第一位 → 完整档案（最常用）
python3 scripts/itra.py report "Kilian Jornet" --races 20

# 已知 ITRA ID / 主页链接
python3 scripts/itra.py profile 123456 --races 50
python3 scripts/itra.py profile https://itra.run/RunnerSpace/example.runner.123456

# 机器可读
python3 scripts/itra.py report "向付召" --json
```

示例中的 `123456` 是虚构 ID，仅展示调用方式，运行时需替换为实际目标跑者 ID。

加 `--json` 输出结构化字段（`itra_id`、`pi`、`level`、`world_top`、`rankings`、`pi_by_category`、`stats`、`races[]`）；加 `--verbose` 逐个打印 HTTP 请求，用于排障。

退出码：`0` 成功，`1` 无匹配跑者，`2` 网络或反爬失败。

## 输出字段

| 字段 | 含义 |
|---|---|
| `pi` | 总 Performance Index，0–1000 —— **这才是人们通常说的「ITRA 分数」** |
| `level` | PI 段位（`Elite 1`、`Expert 4`、`Advanced 2`、`Intermediate 3` …） |
| `world_top` | 百分位，如 `0.55 %` 表示全世界前 0.55% |
| `rankings` | 世界 / 洲际 / 国家的总名次与总人数（年龄组拆分属订阅功能，取不到） |
| `pi_by_category` | 各距离组的 PI：10K / Half Marathon / Marathon / 50K / 50M / 100K / 100M / Endurance |
| `stats` | 完赛场次、总里程、总爬升、总用时 |
| `races[]` | 日期、赛事、组别、距离、爬升、用时、名次/人数、ITRA 完赛积分 |

## 硬性限制 —— 必须如实告知用户

1. **单场 Race Score 抓不到。** ITRA 把 Race Score 做成订阅功能，公开页面对未订阅者一律返回字面量 `DNF`（且所有 JSON 里 `score: 0`）。不许把完赛积分、`finisherLevel` 数字或任何猜测当成 Race Score 展示。用户若要单场分，明确告知需开通 ITRA 订阅账号，且本 skill 刻意不提供该列。
2. **ITRA 完赛积分（0–6）不是成绩分。** 它标注的是赛道难度，同一场比赛所有完赛者拿到的数字相同。展示它时必须说明这一点。
3. **积分只对近期比赛发布。** 跑者页只给最近几场带积分，更早的记录正常显示 `-`，不是数据缺失。
4. **姓名搜索只按名字匹配。** 常见姓名会命中大量跑者，必须让用户确认国籍或 ITRA ID，不许猜。
5. **中文名可以查，但库里存的是罗马化拼写。** 直接搜不到时改拼音重试（`向付召` → `Xiang Fuzhao`）。

## 脆弱点 —— 动手改之前先读

抓取依赖 itra.run 三个未公开的行为。`references/itra-endpoints.md` 记录了每一个的确切请求/响应形态：WAF 路径绕过、载荷 AES 解密、以及页内那两组成绩数组。改任何东西之前先读它 —— 对 URL 或加密逻辑做一次"清理"就会静默弄坏这个 skill。

ITRA 一旦改动其中任何一处，脚本会直接报错而不是返回错数据：

- `Blocked` —— 拿到反爬页而不是内容 → 向用户报告被拦，不要循环重试。
- `ItraError: 搜索页里找不到 antiforgery token` —— 页面结构变了 → 解析器需要对着线上页面更新。

保持默认请求节奏（两次请求间隔约 0.7 秒）。不要对 itra.run 并发请求。

## 文件

- `scripts/itra.py` —— 全部实现：HTTP 会话、antiforgery 引导、AES-CBC 解密、HTML/JSON 抽取、CLI。
- `references/itra-endpoints.md` —— 端点地图、鉴权与反爬说明、数据源怪癖，以及每个输出字段的出处。
- `assets/icon.png` —— 512×512 商店图标（圆角外透明）。`assets/icon.svg` 是可编辑源，重渲染用 headless Chrome：`--window-size=512,512 --default-background-color=00000000`，以保住透明圆角。
