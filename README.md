# alpha-jerry

> A 股基本面分析的 AI Native 工具集——覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送通知"完整业务闭环，帮助个人投资者识别优质公司并持续监控持仓风险。

**当前阶段**：M2 评分评级已完成（263 项单测，覆盖率 99.3%），M3 报告输出待开发。

## 快速开始

```bash
uv sync                                              # 安装依赖
cp .env.example .env                                 # 填入 TUSHARE_TOKEN

# 数据采集
uv run python scripts/sw_industry.py                 # SW 行业缓存（首次 ~11 分钟）
uv run python scripts/full_collect.py                # 全量批量采集（~2-5 分钟）
uv run python scripts/smoke_collect.py --sample 5    # 随机 5 股冒烟

# 评分评级
uv run python scripts/full_scores.py                 # 全量评分评级

# 报告输出
uv run python scripts/full_report.py                 # 荐股 Top20 报告

# 测试
uv run pytest                                        # 全部测试（含网络集成）
uv run pytest -m "not network"                       # 仅 mock 测试（CI）
```

## 技术栈

Python 3.12+ · uv · pydantic-settings · Tushare Pro · DeepSeek V4 Pro · LangGraph 0.2+ · pytest 8+ · ruff

## 项目结构

```
src/
├── config.py                # Settings 全局配置
├── main.py                  # 运行入口
├── data/                    # 数据采集与输出
│   ├── contract.py          # 字段契约（~460 列 + 53 需求对齐表）
│   ├── provider.py          # Tushare 适配器 + 限流重试 + SW 行业分类
│   ├── collect.py           # 采集编排（逐股/批量 + 缓存 + 报告期推算）
│   └── output.py            # CSV 输出与格式化
├── scoring/                 # 评分/评级/否决
│   └── scores.py            # 三维评分纯函数 + 行业权重 + 评级映射
├── reports/                 # 报告输出规则引擎
│   ├── evaluation.py        # 公司类型分类 + 操作建议
│   └── reporting.py         # 荐股报告纯逻辑（解析/上下文/清洗）
└── agents/                  # LLM 适配
    └── llm_adapter.py       # DeepSeek 适配层
data/
├── fin/                     # 采集/评分/荐股产物
├── ref/                     # 参考数据（sw_industry.csv）
├── cache/                   # 采集缓存
├── test/                    # 集成测试产物（自动覆盖）
└── ...
scripts/
├── full_collect.py          # 全量批量采集
├── full_scores.py           # 全量评分评级
├── full_report.py           # 荐股 Top20 报告
├── smoke_collect.py         # 随机 5 股冒烟
└── sw_industry.py           # SW 行业缓存生成
tests/                       # 单元测试（297 项）
├── data/                    # 采集层（contract/provider/collect/output）
├── scoring/                 # 评分层（三维评分/否决/评级）
├── reports/                 # 报告层（公司类型/操作建议）
└── agents/                  # LLM 适配层
integrated_tests/            # 集成测试
docs/                        # 文档（dev-guide + ROADMAP + BRD）
```

## 核心流程

```
stock_basic(全 A 股清单)
  → income_vip / balancesheet_vip / cashflow_vip / fina_indicator_vip (VIP 批量)
  → StockFeatures (~460 字段)
  → check_veto() 一票否决
  → score_growth/stability/return() 三维评分
  → score_composite() 行业权重加权综合分
  → score_rating() 四级评级（皇冠明珠/优秀白马/鸡肋·观察/垃圾）
  → 输出 data/fin/full_scores/YYMMDD.csv
```

## 定位

- **本地优先**：数据本地存储，不上传云端（NFR-01）
- **规则可审计**：评分/评级走纯函数 + 单测，一票否决可追溯
- **非套壳 Agent**：多 Agent 编排 + RAG + 路由 + 工具 + 记忆 + 监控 + 反馈（C-03）

## 文档

- [开发指南](docs/dev-guide.md) — 单一事实来源（业务规则 §8 RIGID）
- [路线图](docs/ROADMAP.md) — M0~M7 里程碑
- [业务需求](docs/brd.md) — 需求基线（55 字段 + step1~4 流程）

## 免责声明

本项目输出仅供参考，不构成投资建议。投资决策由用户自行完成并自担风险。
