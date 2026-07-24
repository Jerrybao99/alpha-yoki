# alpha-jerry

> A 股基本面分析的 AI Native 工具集——覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送通知"完整业务闭环，帮助个人投资者识别优质公司并持续监控持仓风险。

**当前阶段**：M1 数据采集已完成（5516 股批量采集 < 10 秒，86/87 测试通过），M2 评分评级待开发。

## 快速开始

```bash
uv sync                                              # 安装依赖
cp .env.example .env                                 # 填入 TUSHARE_TOKEN

# 数据采集
uv run python scripts/sw_industry.py                 # SW 行业缓存（首次 ~11 分钟）
uv run python scripts/full_collect.py                # 全量批量采集（~5 秒）
uv run python scripts/smoke_collect.py --sample 5    # 随机 5 股冒烟

# 测试
uv run pytest                                        # 全部测试（含网络集成）
uv run pytest -m "not network"                       # 仅 mock 测试（CI）
```

## 技术栈

Python 3.14+ · uv · pydantic-settings · Tushare Pro · DeepSeek V4 Pro · LangGraph 0.2+ · pytest · ruff

## 项目结构

```
src/
├── config.py              # Settings 全局配置
├── main.py                # 运行入口
└── data/                  # 数据采集与输出
    ├── contract.py        # 字段契约（44 列 + 53 需求对齐表）
    ├── provider.py        # Tushare 适配器 + 限流重试 + SW 行业分类
    ├── collect.py         # 采集编排（逐股/批量 + 缓存 + 报告期推算）
    └── output.py          # CSV 输出与格式化
data/
├── fin/                   # 采集产物
├── ref/                   # 参考数据（sw_industry.csv）
├── test/                  # 集成测试产物（自动覆盖）
└── ...
scripts/
├── full_collect.py        # 全量批量采集
├── sw_industry.py         # SW 行业缓存生成
└── smoke_collect.py       # 随机 5 股冒烟
tests/                     # 单元测试（81 项）
integrated_tests/          # 集成测试（6 项 mock + 2 项 network）
docs/                      # 文档（dev-guide + ROADMAP）
```

## 定位

- **本地优先**：数据本地存储，不上传云端（NFR-01）
- **规则可审计**：评分/评级走纯函数 + 单测，一票否决可追溯
- **非套壳 Agent**：多 Agent 编排 + RAG + 路由 + 工具 + 记忆 + 监控 + 反馈（C-03）

## 文档

- [开发指南](docs/dev-guide.md) — 单一事实来源（业务规则 §8 RIGID）
- [路线图](docs/ROADMAP.md) — M0~M7 里程碑

## 免责声明

本项目输出仅供参考，不构成投资建议。投资决策由用户自行完成并自担风险。
