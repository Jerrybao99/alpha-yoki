---
tags: [dev-guide, 开发指南, single-source-of-truth]
status: active
version: 1.0.0
date: 2026-07-21
合并自: [brd-1.md](./brd-1.md) + [prd.md](./prd.md)
适用对象: AI Coding Agent / 开发者
---

# alpha-jerry 开发指南（dev-guide）

> **本文件是项目的单一事实来源（Single Source of Truth）的工程视图**，由 [brd-1.md](./brd-1.md)（业务需求基线）与 [prd.md](./prd.md)（产品需求规格）合并而成。原文档保留不删除；当本文件与原文档冲突时，业务规则以 `brd-1.md` 为准，产品实现以 `prd.md` 为准，本文件以二者合并后的最新表述为准。
>
> **AI Agent 阅读约定**：
> 1. 先读 §0 术语与约定，再读 §2 业务目标，再按需跳转章节。
> 2. 标注 `[RIGID]` 的表格/规则为不可漂移契约，实现必须以纯函数单测对齐。
> 3. 标注 `[TRACE]` 的条目给出跨文档可追溯编号。
> 4. 任何代码改动须先检查 §11 验证门禁与 §12 交付标准。
> 5. 不确定时遵守 §13 决策优先级。

---

## 目录

- [0. 术语与全局约定](#0-术语与全局约定)
- [1. 项目定位](#1-项目定位)
- [2. 业务目标与成功指标](#2-业务目标与成功指标)
- [3. 业务范围与约束](#3-业务范围与约束)
- [4. 技术栈](#4-技术栈)
- [5. 仓库结构与目录边界](#5-仓库结构与目录边界)
- [6. 系统架构](#6-系统架构)
- [7. 多 Agent 设计](#7-多-agent-设计)
- [8. 业务规则（RIGID 契约）](#8-业务规则rigid-契约)
- [9. 功能需求清单（可追溯）](#9-功能需求清单可追溯)
- [10. 非功能需求与配置](#10-非功能需求与配置)
- [11. 接口与 UI](#11-接口与-ui)
- [12. 验证门禁与交付标准](#12-验证门禁与交付标准)
- [13. 里程碑](#13-里程碑)
- [14. 风险与待定事项](#14-风险与待定事项)
- [15. 决策优先级与冲突解决](#15-决策优先级与冲突解决)

---

## 0. 术语与全局约定

| 术语 | 含义 |
|---|---|
| BRD | 业务需求文档，见 [brd-1.md](./brd-1.md) |
| PRD | 产品需求文档，见 [prd.md](./prd.md) |
| `[RIGID]` | 不可漂移契约，须纯函数单测对齐 |
| `[TRACE]` | 跨文档可追溯编号 |
| local-first | 本地优先，数据不外传，仅 LLM 推理外联 |
| 一票否决 | 触发即剔除评级的硬性风险判定 |
| 三维评分 | 成长性 / 稳健性 / 资金回报，各 1-10 分 |
| 综合分 | 三维得分按行业权重加权求和，保留 1 位小数 |
| 评级 | 综合分映射的四档结论 |
| 公司类型 | 千里马 / 现金牛 / 护城河，影响权重 |

**全局约定**：
- 项目为中文项目；文档/注释/日志/Prompt 以中文为主，金融字段同时给中文与英文缩写。
- 数据目录统一为小写 `data/`（符合 `coding.md` 规范，BRD 原文 `DATA/` 已统一）。
- `data/` 下属子目录采用英文简写，映射如下（文件名后缀如 `-评分`/`-评级`/`-荐股` 保留中文以匹配 BRD 文案）：

  | 中文 | 英文简写 | 用途 |
  |---|---|---|
  | 财务 | `fin` | 采集/评分/评级/否决/失败 csv |
  | 分析 | `analysis` | 荐股 Top20 报告 |
  | 持股 | `hold` | 持仓基线与 09/17 重算结果 |
  | 热点 | `hot` | 热搜缓存与识别结果 |
  | 监控 | `monitor` | Agent 执行链 |
  | 反馈 | `feedback` | 用户反馈 |
  | — | `rag` | 向量库与知识库 |

- 文件名 `YYMMDD` 表示日期戳，如 `250721`；带时段后缀 `-09`/`-17` 表示 09:00/17:00 触发产物。
- 需求编号体系：`BR-*`（业务需求）、`FR-<域>-*`（功能需求）、`NFR-*`（非功能）、`AR-*`（Agent 需求）。
- 优先级：`P0` 必须有 / `P1` 应该有 / `P2` 可以有。

---

## 1. 项目定位

`alpha-jerry` 是一套**面向 A 股基本面分析的 AI Native 工具集**，覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送通知"完整业务闭环。

- **形态**：Win/Mac 双端桌面应用 + 本地多 Agent 编排 + RAG 知识库。
- **差异化**：本地优先、对话驱动、规则可审计、结论可回溯。
- **一句话定位**：把机构级基本面筛选逻辑，做成个人投资者桌面上随时可对话的智能助手。
- **非套壳**：Agent 具备多 Agent 编排、RAG、路由、工具、记忆、监控、反馈（BRD 约束 C-03）。

**非目标（Out of Scope）**：量化高频交易、盘中实时下单、港股/美股多市场、云端 SaaS、纯技术面短线策略、自动代客理财。

---

## 2. 业务目标与成功指标

### 2.1 业务目标（SMART） `[TRACE: brd-1.md §3.1]`

| 编号 | 业务目标 | 衡量方式 | 达成时限 |
|---|---|---|---|
| BO-01 | 落地完整基本面分析闭环 | step1~step4 全流程可一键跑通并产出 csv | M3 |
| BO-02 | 评分规则可解释可审计 | 否决记录、评分明细、评级依据可追溯 | M2 |
| BO-03 | 持仓风险主动监控 | 每日 09:00/17:00 自动重算并推送风险提示 | M5 |
| BO-04 | 对话式零门槛交互 | 自然语言即可触发采集/评分/报告/持仓分析 | M4 |
| BO-05 | 双端本地化部署 | Win/Mac 桌面端可安装运行，数据不外传 | M6 |
| BO-06 | 低成本可维护 | 全部依赖成熟开源工具，年度运行成本趋近于零 | M7 |

### 2.2 成功指标（KPI）

| 维度 | 指标 | 目标值 | 采集方式 |
|---|---|---|---|
| 覆盖率 | 全 A 股采集覆盖率 | ≥ 95% | 采集日志统计 |
| 可用性 | 全流程跑通成功率 | ≥ 99%（单股失败不影响整体） | pipeline 执行记录 |
| 时效性 | 持仓分析推送准时率 | 09:00/17:00 ±10 分钟内送达 | 推送日志 |
| 准确性 | 评分规则单测覆盖率 | 阈值边界 100% 覆盖 | pytest 报告 |
| 体验 | 对话响应首字延迟 | ≤ 3 秒（SSE 流式） | 监控区 |
| 隐私 | 云端数据上传量 | 0（仅 LLM 推理外联） | 网络审计 |
| 成本 | 单次全量分析 LLM 成本 | ≤ 可配预算上限 | token 统计 |

> KPI 阈值在 M0 后实测校准，写入 `docs/architecture.md` 的 ADR。

---

## 3. 业务范围与约束

### 3.1 假设与依赖

| 类型 | 编号 | 内容 |
|---|---|---|
| 假设 | A1 | 用户已自办 Tushare Pro 账户并取得可用 token 与积分 |
| 假设 | A2 | 用户已取得 DeepSeek API Key |
| 假设 | A3 | 用户设备网络可达 Tushare 与 DeepSeek |
| 假设 | A4 | A 股财报口径在项目周期内无破坏性变更 |
| 假设 | A5 | 投资决策仍由人完成，工具仅提供分析辅助 |
| 依赖 | D1 | Tushare Pro 接口与积分 |
| 依赖 | D2 | DeepSeek LLM 推理服务 |
| 依赖 | D3 | 百度/微博/东财等热搜来源可访问 |
| 依赖 | D4 | Win/Mac 打包工具链（Electron 等） |

### 3.2 约束条件 `[TRACE: brd-1.md §9]`

| 编号 | 约束 | 类型 |
|---|---|---|
| C-01 | 使用成熟、开源、低成本工具 | 选型 |
| C-02 | 架构简洁、稳定、主流、先进、可扩展 | 架构 |
| C-03 | Agent 非套壳，具备多 Agent 编排/RAG/路由/工具/记忆/监控/反馈 | 架构 |
| C-04 | DeepSeek 为默认 LLM | 选型 |
| C-05 | Tushare 为数据源 | 选型 |
| C-06 | Kimi K3 设计 UI | 设计 |
| C-07 | UI 如 openclaw 般可随时对话交互（Win/Mac） | 交互 |
| C-08 | 图标为巧克力色荷兰侏儒兔，openclaw 风格 | 品牌 |
| C-09 | 数据可及时更新 | 时效 |
| C-10 | Win/Mac 双端兼容 | 平台 |
| C-11 | 数据本地存储，不上传云端 | 隐私 |
| C-12 | 项目命名 `alpha-jerry` | 命名 |

---

## 4. 技术栈

`[TRACE: prd.md §2.1]` 精确到主版本，遵循"成熟、开源、低成本"。

| 层 | 选型 | 版本约束 | 说明 |
|---|---|---|---|
| 语言 | Python | >= 3.12 | 后端/Agent/数据管道 |
| 包管理 | uv | latest | 单虚拟环境，`uv.lock` |
| 构建 | hatchling | latest | `[build-system]`，使 `uv run` 可导入 `src`/`api` 包 |
| LLM | DeepSeek V4 Pro | 默认 provider | OpenAI 兼容接口 |
| UI 设计参考 | Kimi K3 | — | 设计稿生成参考 |
| 数据源 | Tushare Pro | latest | A 股基本面/行情/资金面 |
| Agent 框架 | LangGraph | 0.2+ | 多 Agent 编排、状态机、条件路由 |
| LLM 抽象 | LiteLLM / OpenAI SDK | latest | 统一 provider |
| RAG 向量库 | ChromaDB | latest | 本地嵌入向量 |
| 嵌入模型 | bge-small-zh（本地） | — | 中文金融语义，离线可跑 |
| 后端 API | FastAPI | 0.110+ | 桌面端与调度调用 |
| 调度 | APScheduler / cron | latest | 定时任务 |
| 数据处理 | pandas / csv | latest | csv 读写 |
| 桌面端 | Electron + React + Vite | — | 套壳本地 FastAPI，参考 openclaw apps |
| 配置 | pydantic-settings + `.env` | latest | `Settings` 类集中管理 |
| 测试 | pytest | >= 8 | 单元 + 集成 |
| Lint/Format | ruff | latest | 统一格式 |

> 任何替换须在 ADR（`docs/architecture.md`）中说明。

---

## 5. 仓库结构与目录边界

`[TRACE: prd.md §2.3, coding.md]`

```
alpha-jerry/
├── AGENTS.md                  # 项目级 AI 行为规范（上下文入口）
├── README.md
├── CHANGELOG.md               # Keep a Changelog, SemVer
├── pyproject.toml
├── uv.lock
├── .env.example               # 配置样板（新增配置项必须同步）
├── .gitignore
├── docs/                      # 文档
│   ├── brd.md / brd-1.md / prd.md / dev-guide.md（本文件）/ dev-log.md
│   ├── architecture.md        # 架构详解（ADR）
│   ├── data-contract.md       # 字段契约与计算口径（已合并入 §8.1）
│   └── prompt-library.md      # Prompt 模板库
├── data/                      # 运行期数据（gitignore）
│   ├── fin/                   # YYMMDD.csv / -评分 / -评级 / -否决 / -失败
│   ├── analysis/              # YYMMDD-荐股.csv
│   ├── hold/                  # YYMMDD.csv / -09 / -17
│   ├── hot/                   # YYMMDD-HH.csv
│   ├── monitor/               # Agent 执行链
│   ├── feedback/              # 用户反馈
│   └── rag/                   # 向量库与知识库
├── src/                       # 源代码
│   ├── main.py                # 运行入口
│   ├── config.py              # Settings 入口
│   ├── data/                  # 数据采集与输出层
│   │   ├── contract.py        # StockFeatures 字段模型 + 字段对齐表 + 列序
│   │   ├── provider.py        # Tushare 适配器 + 接口注册表 + 行业分类
│   │   ├── collect.py         # 采集编排 + 缓存 + 报告期推算
│   │   └── reports.py         # CSV 写盘 + 数值格式化
├── scripts/                   # 辅助脚本
├── tests/                     # 单元测试
├── integrated_tests/          # 集成测试
└── manifests/                 # 部署清单（Win/Mac 打包）
```

**目录边界硬规则**（AI 改动时须遵守）：
- 后端逻辑 → `src/`；部署 → `scripts/` + `manifests/`。
- 模块膨胀到 3+ 文件再升格为包，否则保持单文件扁平结构。
- 纯逻辑（评分/评级/权重）与 I/O（爬取/写盘）分层：纯逻辑单独单测，I/O 走集成测试。
- 配置抽离：路径/超时/模型/API Key 全走 `Settings`，禁止硬编码。
- 单 PR 单功能，≤ 20 文件，超出须在 PR 描述说明原因。

---

## 6. 系统架构

### 6.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop Shell (Electron + React, Win/Mac)                   │
│  ─ 对话交互 / 报告查看 / 持仓录入 / 推送预览                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/SSE (localhost)
┌──────────────────────────┴──────────────────────────────────┐
│  API Layer (FastAPI)                                         │
│  ─ /chat /report /portfolio /hotspot /pipeline /health       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  Agent Orchestration (LangGraph)                             │
│  ─ Router → Data/Scoring/Rating/Report/Hotspot/Portfolio/    │
│    Chat Agent                                                │
│  ─ Memory / RAG / Tools / Feedback / Monitor                 │
└──────────┬──────────────────────────────────────────────────┘
           │                        │
┌──────────┴───────────┐  ┌─────────┴────────────────────────┐
│  Domain Core (纯逻辑) │  │  Data Provider (I/O)             │
│  scoring/rating/      │  │  Tushare 适配器 / 缓存 / 重试     │
│  reports/schemas      │  │  RAG 检索 / 通知发送              │
└──────────────────────┘  └──────────────────────────────────┘
```

### 6.2 业务流程（数据流）

**核心流程 step1~step4：**

```
全 A 股清单
  │ ① 采集（Tushare，特征工程字段）
  ▼ data/fin/YYMMDD.csv
  │ ② 评分（否决 → 三维评分 → 行业权重 → 综合分）
  ▼ data/fin/YYMMDD-评分.csv
  │ ③ 评级（综合分 → 四级评级 + AI 点评）
  ▼ data/fin/YYMMDD-评级.csv
  │ ④ 报告（综合分降序 Top20 + 持仓表）
  ▼ data/analysis/YYMMDD-荐股.csv   ← 用户据此决策
     data/hold/YYMMDD.csv        ← 持仓基线
```

**持续运营流程：**

```
每日 09:00 / 17:00
  ├─ 热点追踪：采热搜 → LLM 识别机会 → 受益行业/个股 → data/hot/YYMMDD-HH.csv
  └─ 持股分析：重爬重算持仓 → 风险高亮 → 趋势对比 → 操作建议
        → data/hold/YYMMDD-09.csv / -17.csv
  │
  ▼ 推送（邮件完整 HTML / 微信摘要）
```

**更新流程**：时间触发自动执行；季度财报季后更新基本面；每月更新资金面。

### 6.3 架构原则

1. 目录边界清晰（见 §5）。
2. 配置抽离，禁止硬编码。
3. 数据源单一真源 + Fallback：Tushare 主，预留 `BaseFetcher` 抽象。
4. 纯逻辑与 I/O 分层。
5. Agent 非套壳（C-03）。
6. 本地优先：向量库/数据库/缓存全部本地，除 LLM 推理外不外联。
7. 单 PR 单功能（≤ 20 文件）。
8. 插件化扩展：核心精简，可选能力以扩展形式接入（参考 openclaw）。

---

## 7. 多 Agent 设计

`[TRACE: prd.md §3.2, §7; AR-*]` 参考 `TradingAgents-CN` agents 分层 + `openclaw` agent-core。

### 7.1 Agent 拓扑

| Agent | 职责 | 工具 | 记忆 | 输出 |
|---|---|---|---|---|
| RouterAgent | 意图路由，无法识别回退 ChatAgent | `classify_intent`（LLM+规则正则） | 短期会话 | 路由决策 |
| DataAgent | 采集全 A 股并落地特征字段 | `fetch_stock_list`/`fetch_financials`/`save_csv` | 采集进度 | `data/fin/YYMMDD.csv` |
| ScoringAgent | 否决 + 三维评分 + 权重 + 综合分 | `scoring` 纯函数族 | 评分快照 | `-评分.csv` |
| RatingAgent | 评级 + 公司类型 + 行业分类 + AI 点评 | `rating` 纯函数 + `llm_comment` | 评级历史 | `-评级.csv` |
| ReportAgent | 荐股 Top20 + 持仓表 | `build_top20`/`render_portfolio`/`llm_highlight` | 报告索引 | `data/analysis/荐股.csv`、`data/hold/*.csv` |
| HotspotAgent | 采热搜 → LLM 识别 → 受益行业/个股 | `fetch_hot_search`/`llm_identify_opportunity`/`rag_map_industry_to_stocks` | 热点时序 | `data/hot/` |
| PortfolioAgent | 持仓重算、风险高亮、趋势、操作建议 | `reload_holdings`/`rescore`/`diff_last_score`/`suggest_action` | 持仓变化 | `data/hold/YYMMDD-09.csv` 等 |
| ChatAgent | 自由对话，调用其他 Agent（受权限约束） | 全部工具 | 长期会话 + RAG | 对话回复 |

### 7.2 编排要素（满足 C-03）

- **路由**：RouterAgent 基于 LLM 意图分类 + 规则兜底，决策可解释、可日志回溯（参考 `TradingAgents-CN/graph/conditional_logic.py`）。
- **工具**：能力封装为 LangGraph ToolNode；纯逻辑工具可离线单测。
- **记忆**：短期会话 / 长期（评分历史、持仓变化、用户偏好）/ RAG（行业知识、规则文档）。
- **RAG**：行业对照表、否决规则、评分阈值、行业分类逻辑入库，决策时检索对齐，防幻觉漂移。ChromaDB + bge-small-zh。
- **反馈**：用户对点评/建议点赞或修正，入 `data/feedback/`，用于 Prompt 与评分校准迭代。
- **监控**：每次执行记录 `agent_name / tools_called / tokens / latency / status / error`，落盘 `data/monitor/`，UI 可查。
- **反思**：参考 `TradingAgents-CN/graph/reflection.py`，关键决策（荐股 Top20）支持一轮自我审查。

---

## 8. 业务规则（RIGID 契约）

> **本章是项目核心业务资产，不可漂移。实现必须以纯函数对齐，并以单测覆盖全部区间边界。** `[TRACE: brd-1.md §7, prd.md §6]`

### 8.1 特征工程字段表 `[RIGID]`

采集并落地到 `data/fin/YYMMDD.csv`，**列名采用 Tushare 接口真实返回字段名、数据为真实值**（owner 决策，对齐 https://tushare.pro/document/2；偏离原中文字段名约定已记 CHANGELOG）。

单一事实来源为代码：`src/data/contract.py` 的 `OUTPUT_COLUMNS`（44 列）与 `REQUIREMENT_ALIGNMENT`。接口注册表见 `src/data/provider.py` 的 `TUSHARE_INTERFACES`（20 个接口）。

**接口选型（5000 积分可调用，优先 vip 高级接口）**：财务三表 / 指标 / 预告 / 快报 / 主营构成使用 `_vip` 后缀接口（按 `period` 批量取全市场），其余接口使用常规接口（≤5000 积分）。`fetch_financials` 实际调用 4 个 vip 接口：`income_vip` / `balancesheet_vip` / `cashflow_vip` / `fina_indicator_vip`。

完整接口注册表（20 个，详见 `src/data/provider.py`）：

| 业务别名 | 常规接口 | vip 接口 | 最低积分 | doc_id | 用途 |
|---|---|---|---|---|---|
| stock_basic | stock_basic | — | 2000 | 25 | 股票列表 |
| income | income | **income_vip** | 2000 | 33 | 利润表 |
| balancesheet | balancesheet | **balancesheet_vip** | 2000 | 36 | 资产负债表 |
| cashflow | cashflow | **cashflow_vip** | 2000 | 44 | 现金流量表 |
| fina_indicator | fina_indicator | **fina_indicator_vip** | 2000 | 79 | 财务指标 |
| daily_basic | daily_basic | — | 2000 | 32 | 每日指标（首版不调用） |
| fina_audit | fina_audit | — | 2000 | 80 | 审计意见（首版不调用） |
| dividend | dividend | — | 2000 | 103 | 分红送股（已移除） |
| pledge_stat | pledge_stat | — | 2000 | 110 | 质押统计（首版不调用） |
| forecast | forecast | **forecast_vip** | 2000 | 45 | 业绩预告 |
| express | express | **express_vip** | 2000 | 46 | 业绩快报 |
| fina_mainbz | fina_mainbz | **fina_mainbz_vip** | 2000 | 81 | 主营构成 |
| top10_holders | top10_holders | — | 2000 | 61 | 前十大股东 |
| top10_floatholders | top10_floatholders | — | 2000 | 62 | 前十大流通股东 |
| disclosure_date | disclosure_date | — | 2000 | 162 | 财报披露日期 |
| trade_cal | trade_cal | — | 2000 | 26 | 交易日历 |
| stk_holdernumber | stk_holdernumber | — | 600 | 166 | 股东人数 |
| stk_holdertrade | stk_holdertrade | — | 2000 | 175 | 股东增减持 |
| share_float | share_float | — | 120 | 160 | 限售股解禁 |
| repurchase | repurchase | — | 2000 | 124 | 股票回购 |

原始 55 个需求字段对齐结果（落地 53 个）：

| 对齐 | 数量 | 含义 |
|---|---|---|
| exact | 38 | Tushare 有精确字段，直接采集 |
| approximate | 3 | 无精确字段取最近似：主营收入→`revenue`、主营利润→`operate_profit`、营业外收支→`non_oper_income`/`non_oper_exp` |
| computed_in_scoring | 6 | 不落盘，由 M2 评分纯函数基于真实字段计算（见下方计算口径表） |
| unavailable | 6 | Tushare 无且无近似，首版不采集（见下方不可用字段表） |

> owner 决策（见 CHANGELOG）：上市日期/公告日期不再采集输出，需求字段由 55 收敛为 53；float_share（流通股本）已删除不采集，由 approximate 移入 unavailable；brd-1.md §7.8 业务基线 55 字段清单保持不变。

**计算型字段口径**（不落盘，M2 纯函数计算）：

| 需求字段 | 计算公式 | 依赖真实字段 |
|---|---|---|
| 股东权益比 | `total_hldr_eqy_exc_min_int / total_assets` | balancesheet_vip |
| 限售股合计 | 首版不计算（float_share 已删除） | — |
| 每股经营现金流/每股收益 | `ocfps / eps` | fina_indicator_vip |
| 净利润占营业利润比 | `n_income_attr_p / operate_profit` | income_vip |
| 主营利润率 | `operate_profit / revenue` | income_vip |
| 投资收益占比 | `invest_income / total_profit` | income_vip |

**不可用字段**（6 个，首版不采集）：

| 需求字段 | 原因 |
|---|---|
| 调整后每股净资产 | Tushare 无此字段且无近似 |
| 无限售股合计 | 近似字段 float_share 已删除 |
| A股数量 | Tushare 无此字段 |
| B股数量 | Tushare 无此字段 |
| 国家持股数量 | 需 top10_holders 聚合，首版不采集 |
| 国有法人持股 | 需 top10_holders 聚合，首版不采集 |

**补充字段（3 个，服务一票否决 §8.2 / 三维评分 §8.3）**：`SUPPLEMENTARY_FIELDS` 记录额外采集的字段（`money_cap`/`free_cashflow`/`inv_turn`），来源 `balancesheet_vip`/`cashflow_vip`/`fina_indicator_vip`，已合并入 `OUTPUT_COLUMNS` 中（`SUPPLEMENTARY_COLUMNS` 为空）。

各接口请求字段见 `STOCK_BASIC_FIELDS` / `INCOME_FIELDS` / `BALANCESHEET_FIELDS` / `CASHFLOW_FIELDS` / `FINA_INDICATOR_FIELDS`。百分比类字段（`netprofit_yoy`/`or_yoy`/`grossprofit_margin`/`debt_to_assets`/`netprofit_margin`）以百分数数值返回，写盘加 `%` 后缀保留两位小数。

**报告期与最新数据校验**：`end_date`（财报所属期间）以 `income` 的报告期为唯一来源；`fetch_financials` 调用 4 个 vip 接口（income / balancesheet / cashflow / fina_indicator），其余接口按各自 `end_date` 选最新但不覆盖该字段。`period=None`（"最新"）缓存按 `cache_ttl_hours`（默认 24h）失效，避免新报告期已披露而缓存陈旧。最新报告期校验：`src/data/collect.py::expected_latest_period(today)` 按法定披露截止日（Q1→4-30、半年报→8-31、Q3→10-31、年报→次年4-30）推算预期值；`integrated_tests/test_smoke_collect.py` 为对应 network 测试。

**CSV 列序**：`OUTPUT_COLUMNS`（44 列）按财务阅读习惯分组排列（基本信息→利润表→利润率增速→资产负债→偿债指标→每股指标→现金流量→营运效率），不再按接口来源顺序。

**申万行业分类（五大类）**：CSV 中"所属分类"列不再使用 stock_basic 的 `industry` 字段，改为通过申万行业指数分类映射到五个大类。数据链：`ts_code → index_member_all(ts_code, is_new='Y') → l2_name → sw_l2_to_category() → 五大类`。纯映射见 `src/data/provider.py`（约 130 个 SW 二级行业名→五大类，自动剥离罗马数字后缀如 `中药Ⅱ`→`中药`）。分类仅在采集范围内按需查询 API，结果增量缓存到 `data/cache/sw_industry.csv`。

**CSV 数值格式化**：所有数值字段按 `data/test/YYMMDD-数据来源.csv` 中记录的单位匹配后缀（代码见 `src/data/reports.py::format_value`），具体规则：
- `元` → 亿/万数量级 + 元（如 `1.13亿元`、`-1526.07万元`）
- `%` → `.2f%`（含 PERCENT_FIELDS 五项 + roe）
- `倍` → `.2f倍`（current_ratio/quick_ratio/assets_to_eqt）
- `次` → `.2f次`（inv_turn）
- `元/股` → `.2f元/股`（eps/bps/ocfps/capital_rese_ps/undist_profit_ps）
- `股` → 亿/万数量级 + 股（total_share，如 `3.56亿股`）
- `比率` → `.2f` 无后缀（ocf_to_shortdebt）
单元格不做 CJK 宽度填充（Excel 打开后 Ctrl+A + 双击列边界即可自适应列宽）。

### 8.2 一票否决规则 `[RIGID]`

| 否决项 | 判定条件 |
|---|---|
| 造假嫌疑 | 货币资金高但利息收入极低；经营现金流连续多年远低于净利润 |
| 行业毁灭 | 技术路线被颠覆（如胶卷、燃油车零部件） |
| 诚信问题 | 频繁更换审计机构（3 年换 2 次以上）；大股东质押率 >70%；曾因信披违规被立案 |

**逻辑**：触发任一 → 剔除评级 → 记录到 `data/fin/YYMMDD-否决.csv` 供审计。

### 8.3 三维评分阈值 `[RIGID]`

#### 8.3.1 成长性得分

| 分数 | 营收增速 | 净利增速 | 盈利质量 | 现金流匹配 |
|---|---|---|---|---|
| 9-10 | > 40% | >50% | 毛利上升 | >1.2 |
| 7-8 | 25-40% | 30-50% | 毛利稳定 | 1.0-1.2 |
| 5-6 | 15-25% | 15-30% | 毛利微降 | 0.8-1.0 |
| 3-4 | 5-15% | 0-15% | 毛利显著降 | 0.5-0.8 |
| 1-2 | < 5%或负 | 负增长 | 毛利崩盘 | <0.5 |

#### 8.3.2 稳健性得分

| 分数 | 资产负债率 | 流动比率 | 存货周转率 | 审计意见 |
|---|---|---|---|---|
| 9-10 | < 40% | > 2.5 | 快于平均 | 无风险 |
| 7-8 | 40-60% | 1.5-2.5 | 持平平均 | 结构清晰 |
| 5-6 | 60-75% | 1.0-1.5 | 略慢平均 | 少量关联交易 |
| 3-4 | 75-85% | < 1.0 | 积压严重 | 审计非标 |
| 1-2 | > 85% | 断裂边缘 | 卖不出去 | 存贷双高 |

#### 8.3.3 资金回报得分

| 分数 | ROE | 自由现金流 | 分红率 | 估值 |
|---|---|---|---|---|
| 9-10 | > 20% | 持续正且增长 | 分红 > 40% | PEG < 1 |
| 7-8 | 15-20% | 正偶尔波动 | 分红 30-40% | PEG 1-1.5 |
| 5-6 | 10-15% | 接近 0 | 象征性分红 | PEG > 1.5 |
| 3-4 | 6-10% | 为负 | 不分红 | 历史高位 |
| 1-2 | < 6% | 巨额负值 | 铁公鸡 | 泡沫化 |

### 8.4 行业权重对照表 `[RIGID]`

> 权重以区间给出时，默认取区间中点；评审冻结后可改为确定值并在 `Settings` 中覆盖。

#### 周期资源类

| 维度 | 权重 | 9-10分 | 7-8分 | 5-6分 | 3分以下 |
|---|---|---|---|---|---|
| 成长性 | 20-30% | 产品价涨>20%或营收>30% | 营收15-30%靠产能 | 营收5-15% | 营收<5%或负 |
| 稳健性 | 30-40% | 负债率<50% | 50-65% | 65-75% | >75%存贷双高 |
| 资金回报 | 40% | ROE>18%股息率>4% | 12-18%稳分红 | 10-12%微薄 | <10%不分红 |

#### 大消费类

| 维度 | 权重 | 9-10分 | 7-8分 | 5-6分 | 3分以下 |
|---|---|---|---|---|---|
| 成长性 | 30% | 双位数+预收增 | 营收10-20% | 3-10% | 负增长 |
| 稳健性 | 30% | 现金流>净利 | 负债率<40% | 40-50% | >50% |
| 资金回报 | 40% | ROE>25%分红>50% | 15-20%分红>30% | 10-15%分红<30% | <10%不分红 |

#### 证券金融类

| 维度 | 权重 | 9-10分 | 7-8分 | 5-6分 | 3分以下 |
|---|---|---|---|---|---|
| 成长性 | 30% | 净利>50%市占升 | 20-40%跑赢大盘 | 5-20% | 负增长 |
| 稳健性 | 30% | 风控全覆盖 | 资本充足达标 | 基本达标 | 重大违规 |
| 资金回报 | 40% | ROE>12% PB低位 | 8-12%分红稳 | 5-8% | <5%不分红 |

#### 新能源/高端制造/科技

| 维度 | 权重 | 9-10分 | 7-8分 | 5-6分 | 3分以下 |
|---|---|---|---|---|---|
| 成长性 | 50% | 营收>40%订单饱满 | 25-40%产能利用率>85% | 15-25% | <15%负 |
| 稳健性 | 20% | 研发>10%流动>1.5 | 5-10%负债<60% | <5%流动<1.2 | 技术颠覆 |
| 资金回报 | 30% | 毛利>30%提升 PEG<1 | 毛利稳 ROE>12% | 毛利降 8-12% | <8% |

#### 公用事业/基建/交通

| 维度 | 权重 | 9-10分 | 7-8分 | 5-6分 | 3分以下 |
|---|---|---|---|---|---|
| 成长性 | 20% | 新项目净利>20% | 5-15% | 0-5% | 负增长 |
| 稳健性 | 40% | 现金流充沛 融资成本<3% | 渠道畅通 | 负债偏高可控 | 违约风险 |
| 资金回报 | 40% | 股息率>5% 支付率>60% | 3-5% ROE8-12% | 1-3% ROE5-8% | <1%不分红 |

### 8.5 综合分公式 `[RIGID]`

$$
\text{综合分} = \text{成长分} \times \text{成长权重} + \text{稳健分} \times \text{稳健权重} + \text{回报分} \times \text{回报权重}
$$

- 保留 1 位小数。
- 综合分追加到原 csv 字段末尾，另存 `data/fin/YYMMDD-评分.csv`，保留全部原始字段。

### 8.6 评级映射 `[RIGID]`

| 综合分 | 评级 |
|---|---|
| 8.5-10 | 👑 皇冠明珠 |
| 7.0-8.4 | ⭐ 优秀白马 |
| 5.5-6.9 | 🔄 鸡肋·观察 |
| <5.5 | ⚠️ 垃圾 |

- 评级字段追加到原 csv 末尾，另存 `data/fin/YYMMDD-评级.csv`，保留原字段。
- **边界单测必覆盖**：8.5 / 7.0 / 5.5 三个临界值归属正确。

### 8.7 公司类型 `[RIGID]`

| 类型 | 典型特征 | 示例行业 | 成长/稳健/回报权重 |
|---|---|---|---|
| 🐎 千里马 | 营收增速 > 15%，扩张期 | 科技、医药、新能源 | 50% / 20% / 30% |
| 🐮 现金牛 | 增速稳定，高分红，成熟期 | 银行、能源、基建、高速 | 20% / 40% / 40% |
| 🛡️ 护城河 | 品牌溢价高，毛利高，抗通胀 | 高端白酒、家电、食品 | 30% / 30% / 40% |

### 8.8 行业分类 `[RIGID]`

| 行业 | 典型公司 | 常态分类 | 特殊情况 |
|---|---|---|---|
| 周期资源 | 紫金矿业、山东黄金 | 现金牛 | 景气爆发期可为千里马 |
| 大消费 | 贵州茅台、山西汾酒 | 护城河 | 大众消费品可为千里马 |
| 证券金融 | 中信证券、国泰海通 | 护城河（头部） | 特色券商可为千里马 |
| 科技/制造 | 比亚迪、金雷股份 | 千里马 | 平台型龙头可为护城河 |
| 公用事业/基建 | 粤高速A、江苏华辰 | 现金牛 | 扩张期可为千里马 |

### 8.9 评级 → 操作建议映射 `[RIGID]`

| 评级 | 操作建议 | 仓位建议 |
|---|---|---|
| 👑 皇冠明珠 | 重仓买入 | 10-20% |
| ⭐ 优秀白马 | 分批建仓 | 5-10% |
| 🔄 鸡肋·观察 | 观望/波段 | <3% |
| ⚠️ 垃圾 | 坚决回避 | 0% |

### 8.10 荐股/持仓报告字段 `[RIGID]`

| 字段（缩写） | 列属性 | 取值示例 |
|---|---|---|
| 股票代码（Code） | 文本 | 600000 |
| 股票名称（Name） | 文本 | 浦发银行 |
| 公司类型 | 文本 | 千里马/现金牛/护城河 |
| 行业分类 | 文本 | 周期资源/大消费/证券金融/新能源制造/公用事业基建 |
| 核心亮点 | 文本 | AI 生成，≤30 字 |
| 成长性 | 数值(1位) | 0-10 |
| 稳健性 | 数值(1位) | 0-10 |
| 回报性 | 数值(1位) | 0-10 |
| 综合分 | 数值(1位) | 0-10 |
| 评级 | 文本 | 皇冠明珠/优秀白马/鸡肋·观察/垃圾 |
| 点评 | 文本 | AI 点评，≤50 字 |

- 荐股：按综合分降序取 Top20，落地 `data/analysis/YYMMDD-荐股.csv`。
- 持仓：用户对话录入（代码+名称），系统生成 `data/hold/YYMMDD.csv`，字段同荐股表。

---

## 9. 功能需求清单（可追溯）

> 业务需求 `BR-*` 来自 brd-1.md §8，功能需求 `FR-*` 来自 prd.md §4。下表为二者映射，AI 实现时以 `FR-*` 为单元交付。

| BR | FR 域 | 需求要点 | 优先级 |
|---|---|---|---|
| BR-01/02 | FR-DATA-01~10 | Tushare 单一数据源 + `BaseFetcher` 抽象；全 A 股清单；特征字段落地 `data/fin/YYMMDD.csv`；最新报告期三表；低并发续采；缓存增量；限流重试；Tushare 真实字段名+百分比格式（§8.1）；季度/月度更新 | P0 |
| BR-03 | FR-SCORE-01 | 一票否决（§8.2）剔除并审计 | P0 |
| BR-04 | FR-SCORE-02~09 | 三维评分（§8.3）+ 行业权重（§8.4）+ 综合分（§8.5）；纯函数单测；公司类型权重微调 | P0 |
| BR-05 | FR-RATE-01~04 | 四级评级（§8.6）；边界单测；否决记录审计 | P0 |
| BR-06 | FR-REPORT-01~07 | 荐股 Top20（§8.10）；AI 亮点≤30字/点评≤50字；公司类型+行业分类规则校验；操作建议（§8.9） | P0 |
| BR-07 | FR-REPORT-06 | 持仓录入生成持仓表 | P0 |
| BR-08 | FR-HOTSPOT-01~05 | 每日 09:00/17:00；采 Top10 热搜；LLM 识别机会；RAG 映射个股 Top5 | P0/P1 |
| BR-09 | FR-PORT-01~05 | 每日 09:00/17:00；重爬重算；风险高亮；趋势对比；操作建议 | P0 |
| BR-10 | FR-PUSH-01~05 | 结束即推；持仓摘要+热点 Top5；邮件 HTML/微信摘要；单渠道失败不拖垮 | P0/P1 |
| BR-11 | FR-UPDATE-01~04 | 时间触发；季度基本面/月度资金面；手动入口 | P0/P1 |
| BR-12 | AR-* / §7 | 多 Agent 编排 + RAG + 记忆 + 监控 + 反馈 | P0 |
| BR-13 | FR-UI-06 | Win/Mac 双端打包 | P0 |
| BR-14 | FR-CHAT-01~05 | 双端对话；触发任意 Agent；SSE 流式；RAG 作答；历史持久化 | P0/P1 |
| BR-15 | NFR-01 | 数据本地存储，不上传云端 | P0 |
| BR-16 | FR-UI-02 | 图标巧克力色荷兰侏儒兔 | P0 |
| BR-17 | §4 | DeepSeek/Tushare/Kimi K3 选型落地 | P0 |

---

## 10. 非功能需求与配置

### 10.1 非功能需求 `[TRACE: prd.md §5]`

| 编号 | 维度 | 要求 |
|---|---|---|
| NFR-01 | 隐私 | 全部数据本地存储；仅 LLM 推理外联 DeepSeek，可配本地模型替代 |
| NFR-02 | 双端兼容 | Win10+ / macOS 12+ 一致体验 |
| NFR-03 | 性能 | 全量 A 股采集可在一晚完成；评分/评级纯函数毫秒级 |
| NFR-04 | 稳定性 | 单股/单源/单渠道失败不拖垮整体 |
| NFR-05 | 可观测 | Agent 执行链、token、耗时、失败原因落盘可查 |
| NFR-06 | 可扩展 | 数据源、推送渠道、Agent 插件式扩展 |
| NFR-07 | 配置化 | 路径/超时/模型/限流/阈值均可配，禁止硬编码 |
| NFR-08 | 安全 | `.env` 不入库；`.env.example` 同步；密钥不明文日志 |
| NFR-09 | 可测试 | 纯逻辑单测全覆盖；I/O 集成测试；CI 阻断 lint/编译错误 |
| NFR-10 | 文档 | 字段契约/评分规则/Prompt/架构决策与代码同步 |

### 10.2 配置项（`.env.example` 必须同步）

```dotenv
DEEPSEEK_API_KEY=            # LLM 密钥
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
TUSHARE_TOKEN=               # Tushare Pro token（注册 tushare.pro 获取；vip 接口需 5000 积分）
DATA_DIR=data                # 数据根目录
CONCURRENCY=4                # 采集并发
TUSHARE_RATE_LIMIT=500       # 每分钟调用上限（5000积分=500次/分；2000积分=200次/分）
CACHE_TTL_HOURS=24          # "最新"缓存有效期（小时），过期重采以获取新报告期；0=永不过期
HOTSPOT_CRON_09=0 9 * * *
HOTSPOT_CRON_17=0 17 * * *
PORTFOLIO_CRON_09=0 9 * * *
PORTFOLIO_CRON_17=0 17 * * *
SMTP_HOST= / SMTP_PORT= / SMTP_USER= / SMTP_PASS=
WECHAT_PUSH_ENABLED=false
LLM_LOCAL_FALLBACK=false     # 是否启用本地模型兜底
```

### 10.3 部署形态

- 本地运行：`uv run python src/main.py` 或桌面端启动拉起 FastAPI。
- 定时任务：APScheduler 内嵌；亦可系统 cron。
- 打包：桌面端一键安装包（Win/Mac）。

---

## 11. 接口与 UI

### 11.1 FastAPI 路由（初版）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/chat` | 对话入口（SSE 流式） |
| POST | `/pipeline/run` | 触发采集/评分/评级/报告全流程 |
| GET | `/report/{date}` | 获取荐股/持仓/热点报告 |
| POST | `/portfolio` | 录入/更新持仓 |
| GET | `/hotspot/{date}` | 获取热点分析 |
| GET | `/health` | 健康检查 |

### 11.2 桌面端（apps/desktop）

- 技术栈：Electron + React + Vite，套壳本地 FastAPI。
- 设计参考：openclaw 桌面端交互 + Kimi K3 视觉风格。
- 图标：巧克力色荷兰侏儒兔，提供 `.ico`（Win）与 `.icns`（Mac）。
- 主界面分区：对话区 + 报告区 + 持仓区 + 热点区 + 监控区。
- UI 明示"数据本地存储，不上传云端"。
- 双端打包配置收敛到 `manifests/`。

---

## 12. 验证门禁与交付标准

### 12.1 验证门禁（CI 阻断）

| 检查项 | 命令 | 阻断 |
|---|---|---|
| Lint | `uv run ruff check .` | 是 |
| 类型/编译 | `uv run python -m py_compile <changed_files>` | 是 |
| 单元测试 | `uv run pytest -m "not network"` | 是 |
| 纯函数边界单测 | 评分/评级阈值边界全覆盖 | 是 |
| 配置同步 | 新增配置项须同步 `.env.example` | 是 |

### 12.2 交付标准（来自 coding.md）

- 单 PR 单功能，≤ 20 文件，超出须说明原因。
- PR 描述含：改动目的与背景 / 内容摘要 / 验证方式（命令/截图）/ 未验证项 / 风险点 / 回滚方式。
- 提交者自测确保本地通过。
- 不含构建产物（`__pycache__/`、`*.pyc`、`node_modules/`、`build/`、`dist/` 等）。
- `.env` 不入库。

### 12.3 验收清单（DoD）

- [ ] BRD step1~step4 全流程可一键跑通并产出对应 csv。
- [ ] 采集数据为最新报告期（`integrated_tests/test_smoke_collect.py` 交叉校验通过）。
- [ ] 评分/评级纯函数单测覆盖全部阈值边界（8.5/7.0/5.5 等）。
- [ ] 一票否决剔除公司记录可审计（`-否决.csv`）。
- [ ] 热点/持仓定时任务按 09:00/17:00 触发并推送。
- [ ] 桌面端 Win/Mac 可安装运行，可对话交互。
- [ ] 图标为巧克力色荷兰侏儒兔风格。
- [ ] 数据全部本地存储，`.env` 不入库。
- [ ] `docs/` 与代码同步。
- [ ] `CHANGELOG.md` 按 Keep a Changelog 维护，SemVer。
- [ ] CI（ruff lint + pytest）通过。

---

## 13. 里程碑

`[TRACE: prd.md §10, brd-1.md §11]`

| 里程碑 | 范围 | 验收 |
|---|---|---|
| M0 工程骨架 | 目录/AGENTS.md/pyproject/Settings/CI | `uv run pytest` 骨架用例通过 |
| M1 数据采集 | DataAgent + Tushare 适配 + 字段落地 | 随机 5 股采集成功，csv 字段齐全 |
| M2 评分评级 | 纯函数 + 单测 + 行业权重 + 否决 | 阈值表单测全覆盖；`-评分`/`-评级` csv 产出 |
| M3 报告输出 | 荐股 Top20 + 持仓表 + AI 点评 | `data/analysis/荐股.csv` 生成 |
| M4 多 Agent 编排 | RouterAgent + ChatAgent + LangGraph + 记忆/RAG | 对话可触发各 Agent |
| M5 热点+持仓监控+推送 | HotspotAgent + PortfolioAgent + 邮件/微信 | 定时任务与推送链路打通 |
| M6 桌面端 UI | Electron + React 双端 + 图标 + 打包 | Win/Mac 可安装运行 |
| M7 监控与反馈 | 执行链落盘 + UI 监控区 + 反馈库 | 监控可查、反馈可写 |

---

## 14. 风险与待定事项

### 14.1 风险

| 编号 | 风险 | 影响 | 等级 | 缓解 |
|---|---|---|---|---|
| R-01 | 投资建议合规与法律风险 | 误导用户/合规追责 | 高 | 明示"仅供参考，不构成投资建议"；免责声明；评审通过后上线 |
| R-02 | 评分规则业务合理性 | 结论失真 | 高 | 三人业务评审冻结阈值；RAG 对齐；反馈迭代 |
| R-03 | Tushare 积分/限流 | 采集中断 | 中 | 限流+缓存+续采；提示补积分 |
| R-04 | LLM 幻觉 | 点评失真 | 中 | 关键决策走规则引擎；LLM 仅文案并由规则校验 |
| R-05 | 热搜来源不可访问 | 热点失效 | 中 | 多来源 fallback；失败不拖垮主流程 |
| R-06 | 财报口径变更 | 字段漂移 | 中 | 字段契约文档 + 集成测试固定样本对齐 |
| R-07 | 双端打包差异 | 体验不一致 | 低 | 共享 UI，平台差异收敛到 `manifests/` |
| R-08 | 知识产权保护缺失 | 资产外流 | 中 | 待定知识产权策略 |
---

## 15. 决策优先级与冲突解决

AI Agent 在不确定时按以下优先级决策：

1. **RIGID 契约优先**：§8 全部规则不可漂移，与代码冲突时修代码不修规则（除非业务评审通过并记录于 `CHANGELOG.md`）。
2. **业务评审冻结值优先**：评审通过的阈值/权重覆盖本文档区间默认值。
3. **代码现状优先**：文档与代码不一致时，以实际可执行内容为准，并顺手修正文档避免漂移。
4. **稳定性优先**：非当前任务直接需要的重构/抽象一律克制。
5. **最小改动优先**：只做当前任务直接相关的最小改动，不顺手夹带无关重构。
6. **配置优于硬编码**：路径/超时/模型/阈值走 `Settings`。
7. **纯逻辑优先单测**：纯函数加单测，I/O 走集成测试。
8. **本地优先**：除 LLM 推理外不外联，数据不外传。

**冲突溯源**：业务规则以 [brd-1.md](./brd-1.md) §7 为准；产品实现以 [prd.md](./prd.md) 为准；本文件为合并工程视图。

---

## 16. 参考资料

- 业务需求：[brd-1.md](./brd-1.md)
- 产品需求：[prd.md](./prd.md)
- 原始草案：[brd.md](./brd.md)
- 开发日志：[dev-log.md](./dev-log.md)
- 工程规范：`coding.md`、`AGENTS.md.md`
- 规范仓库：`qtcloud-devops-main`、`qtcloud-course-main`
- 架构灵感：`openclaw-main`
- 功能灵感：`OpenBB-develop`、`daily_stock_analysis-main`、`Vibe-Trading-main`、`TradingAgents-CN-main`
