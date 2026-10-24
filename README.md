# agent-skills

Open agent skills（[skills.sh](https://skills.sh) 生态）——可被 Claude Code / Cursor / Codex 等编码代理直接安装使用。

## git-annual-report · 代码年度报告生成器

把本地 git 仓库的提交历史变成一份「网易云年报」风格的单文件离线 HTML 年度报告：年度总览、全年逐日热力图、24 小时与星期分布、逐月代码量、最活跃项目、技术栈构成、关键词云、时间线彩蛋、极值里程碑、提交类型人设（创造者 vs 消防员）、文风与深夜独白、开工时间表、提交节奏、劳模文件与目录、年度判词，共 16 屏。

- 纯 Python 标准库，零第三方依赖，全程离线，只读 git 仓库；
- 报告为自包含单文件 HTML，双击即开，可直接分享。

### 安装

```bash
npx skills add yinwenjian/agent-skills
```

### 使用

对代理说「给我的仓库生成 2026 年度代码报告 / 年度总结 / 年报」即可触发；或直接运行：

```bash
cd <skill>/scripts
python3 -m annual_report --demo --output demo.html          # 30 秒示例
python3 -m annual_report ~/work/api --year 2026             # 真实数据
```

## License

[MIT](LICENSE)
