---
tags: [dev-guide, AGENTS]
date: 2026-07-28
---

# `AGENTS.md` 规范

- alpha-jerry 项目级 AI 行为规范配置文件，是为项目上下文入口
- 只放影响 AI 行为的指令，缺了就会做错或必须遵守的刚性规则
- `AGENTS.md` 冲突时以项目级优先（就近原则）；业务规则以 `docs/dev-guide.md` §8 为准

## 业务意图

alpha-jerry 是一套面向 A 股基本面分析的 AI Native 工具集，覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送"完整业务闭环。帮助个人投资者识别优质公司并持续监控持仓风险。

核心流程：全 A 股清单 → Tushare 采集财务数据(4 个 VIP 接口，~460 字段) → 一票否决剔除 → 三维评分(成长性/稳健性/资金回报) → 行业权重加权求综合分 → 四级评级(皇冠明珠/优秀白马/鸡肋·观察/垃圾) → 荐股 Top20 报告。

当前阶段：M2 评分评级已完成(290 项单测，覆盖率 99.4%)，M3 报告输出进行中(Step 3-1 公司类型+操作建议已完成)。

## 关键决策

1. **本地优先**：数据本地存储，不上传云端，仅 LLM 推理外联(NFR-01)。`data/` 目录不入库(`.gitignore` 已配置 `/data/`)。
2. **规则可审计**：评分/评级走纯函数 + 单测，一票否决可追溯。`docs/dev-guide.md` §8 全部 RIGID 规则不可漂移，冲突时改代码不修规则。
3. **数据源单一真源**：Tushare Pro 为唯一数据源，通过 `BaseFetcher` 抽象隔离业务代码(FR-DATA-01)。VIP 接口优先，不传 `fields` 取全量字段。
4. **纯逻辑与 I/O 分层**：`src/scoring/scores.py` 仅含纯函数，可离线单测；`src/data/` 含网络/文件 I/O，走集成测试。
5. **配置抽离**：路径/超时/模型/API Key/阈值全走 `pydantic-settings` 的 `Settings` 单例，禁止硬编码。新增配置项须同步 `.env.example`。
6. **能批量不逐股**：全量采集用 `run_batch()` 调用 VIP 接口 O(1) 拿全市场；逐股模式仅用于增量更新/冒烟测试。
7. **申万行业分类→五大类**：`ts_code → index_member_all → l2_name → sw_l2_to_category() → 五大类`，缓存落 `data/ref/sw_industry.csv`。
8. **报告期以 income 为准**：`end_date` 锁定 income 报告期，其余接口 end_date 不覆盖；`expected_latest_period()` 按法定披露截止日推算。

## 管道逻辑

```
stock_basic(全 A 股清单)
  → income_vip / balancesheet_vip / cashflow_vip / fina_indicator_vip (4 个 VIP 接口按 period 批量)
  → StockFeatures (pydantic extra=allow, ~460 字段)
  → check_veto() 一票否决
  → score_growth() / score_stability() / score_return() 三维评分
  → score_composite() 按行业权重加权 (五大类权重: 周期资源 25/35/40, 大消费 30/30/40, 证券金融 30/30/40, 科技/制造 50/20/30, 公用事业/基建 20/40/40)
  → score_rating() 四级评级 (8.5/7.0/5.5 三临界)
  → 输出 data/fin/scoring/YYMMDD.csv + -否决.csv
```

数据目录映射：`fin`(财务) / `analysis`(荐股) / `hold`(持股) / `hot`(热点) / `monitor`(监控) / `feedback`(反馈) / `rag`(知识库) / `ref`(参考数据) / `test`(测试产物)。

## Commands

- dependencies: `uv sync`
- test: `uv run pytest -m "not network"`
- lint: `uv run ruff check .`
- format: `uv run ruff format .`
- run: `uv run python src/main.py`
- full-collect: `uv run python scripts/full_collect.py`
- smoke-collect: `uv run python scripts/smoke_collect.py --sample 5`
- full-scores: `uv run python scripts/full_scores.py`
- sw-cache: `uv run python scripts/sw_industry.py`

## Stack

