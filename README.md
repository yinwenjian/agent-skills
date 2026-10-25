# agent-skills

我个人维护的 Agent Skill 仓库，收录从实际工作中提炼、可复用的技能与工具。每个技能独立维护，按需安装；优先把一个明确的任务做得可靠，再逐步扩充。

## 技能目录

| 技能 | 用途 | 运行要求 |
| --- | --- | --- |
| [git-annual-report](skills/git-annual-report/SKILL.md) | 将本地 Git 提交历史生成可离线分享的 HTML 年度报告 | macOS / Linux、Python 3.10+、Git |
| [itra-runner-score](skills/itra-runner-score/SKILL.md) | 按姓名或 ITRA ID 查询越野跑者 PI、排名与完赛记录 | Python 3，需联网访问 itra.run；详见技能说明 |

通过 [skills.sh](https://skills.sh) 按需安装。具体触发方式、依赖与限制，以各技能的 `SKILL.md` 为准。

### 安装

```bash
npx skills add yinwenjian/agent-skills -l                      # 先列出仓库里有哪些 skill
npx skills add yinwenjian/agent-skills -s itra-runner-score    # 只装指定的一个（-s 可重复）
npx skills add yinwenjian/agent-skills                         # 交互式勾选
npx skills add yinwenjian/agent-skills -y                      # 全装，跳过询问
```

> 仓库里只有 1 个 skill 时 CLI 会直接装；有多个时会弹多选清单。只想临时用、不安装，可用 `npx skills use yinwenjian/agent-skills@itra-runner-score` 生成一段提示。

## git代码提交年度报告生成器（git-annual-report）

![icon](skills/git-annual-report/icon.png)

把本地 git 仓库的提交历史变成一份「网易云年报」风格的单文件离线 HTML 年度报告：年度总览、全年逐日热力图、24 小时与星期分布、逐月代码量、最活跃项目、技术栈构成、关键词云、时间线彩蛋、极值里程碑、提交类型人设（创造者 vs 消防员）、文风与深夜独白、开工时间表、提交节奏、劳模文件与目录、年度判词，共 16 屏。

- 纯 Python 标准库，零第三方依赖，全程离线，只读 git 仓库；
- 报告为自包含单文件 HTML，双击即开，可直接分享。

### 使用

对代理说「给我的仓库生成 2026 年度代码报告 / 年度总结 / 年报」即可触发；或直接运行：

```bash
cd <skill>/scripts
python3 -m annual_report --demo --output demo.html          # 30 秒示例
python3 -m annual_report ~/work/api --year 2026             # 真实数据
```

## ITRA 跑者分数查询（itra-runner-score）

![icon](skills/itra-runner-score/assets/icon.png)

按姓名或 ITRA ID 查越野跑者的 **ITRA 表现指数（PI）**、跑者等级、世界 / 洲际 / 国家排名与完整完赛记录。直接抓 itra.run 公开页面，**免登录、无需 API Key、零第三方依赖**（urllib + 手写 AES-256-CBC 解密）。

- 三种输入：姓名搜索（多候选会摊开消歧，不静默取第一条）／ ITRA ID ／ 主页 URL；
- 输出 PI、段位、百分位（世界前 X%）、各距离组 PI、完赛统计与逐场明细；
- 如实标注 ITRA 的两处数据限制：单场 Race Score 属订阅功能、公开页一律返回 `DNF`，本 skill 刻意不提供该列；完赛积分（0–6）标注的是赛道难度，不是成绩分。

### 使用

对代理说「查一下 Kilian Jornet 的 ITRA 分数」「我的 ITRA ID 是 123456，看看 PI 和世界排名」即可触发；或直接运行：

```bash
cd skills/itra-runner-score
python3 scripts/itra.py report "Kilian Jornet" --races 20    # 姓名 → 完整档案
python3 scripts/itra.py profile 123456 --races 50           # 虚构 ID 示例，请替换为目标跑者的实际 ID
python3 scripts/itra.py search "Example Runner" --limit 10   # 虚构姓名示例，先看候选再消歧
python3 scripts/itra.py report "向付召" --json                # 机器可读输出
```

> 抓取依赖 itra.run 三个未公开行为（WAF 路径绕过、AES 载荷解密、页内两组成绩数组），细节见 [references/itra-endpoints.md](skills/itra-runner-score/references/itra-endpoints.md)。改脚本前先读它——顺手「清理」一次 URL 或加密逻辑，就会静默弄坏这个 skill。

## 仓库结构

```text
agent-skills/
├── README.md                 # 技能索引与使用入口
├── LICENSE
├── skills/                   # 技能源码，一个技能一个目录
│   ├── git-annual-report/
│   └── itra-runner-score/
└── templates/
    └── SKILL.md.template      # 新技能起点，不作为可安装技能
```

## 新增或维护技能

从 [技能模板](templates/SKILL.md.template) 开始：

1. 在 `skills/<skill-name>/` 创建 `SKILL.md`，目录名与 frontmatter 的 `name` 保持一致。
2. 写清用途、触发场景、输入、执行方式、验证方法和交付结果；脚本、参考资料和素材按需添加。
3. 在临时目录验证一个典型场景；有脚本时按风险检查关键失败场景，再更新上方技能目录。

收录已整理、能独立使用的技能；从实际任务验证效果后再扩充目录。

## License

原创内容采用 [MIT](LICENSE)；引入的第三方内容遵循其原许可证，并在对应技能中注明。
