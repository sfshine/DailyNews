# DailyNews 技术情报日报

本项目用于沉淀每日技术情报，重点覆盖：

- **移动大前端**：Android、iOS、Flutter、React Native、跨端与端智能开发工具链。
- **AI Coding**：AI 编程助手、代码智能体、IDE/CLI Agent、MCP/Agent 工作流与安全。
- **具身人工智能**：机器人基础模型、Physical AI、Humanoid、仿真与真实世界部署。

## 自动化计划

仓库包含 GitHub Actions 定时任务，会在每天 **06:30 UTC** 运行 `scripts/generate_daily_report.py`，从公开 RSS/API 拉取最新信息并生成 `reports/YYYY-MM-DD.md`。

> 如果你希望按中国时间 06:30 运行，请把 `.github/workflows/daily-intel.yml` 的 cron 改为 `30 22 * * *`（UTC 前一天 22:30）。

## 手动生成日报

```bash
python3 scripts/generate_daily_report.py --date 2026-06-07
```

脚本不依赖第三方 Python 包，默认输出到 `reports/`。