- Runtime: Python 3.12+
- Package Manager: uv
- Language: Python
- LLM: DeepSeek V4 Pro
- Data: Tushare Pro (vip 接口需 5000 积分: income_vip/balancesheet_vip/cashflow_vip/fina_indicator_vip)
- Agent Framework: LangGraph 0.2+
- RAG: ChromaDB + bge-small-zh (local)
- Backend API: FastAPI 0.110+
- Desktop: Electron + React + Vite
- Config: pydantic-settings + `.env`
- Test: pytest 8+ (mock + network 两组); Lint/Format: ruff

## Key Files

- `docs/dev-guide.md` — 单一事实来源(Single Source of Truth)，§8 为不可漂移的业务规则(RIGID)
- `docs/ROADMAP.md` — 工程路线图(M0-M7，每步标注实现 BR/FR 需求编号)
- `docs/brd.md` — 业务需求基线(BRD)，需求字段 55 项
- `src/config.py` — 全局配置入口(`get_settings()` 单例)，路径/超时/模型/密钥集中管理
- `pyproject.toml` — 依赖、工具配置、pytest/ruff 设置(行宽 120，引号样式 double)
- `src/data/contract.py` — 字段模型(StockFeatures + StockInfo)、53 需求对齐表、~460 输出列、FIELD_CN/FIELD_UNIT 全量字段映射
- `src/data/provider.py` — Tushare 适配器(20 接口注册表)、RateLimiter 限流、指数退避重试、SW 行业 5 大类映射(~130 行业)
- `src/data/collect.py` — 采集编排(Cache TTL + CollectionPipeline + run/run_batch)、报告期推算
- `src/scoring/scores.py` — 三维评分纯函数 + 综合分 + 一票否决 + 评级映射
- `.env.example` — 配置样板(新增配置项必须同步)

## Constraints

### 设计

- 单文件尽可能 300 行内，越少越好；`contract.py`(~2009 行)因全量字段映射为合理例外
- 不自造轮子，优先用项目中已有的工具库和代码
- 不可偏移 `docs/dev-guide.md`，与代码冲突时改代码不修规则
- 纯逻辑(评分/评级/权重)与 I/O(爬取/写盘)分层：纯逻辑单独单测，I/O 走集成测试
- 模块膨胀到 3+ 文件再升格为包，否则保持单文件扁平结构
- 单 PR 单功能，≤ 20 文件；每步提交后直接 `git push origin main`(不开分支、不开 PR)

### 安全

- 不阅读 `dev-log.md`、`.env`，需要配置值时通过 `Settings` 读取(如 `get_settings().tushare_token`)，仅查看长度/是否为空等非敏感属性，禁止 read/cat/print 其内容
- `.env` 不入库(NFR-08)，密钥不明文日志
- 数据本地存储，不上传云端(NFR-01)

### 代码

- 代码文件抬头三行注释简要写明该代码功能(参见 `src/config.py`、`src/data/contract.py` 等现有文件格式)
- 配置抽离：路径/超时/模型/API Key 全走 `Settings`，禁止硬编码
- 代码-测试-脚本-产物命名对齐统一，示例如下

| 层级 | 文件 |
|------|------|
| 源码 | `src/data/collect.py` |
| 测试 | `tests/data/test_collect.py` |
| 脚本 | `scripts/full_collect.py` |
| 产物 | `data/fin/full_collect/YYMMDD.csv` |

### 测试

- 编辑无论大小，立即运行 `uv run pytest -m "not network"`
- 只针对失败写修复，不提前假设
- 按功能/文件区逐个测试，产出物通过才能进行下一个开发
- 单元测试覆盖全部阈值边界(8.5/7.0/5.5 等)
- 单元测试行覆盖率 ≥ 80%(`--cov-fail-under=80`)，CI 门禁阻断
- 不允许对 `ROADMAP.md` 自动打勾，需人工打勾

## Verification

修改代码后必须运行：

1. `uv run ruff check .` — 无新警告
2. `uv run pytest -m "not network" --cov=src --cov-fail-under=80` — 测试通过，覆盖率 ≥ 80%
3. `uv run python -c "from src.config import Settings; print(Settings())"` — 配置可加载

`integrated_tests` 内文件必须运行：

1. `uv run ruff check .` — 无新警告
2. `uv run pytest -m network` — 联网测试检查产出物(需配置 TUSHARE_TOKEN)
