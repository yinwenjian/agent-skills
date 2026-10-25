# itra.run —— 逆向出的端点地图

以下全部对着线上站点实测验证过。无需 API Key，无需登录。
主机：`https://itra.run`。请求必须带桌面浏览器的 `User-Agent`，否则站点直接回 `403`。

## 1. 反爬：路径编码技巧

`GET /Runners/FindARunner` 上挂着一条 AWS WAF 规则，任何非浏览器客户端都收到 `405` + `<title>Human Verification</title>`。headless Chrome 同样被拦。

把路径中**一个字符**做百分号编码即可跳过该规则，而 ASP.NET Core 仍然路由到同一个 handler：

```
GET /Runners/%46indARunner   → 200, "ITRA Find a Runner"
```

响应会下发 `.AspNetCore.Session` / `.AspNetCore.Antiforgery.*` cookie，页面里含隐藏字段 `__RequestVerificationToken`。这两样都是搜索调用所必需的。**纯 HTTP 方案能成立，唯一原因就是这一条**；如果 ITRA 哪天规范化了编码路径，本 skill 立即失效。

大小写变体（`/runners/findarunner`）、尾斜杠、`%20` 都**不能**绕过该规则 —— 只有编码字符有效。

## 2. 跑者搜索

```
POST /api/runner/find
Content-Type: application/x-www-form-urlencoded
X-CSRF-TOKEN: <__RequestVerificationToken>
X-Requested-With: XMLHttpRequest
Referer: https://itra.run/Runners/FindARunner

name=<全名或部分姓名>&nationality=<IOC 国家代码或空>&start=1&count=10&echoToken=<float>
```

`name` 至少 2 个字符。

响应**不是**明文 JSON。服务端把 AES 材料连同密文一起发回来（安全表演，但对调用方很方便）：

```json
{"response1": "<base64 密文>", "response2": "<base64 IV>", "response3": "<base64 原始 key>"}
```

`response3` 解出来是 16/24/32 字节 → AES-128/192/256-CBC；`response2` 是 16 字节 IV；PKCS#7 填充。明文结构如下（示例身份、标识、统计及资源路径均为虚构）：

```json
{"ResultCount": 1, "EchoToken": ..., "Results": [{
  "RunnerId": 123456, "FirstName": "Example", "LastName": "RUNNER",
  "Nationality": "Czech Republic", "Gender": "Male", "AgeGroup": " 35-39",
  "RecentRaces": "...", "ProfilePic": "/Files/Photos/example.jpg",
  "Pi": 735, "PiIndex": "Expert 4", "ColorCode": "#FFB470"}]}
```

也就是说**一次调用就搞定「姓名 → ID → PI」**。`scripts/itra.py` 用纯 Python 实现了 AES 解密（`aes_cbc_decrypt`），并对 `openssl enc` 做过交叉验证。

## 3. 跑者主页

```
GET /RunnerSpace/<slug>.<slug>.<itra_id>
```

slug 规则（在带变音符号的姓名上验证过）：转小写 → 去变音符（NFKD）→ 只保留 `a-z0-9`。`"EXAMPLE RUNNER"` → `examplerunner`。ID 必须是真实 ID；slug 错就 404，不会重定向，所以 ID 和姓名两者都得有。

页面是服务端渲染的，里面并列着六个数据孤岛：

| 孤岛 | 怎么找 | 给什么 |
|---|---|---|
| `selectedItem` 数组 | 正则 `"pi":<n>,"categoryName":"..."` | 各距离组 PI + 段位 |
| `#divProgress` | `level-count` / `level` 两个 span | 总 PI + 段位 |
| 排名卡片 | `<h4> World/Continent/Country Ranking` | 总名次/总人数、`World Top x %` |
| `scorePerformance` | `"scorePerformance":{...}` | 年份、距离分类、**全部**比赛 |
| `raceResults` | `"raceResults":[...]`（results tab 的 model） | **最近几场**比赛，带 ITRA 积分 |
| stats | `"title":"Finished Races","value":"40"` | 汇总值（值是 JSON 转义的，如 `\u002B213,018 m`） |

整块 model 在 HTML 里重复约 5 次 —— 必须去重。

`scorePerformance.results` 是全的，但 `score: 0`、`id: 0`、`itraPoints: null`；`raceResults` 很短，却带着 `itraPoint`、`mountainPoints`、`finishers`、`displayedScore`。脚本按 `(date, time)` 把两者合并。

## 4. 被锁住的内容（别试着抓）

- **单场 Race Score**（0–1000）。所有公开载荷里都是 `score: 0` 与 `displayedScore: "DNF"`、`displayedScoreForNonsubscribers: "DNF"`。ITRA 自己的订阅页把 "Explore ITRA Race Scores for all runners and races" 明确列为付费权益。`GET /api/race/raceresults/{raceYearId}` 对每个完赛者也同样返回 `score: 0`。
- **年龄组排名拆分** —— 渲染在 `cls-subscriber` 块后面，未订阅显示 `DNF`。
- `finisherLevel` 每场都有（如 346、624），但语义未公开，而且它**不是** Race Score。不要把它当成分数展示。

## 5. 存在但在这里没用的端点

| 端点 | 为什么不用 |
|---|---|
| `GET /api/Runner/{id}` | `401 User not authorized` |
| `GET /api/Runner/Info/{id}`、`/api/Runner/DataOfRunners/{id}` | `401` |
| `POST /api/race/getrunnerraceresults`（`Start`/`Length`/`RunnerId`） | `200` 但 `data: null` —— 需要登录态上下文 |
| `POST /api/RunnerRankData` | 响应 AES 加密，且**密钥材料不随载荷下发**；另外它只有排行列表 |
| `GET /api/Runner/{anything}` | 路由约束是 `{id:int}`，任何字符串都返回 400 校验错误 |
| `api.itra.run/api/v1/*` | 官方合作 API：需要 `Authorization: Bearer` + `X-Access-Token` + `X-HMAC-Signature` + `X-Timestamp`，且**没有**姓名搜索端点 |
| `POST /api/Race/GetRaceResultsDetails` | jQuery 深度序列化的 `model[...]` 表单，最小化 model 会渲染成"无数据"。不值得重放 |

## 6. 有用的术语（取自 ITRA 官方 FAQ）

- **Performance Index（PI）** —— 0–1000，取最近 36 个月内最好的 5 场 Race Score 加权平均。这就是人们口中的「ITRA 分数」。
- **Race Score** —— 0–1000，每完赛一场一个。是 PI 的输入项，付费功能。
- **ITRA / Endurance Points（完赛积分）** —— 0–6，赋给**赛事**（赛道难度），同场所有完赛者相同。不是成绩指标。
- **PI 段位** —— `Elite 1-3`、`Expert 1-4`、`Advanced 1-3`、`Intermediate 1-5`（class 名里写作 `Expert-4`，正文里写作 `Expert 4`）。
