---
tags: [roadmap, 路线图]
status: active
version: 1.2.0
date: 2026-07-23
依据: [dev-guide.md](./dev-guide.md) §9 功能需求清单 + §13 里程碑 + §12 验证门禁
---

# alpha-jerry 项目工程路线图

> 基于 [dev-guide.md](./dev-guide.md) 生成，可追溯需求（每步标注实现 BR-/FR-），步骤按严格开发逻辑顺序。
> 每个断点提交后直接 `git push origin main`（不开分支、不开 PR）；main 永远保持可用基线，出问题用 `git revert` 回滚。

## M0 工程骨架

- 实现需求：工程基线（支撑全部 FR/NFR）

### Step 0-1 初始化仓库与基础文件

- 涉及文件：`.gitignore`、`README.md`、`CHANGELOG.md`
- [x] 操作：在项目根目录初始化 git，创建 `.gitignore`、`README.md`、`CHANGELOG.md`。
- [x] 测试/验收：仓库可提交。

### Step 0-2 依赖管理与工具配置

- 涉及文件：`pyproject.toml`、`uv.lock`、`.env.example`
- [x] 操作：用 `uv` 初始化 Python 项目，配置 `pyproject.toml`（含 `[build-system]` hatchling 构建，使 `uv run python scripts/*.py` 无需设 `PYTHONPATH`），加入 ruff（格式/检查）与 pytest（测试）。
- [x] 测试/验收：`uv sync` 成功，`uv run ruff check .` 无警告。

### Step 0-3 目录骨架与配置入口

- 涉及文件：`AGENTS.md`、`src/config.py`、`src/__init__.py`、`src/main.py`、`.env.example`
- [x] 操作：按 dev-guide §5 创建源码目录结构；写 `AGENTS.md`（项目级 AI 行为规范）；写 `src/config.py` 的 `Settings` 类雏形与 `.env.example`；建 `src/main.py` 作为运行入口（dev-guide §10.3）。
- [x] 测试/验收：`uv run python -c "from src.config import Settings; print(Settings())"` 可加载。

### Step 0-4 CI 门禁与第一个骨架测试

- 涉及文件：`.github/workflows/ci.yml`、`tests/test_skeleton.py`
- [x] 操作：加 GitHub Actions workflow（`ruff format --check .` + `ruff check .` + `pytest -m "not network"`），写一个最简单的骨架测试让 CI 有东西可跑。
- [x] 测试/验收：CI 跑通 format + lint + pytest。

---

## M1 数据采集

- 实现需求：BR-01/02 · FR-DATA-01~10 · FR-UPDATE-02/03（季度基本面/月度资金面更新）· NFR-03（全量 A 股采集可一晚完成）
- 目标：能从 Tushare 采集 A 股财务数据并落地为 `data/fin/YYMMDD.csv`。支持两种模式：逐股（增量/持仓）与批量（首次全量/季度财报季全量刷新）。
- 验收：5 股冒烟通过 + 全量批量采集产出 `data/fin/YYMMDD.csv`（≥5000 行），csv 字段对齐 dev-guide §8.1。

### Step 1-1 数据源抽象与字段模型

- 涉及文件：`src/data/contract.py`、`src/data/provider.py`、`tests/data/test_contract.py`
- 实现 BR-01
- 实现 FR-DATA-01、FR-DATA-08
- [x] 操作：在 `src/data/provider.py` 定义 `BaseFetcher` 抽象接口 + `TUSHARE_INTERFACES` 接口注册表；在 `src/contract.py` 定义 `StockFeatures`（44 列）+ `REQUIREMENT_ALIGNMENT`（53 需求对齐）+ `SUPPLEMENTARY_FIELDS`（3 个）。
- [x] 测试/验收：`uv run pytest tests/data/test_contract.py` 通过。

### Step 1-2 Tushare 适配器与限流重试

- 涉及文件：`src/data/provider.py`、`.env`、`tests/data/test_provider.py`
- 实现 BR-01
- 实现 FR-DATA-03、FR-DATA-04、FR-DATA-07
- [x] 操作：实现 `src/data/provider.py`，含限流器（每分钟调用上限）与指数退避重试（FR-DATA-07）
- [x] 测试/验收：`uv run pytest tests/data/test_provider.py`（mock 网络）通过；限流/重试/token 缺失报错均覆盖。

### Step 1-3 采集编排、缓存与失败隔离

- 涉及文件：`src/data/collect.py`、`src/data/output.py`、`tests/data/test_collect.py`
- 实现 BR-02
- 实现 FR-DATA-05、FR-DATA-06
- 学习点：**低并发线程池**（A 股 5000+ 只，不能一次性全请求，用线程池控制并发数如 4）；**缓存键 = 股票代码 + 报告期**（同季重跑不重复调接口，省积分）；**失败隔离**（一只出错不能拖垮整体，记下来后续采）。
- [x] 操作：在 `src/data/collect.py` 写采集主流程——读全量清单 → 低并发线程池采集 → 缓存原始响应 → 字段标准化；单股失败入 `data/fin/YYMMDD-失败.csv`。
- [x] 测试/验收：`uv run pytest tests/data/test_collect.py`（mock 数据源）通过。

### Step 1-4 随机 5 股冒烟测试与 csv 落地

- 涉及文件：`scripts/smoke_collect.py`、`src/data/output.py`、`integrated_tests/test_smoke_collect.py`、`src/data/collect.py`、`tests/data/test_collect.py`、`src/data/provider.py`
- 实现 BR-02
- 实现 FR-DATA-09、FR-DATA-10
- [x] 操作：
  - [x] 写脚本随机选 5 股真实采集
  - [x] 所属行业列构建策略更新：通过 `index_member_all` 接口按 ts_code 查询申万二级行业，映射到五大类（周期资源/大消费/证券金融/科技制造/公用事业基建），缓存到 `data/ref/sw_industry.csv`。纯映射见 `src/data/provider.py`（~130 个 SW L2 行业→5 大类，含罗马数字后缀剥离）。数据链：`ts_code → index_member_all(ts_code, is_new='Y') → l2_name → sw_l2_to_category() → 5大类`。仅在采集范围内按需查询 API，增量写缓存
  - [x] 采用最新报告期的数据（`end_date` 锁定 income 报告期 + 缓存 TTL，集成测试 `test_smoke_regenerates_latest_csv` 交叉校验 end_date）
  - [x] csv 字段为真实字段名，翻译为准确中文，增强可读性
  - [x] csv 中所有字段在数值中放弃科学计数法，匹配合适的汉字单位，按数据来源 CSV 中记录的单位逐字段追加后缀，并保留两位小数
  - [x] 单列一个 csv 列出采用的：接口、字段、字段对应中文、该接口/字段对应的文档 URL，形如 `YYMMDD-数据来源.csv`
  - [x] 生成的 csv 在 data 的 test 文件夹，形如 `YYMMDD.csv`
  - [x] 集成测试代码对齐`scripts/smoke_collect.py`、`src/data/output.py`、`ROADMAP.md`、`dev-guide.md`
- [x] 测试/验收：`uv run python scripts/smoke_collect.py --sample 5`；`uv run pytest -m network integrated_tests/`（交叉校验 end_date 为 Tushare 最新）；打开生成的 csv 人工确认。

### Step 1-5 全量批量采集与性能策略

- 涉及文件：`src/data/provider.py`（新增 `fetch_financials_batch`）、`src/data/collect.py`（新增 `run_batch`）、`scripts/full_collect.py`、`scripts/sw_industry.py`、`integrated_tests/test_full_collect.py`、`.env.example`
- 实现 BR-02
- 实现 FR-DATA-09、FR-DATA-10、NFR-03
- [x] 操作：
  - [x] **Provider 层**：`TushareFetcher` 加 `fetch_financials_batch(period)` + `_call_paginated`——调用 4 个 VIP 接口时只传 `period` 不传 `ts_code`，拿全市场数据，返回 `dict[str, StockFeatures]`。分页由 `_call_paginated` 按 `offset/limit` 循环拉取直到返回数 < 上限。数值 NaN → None 归一化同上。
  - [x] **Pipeline 层**：`CollectionPipeline` 加 `run_batch(period)`——调用 `fetch_financials_batch` 获取全量特征，回填 stock_basic 与 SW 行业分类，返回 `CollectionResult`（含 failures）。**流式分批写 CSV、进度条（`已处理 2500/5200 …`）、断点续采（`--resume`）等 I/O 操作不在 Pipeline 内部，由 `scripts/full_collect.py` 负责**，保持采集编排与落盘分离。
  - [x] **模式选择**：增量更新走逐股模式（`run(codes=[...])`），全量批量走 `run_batch()`。`scripts/full_collect.py` 通过 `--mode batch|per-stock` 切换（默认 batch）。两种模式对同一股票产出的 StockFeatures 已通过 mock 单测 cross-validate 断言一致（`test_full_collect.py:155-164`）。
  - [x] **配置**：`.env.example` 和 `Settings` 已加 `BATCH_SIZE=500`（流式写盘批次行数）和 `VIP_PAGE_SIZE=5000`（VIP 分页每页行数）。`PERF_MODE` 已声明（low/mid/high）但暂未接入代码控制并发/批次。
  - [x] **脚本**：`scripts/full_collect.py`——支持 `--period` / `--mode batch|per-stock` / `--resume`，默认批量模式。**全量采集启动前自动检查 `data/ref/sw_industry.csv`，不存在则自动调用 `build_sw_cache()` 生成**（~11 分钟），之后再执行采集。`_run_batch()` 内流式分批写盘，`_run_per_stock()` 逐股线程池写盘，均支持断点。
  - [x] **SW 缓存预构建**：`scripts/sw_industry.py`——多线程并行查询全 A 股申万二级行业 → 五大类映射，落盘 `data/ref/sw_industry.csv`。首次 ~11 分钟，后续批量采集秒级命中。
  - [x] **性能参考**（mid 模式 / 5000 积分 / 中配 4 核 16G）：批量模式 ~2-5 分钟（4 次 VIP 调用 + 1 次 stock_basic + 流式写盘）。逐股模式 ~40-50 分钟（20000 次调用 / 500 次每分钟）。low 模式批量 ~5-10 分钟。2000 积分模式下批量仍 ~2-5 分钟（VIP 接口不占用常规额度），逐股模式延至 ~100 分钟。
- [x] 测试/验收（`integrated_tests/test_full_collect.py`）：
  - [x] **mock 测试（CI 可跑）**：`test_run_batch_collects_all_stocks`（全量批量） / `test_run_batch_fills_stock_info`（回填名称行业） / `test_run_batch_missing_stock_is_failure`（缺失记失败） / `test_run_batch_auto_period`（自动推算报告期） / `test_run_batch_no_batch_method_raises`（无批量方法报错） / `test_batch_matches_per_stock`（批量和逐股产出一致 cross-validate）
  - [x] **CSV 落地测试（CI 可跑）**：`test_full_collect_csv_structure`（44 列中文列头 + 百分比/亿万格式化） / `test_csv_resume_reads_existing`（断点续采读已有 ts_code） / `test_csv_resume_empty_csv` / `test_csv_resume_no_file`
  - [x] **network 测试（`-m network`）**：`test_real_batch_collects_all_stocks`（真实全量采集 ≥5000 股 + 产出落 `data/test/full_collect_test.csv` 自动覆盖） / `test_batch_vs_per_stock_cross_validate`（3 股逐字段比对）
  - [x] `uv run python scripts/full_collect.py`——命令行跑通，产出 `data/fin/YYMMDD.csv`

---

## M2 评分评级

- 实现需求：BR-03/04/05 · FR-SCORE-01~09 · FR-RATE-01~04
- 目标：把 dev-guide §8 的业务规则（一票否决、三维评分、行业权重、综合分、评级）落地为纯函数 + 单测。
- 验收：阈值表单测全覆盖；`-评分`/`-评级` csv 产出。

### Step 2-1 三维评分纯函数 + 单测

- 涉及文件：`src/scoring/growth.py`、`src/scoring/stability.py`、`src/scoring/return.py`、`tests/test_scoring_growth.py`、`tests/test_scoring_stability.py`、`tests/test_scoring_return.py`
- 实现 BR-04
- 实现 FR-SCORE-02~05
- 学习点：**纯函数** = 给相同输入永远得相同输出，不碰网络/文件/时间。这种函数最好测、最不易出 bug。dev-guide §6.3 原则 4 要求评分必须纯函数。**边界值测试**：如 8.5、7.0、5.5 这些临界点最容易出错，必须专门测。
- [ ] 操作：在 `src/scoring/` 实现成长性/稳健性/资金回报三个评分纯函数（dev-guide §8.3），每个阈值表配单测覆盖区间边界。
- [ ] 测试/验收：`uv run pytest tests/test_scoring_growth.py tests/test_scoring_stability.py tests/test_scoring_return.py`。
- 断点提交：
  ```bash
  git add src/scoring/growth.py src/scoring/stability.py src/scoring/return.py tests/test_scoring_*.py
  git commit -m "feat(scoring): 三维评分纯函数"
  ```

### Step 2-2 行业权重、综合分与一票否决

- 涉及文件：`src/scoring/weights.py`、`src/scoring/composite.py`、`src/scoring/veto.py`、`tests/test_scoring_weights.py`、`tests/test_scoring_composite.py`、`tests/test_scoring_veto.py`
- 实现 BR-03、BR-04
- 实现 FR-SCORE-01、FR-SCORE-06、FR-SCORE-07
- 学习点：权重以区间给出时取中点为默认值，可被 `Settings` 覆盖（dev-guide §8.4 备注）。一票否决是"硬性风险"，触发即剔除但必须留审计记录（可追溯）。
- [ ] 操作：实现行业权重对照表（§8.4）、综合分公式（§8.5）、一票否决（§8.2）；否决记录入 `data/fin/YYMMDD-否决.csv`。
- [ ] 测试/验收：`uv run pytest tests/test_scoring_weights.py tests/test_scoring_composite.py tests/test_scoring_veto.py`。
- 断点提交：
  ```bash
  git add src/scoring/weights.py src/scoring/composite.py src/scoring/veto.py tests/test_scoring_*.py
  git commit -m "feat(scoring): 行业权重、综合分与一票否决"
  ```

### Step 2-3 评级纯函数与边界单测

- 涉及文件：`src/rate.py`、`tests/test_rating_rate.py`
- 实现 BR-05
- 实现 FR-RATE-01
- 学习点：`<5.5` 是垃圾、`5.5` 是鸡肋·观察——这种"等号归哪边"的细节最易写错，单测要明确断言。
- [ ] 操作：在 `src/` 实现评级映射（§8.6），单测覆盖 8.5 / 7.0 / 5.5 三个临界值归属。
- [ ] 测试/验收：`uv run pytest tests/test_rating_rate.py`。
- 断点提交：
  ```bash
  git add src/rate.py tests/test_rating_rate.py
  git commit -m "feat(rating): 评级映射与边界单测"
  ```

### Step 2-4 评分评级串联 csv 落地

- 涉及文件：`src/data/collect.py`（扩展）、`src/data/output.py`（扩展）、`integrated_tests/test_score_rate.py`
- 实现 BR-05
- 实现 FR-RATE-02~04、FR-SCORE-08、FR-SCORE-09
- 学习点：**追加字段不破坏原字段**是数据契约的稳定性要求（dev-guide §15 决策优先级），下游消费方才不会突然崩。
- [ ] 操作：把评分与评级串进 pipeline，输出 `data/fin/YYMMDD-评分.csv` 与 `data/fin/YYMMDD-评级.csv`，保留全部原始字段（追加新列）。
- [ ] 测试/验收：用 M1 的 5 股样本跑全流程，检查两个 csv 生成且评级列正确。
- 断点提交：
  ```bash
  git add src/data/collect.py src/data/output.py integrated_tests/test_score_rate.py
  git commit -m "feat(rating): 评分评级串联并落地csv"
  ```

> 🎯 **M2 验收**：`uv run pytest` 全绿；5 股样本产出 `-评分`/`-评级`/`-否决` csv。

---

## M3 报告输出

- 实现需求：BR-06/07 · FR-REPORT-01~07
- 目标：生成荐股 Top20 报告与持仓表，含 AI 亮点与点评。
- 验收：`data/analysis/YYMMDD-荐股.csv` 生成。

### Step 3-1 公司类型、行业分类与操作建议

- 涉及文件：`src/company_type.py`、`src/data/provider.py`、`src/advice.py`、`tests/test_rating_company_type.py`、`tests/test_rating_industry.py`、`tests/test_rating_advice.py`
- 实现 BR-06
- 实现 FR-REPORT-02、FR-REPORT-03、FR-REPORT-04
- [ ] 操作：实现公司类型（千里马/现金牛/护城河，§8.7）、行业分类（§8.8）、评级→操作建议映射（§8.9）。
- [ ] 测试/验收：`uv run pytest tests/test_rating_*.py`。
- 断点提交：
  ```bash
  git add src/company_type.py src/data/provider.py src/advice.py tests/test_rating_*.py
  git commit -m "feat(report): 公司类型、行业分类与操作建议"
  ```

### Step 3-2 荐股 Top20 与持仓表生成

- 涉及文件：`src/reports/picks.py`、`src/reports/portfolio.py`、`integrated_tests/test_reports.py`
- 实现 BR-06、BR-07
- 实现 FR-REPORT-01、FR-REPORT-05、FR-REPORT-06
- 学习点：核心亮点（≤30 字）与点评（≤50 字）由 LLM 生成，但**关键决策走规则引擎**，LLM 只写文案并由规则校验（风险 R-04 缓解）。
- [ ] 操作：按综合分降序取 Top20，渲染荐股表（字段见 §8.10）；支持对话录入持仓生成 `data/hold/YYMMDD.csv`。
- [ ] 测试/验收：5 股样本扩展到足够数量后生成荐股表；检查字段齐全。
- 断点提交：
  ```bash
  git add src/reports/picks.py src/reports/portfolio.py integrated_tests/test_reports.py
  git commit -m "feat(report): 荐股Top20与持仓表生成"
  ```

### Step 3-3 字段契约与 Prompt 文档

- 涉及文件：`docs/dev-guide.md`（§8.1 字段契约）、`docs/prompt-library.md`
- 实现 BR-06
- 实现 FR-REPORT-07
- 学习点：文档与代码同步是工程基本功（NFR-10）。字段口径写不清，下游（包括你自己三个月后）会反复踩坑。
- [x] 操作：字段计算口径已合并入 `docs/dev-guide.md` §8.1，无需单独的 `data-contract.md`；待补 `docs/prompt-library.md`（亮点/点评 Prompt 模板）。
- [ ] 测试/验收：人工核对字段口径与代码一致。
- 断点提交：
  ```bash
  git add docs/prompt-library.md
  git commit -m "docs: Prompt文档"
  ```

> 🎯 **M3 验收**：step1~step4 全流程一键跑通并产出 csv（dev-guide §12.3 DoD 第 1 条）。

---

## M4 多 Agent 编排

- 实现需求：BR-12/14/17 · AR-*（§7）· FR-CHAT-01~05
- 目标：把单线 pipeline 升级为多 Agent 编排，支持自然语言对话驱动。
- 验收：对话可触发各 Agent。

### Step 4-1 LLM 适配层与 DeepSeek 接入

- 涉及文件：`src/agents/llm_adapter.py`、`.env.example`（补 `DEEPSEEK_*`，对齐 §10.2）、`tests/test_llm_adapter.py`
- 实现 BR-14
- 实现 FR-CHAT-04
- 学习点：把 LLM 调用收进一个适配层，业务代码不直接依赖某家 SDK，换模型只改适配层（依赖倒置）。
- [ ] 操作：在 `src/agents/llm_adapter.py` 封装 DeepSeek（OpenAI 兼容接口），统一 provider 接口，便于未来切换。
- [ ] 测试/验收：写一个 mock 测试 + 一个真实调用冒烟（标 `@pytest.mark.network`，CI 不跑）。
- 断点提交：
  ```bash
  git add src/agents/llm_adapter.py .env.example tests/test_llm_adapter.py
  git commit -m "feat(llm): DeepSeek适配层"
  ```

### Step 4-2 RAG 知识库

- 涉及文件：`src/rag/store.py`、`src/rag/indexer.py`、`src/rag/retriever.py`、`tests/test_rag_retriever.py`
- 实现 BR-12
- 实现 AR-RAG（§7.2）
- 学习点：RAG = 检索增强生成。Agent 决策前先检索知识库对齐规则，防止 LLM"幻觉"导致评分漂移。向量库本地存储，符合 local-first（NFR-01）。
- [ ] 操作：用 ChromaDB + bge-small-zh 把行业对照表、否决规则、评分阈值、行业分类逻辑入库（dev-guide §7.2 RAG 要素）。
- [ ] 测试/验收：`uv run pytest tests/test_rag_retriever.py`。
- 断点提交：
  ```bash
  git add src/rag/ tests/test_rag_retriever.py
  git commit -m "feat(rag): 本地知识库构建"
  ```

### Step 4-3 RouterAgent 与 Agent 编排

- 涉及文件：`src/agents/router.py`、`src/agents/data_agent.py`、`src/agents/scoring_agent.py` 等、`src/agents/graph.py`、`tests/test_agents_router.py`
- 实现 BR-12、BR-17
- 实现 AR-Router（§7.1）
- 学习点：**路由 = 意图分类 + 分发**。RouterAgent 先判断用户想干嘛（采集？评分？看报告？），再交给对应 Agent。无法识别时回退 ChatAgent。决策要可日志回溯。
- [ ] 操作：用 LangGraph 实现 RouterAgent（意图路由 + 规则兜底）与各业务 Agent（Data/Scoring/Rating/Report），组装状态机（dev-guide §7.1）。
- [ ] 测试/验收：`uv run pytest tests/test_agents_router.py`。
- 断点提交：
  ```bash
  git add src/agents/router.py src/agents/data_agent.py src/agents/scoring_agent.py src/agents/graph.py tests/test_agents_router.py
  git commit -m "feat(agents): 路由与Agent编排"
  ```

### Step 4-4 ChatAgent、记忆与流式对话 API

- 涉及文件：`src/agents/chat_agent.py`、`src/agents/memory.py`、`api/routes/chat.py`、`tests/test_chat.py`
- 实现 BR-14
- 实现 FR-CHAT-01、FR-CHAT-02、FR-CHAT-03、FR-CHAT-05
- 学习点：**SSE（Server-Sent Events）** 让对话"一个字一个字蹦出来"，体验远好于等整段返回。记忆分层让 Agent 跨会话记得你的持仓与偏好。
- [ ] 操作：实现 ChatAgent + 分层记忆（短期会话/长期偏好/RAG）；加 `POST /chat`（SSE 流式，§11.1）。
- [ ] 测试/验收：本地起服务，用 curl 测 `/chat` 能流式返回。
- 断点提交：
  ```bash
  git add src/agents/chat_agent.py src/agents/memory.py api/routes/chat.py tests/test_chat.py
  git commit -m "feat(chat): 记忆与流式对话API"
  ```

> 🎯 **M4 验收**：自然语言可触发采集/评分/报告。

---

## M5 热点追踪 + 持股监控 + 推送

- 实现需求：BR-08/09/10/11 · FR-HOTSPOT-01~05 · FR-PORT-01~05 · FR-PUSH-01~05 · FR-UPDATE-01
- 目标：每日 09:00/17:00 自动跑热点与持仓分析并推送。
- 验收：定时任务与推送链路打通。

### Step 5-1 定时调度器

- 涉及文件：`src/scheduler/scheduler.py`、`.env.example`（补 cron 配置，对齐 §10.2）、`tests/test_scheduler.py`
- 实现 BR-11
- 实现 FR-UPDATE-01
- 学习点：cron 表达式 `0 9 * * *` = 每天 9 点。把触发时间放配置，不硬编码（NFR-07）。
- [ ] 操作：用 APScheduler 实现 09:00/17:00 触发（dev-guide §10.2 cron 配置：`HOTSPOT_CRON_09`/`PORTFOLIO_CRON_09` 等）。
- [ ] 测试/验收：把 cron 改成 1 分钟后触发，观察日志。
- 断点提交：
  ```bash
  git add src/scheduler/ tests/test_scheduler.py
  git commit -m "feat(scheduler): 09/17定时任务"
  ```

### Step 5-2 HotspotAgent 热点追踪

- 涉及文件：`src/agents/hotspot_agent.py`、`src/data/hot_search_fetcher.py`、`tests/test_hotspot_agent.py`
- 实现 BR-08
- 实现 FR-HOTSPOT-01~05
- 学习点：热搜来源不稳定，要多来源 fallback，单个失败不拖垮（风险 R-05）。
- [ ] 操作：采 Top10 热搜（百度/微博/东财）→ LLM 识别受益行业 → RAG 映射个股 Top5，落 `data/hot/`。
- [ ] 测试/验收：`uv run pytest tests/test_hotspot_agent.py`。
- 断点提交：
  ```bash
  git add src/agents/hotspot_agent.py src/data/hot_search_fetcher.py tests/test_hotspot_agent.py
  git commit -m "feat(hotspot): 热点追踪Agent"
  ```

### Step 5-3 PortfolioAgent 持股监控

- 涉及文件：`src/agents/portfolio_agent.py`、`tests/test_portfolio_agent.py`
- 实现 BR-09
- 实现 FR-PORT-01~05
- [ ] 操作：重爬重算持仓 → 风险高亮（一票否决触发）→ 趋势对比（与上次评分差值）→ 操作建议（持有/加仓/减仓/止损），输出 `data/hold/YYMMDD-09.csv`/`-17.csv`。
- [ ] 测试/验收：`uv run pytest tests/test_portfolio_agent.py`。
- 断点提交：
  ```bash
  git add src/agents/portfolio_agent.py tests/test_portfolio_agent.py
  git commit -m "feat(portfolio): 持股监控Agent"
  ```

### Step 5-4 推送通知（邮件/微信）

- 涉及文件：`src/notifications/email_notifier.py`、`src/notifications/wechat_notifier.py`、`.env.example`（补 `SMTP_*`/`WECHAT_PUSH_ENABLED`，对齐 §10.2）、`tests/test_notifications.py`
- 实现 BR-10
- 实现 FR-PUSH-01~05
- 学习点：**单渠道失败不拖垮整体**是稳定性护栏（NFR-04）。邮件挂了不能让整个分析流程崩。
- [ ] 操作：邮件发完整 HTML 表格，微信发摘要（可选）；单渠道失败不拖垮主流程（FR-PUSH-05）。
- [ ] 测试/验收：配置 SMTP 后真实发一封测试邮件。
- 断点提交：
  ```bash
  git add src/notifications/ tests/test_notifications.py
  git commit -m "feat(notify): 邮件与微信推送"
  ```

> 🎯 **M5 验收**：09:00/17:00 自动跑并推送（DoD 第 4 条）。

---

## M6 桌面端 UI

- 实现需求：BR-13/15/16 · FR-UI-01~07 · NFR-01/02
- 目标：Win/Mac 双端桌面应用可安装运行、可对话。
- 验收：Win/Mac 可安装运行。

### Step 6-1 FastAPI 路由完善

- 涉及文件：`api/routes/*.py`
- 实现 BR-15
- 实现 FR-UI-01
- [ ] 操作：补齐 dev-guide §11.1 剩余路由（`/chat` 已在 M4 完成）：`POST /pipeline/run`、`GET /report/{date}`、`POST /portfolio`、`GET /hotspot/{date}`、`GET /health`。
- [ ] 测试/验收：`uv run uvicorn api.app:app --reload`，逐个 curl 测。
- 断点提交：
  ```bash
  git add api/routes/
  git commit -m "feat(api): 补齐FastAPI路由"
  ```

### Step 6-2 Electron + React 骨架

- 涉及文件：`apps/desktop/` 全部
- 实现 BR-13、BR-15
- 实现 FR-UI-03
- 学习点：Electron = 用网页技术做桌面应用；它启动时拉起本地 FastAPI，前端通过 HTTP/SSE 调本地后端，数据不出本机（local-first）。
- [ ] 操作：在 `apps/desktop` 初始化 Electron + React + Vite，套壳本地 FastAPI；先做对话区与报告区。
- [ ] 测试/验收：`cd apps/desktop && npm run dev` 能打开窗口并对话。
- 断点提交：
  ```bash
  git add apps/desktop/
  git commit -m "feat(desktop): Electron+React骨架"
  ```

### Step 6-3 图标与完整仪表盘

- 涉及文件：`apps/desktop/assets/icon.*`、各页面组件
- 实现 BR-16
- 实现 FR-UI-02、FR-UI-07
- [ ] 操作：制作巧克力色荷兰侏儒兔图标（`.ico`/`.icns`，C-08，FR-UI-02）；补持仓区、热点区、监控区；UI 明示"数据本地存储"（FR-UI-07）。
- [ ] 测试/验收：视觉评审图标风格；四个区都能显示数据。
- 断点提交：
  ```bash
  git add apps/desktop/assets/ apps/desktop/src/
  git commit -m "feat(desktop): 图标与仪表盘区域"
  ```

### Step 6-4 Win/Mac 打包

- 涉及文件：`manifests/win.yml`、`manifests/mac.yml`、`apps/desktop/electron-builder.*`
- 实现 BR-13
- 实现 FR-UI-06
- 学习点：平台差异收敛到打包配置，UI 代码共享一份（风险 R-07 缓解）。
- [ ] 操作：在 `manifests/` 配置 Win（nsis/portable）与 Mac（dmg）打包（FR-UI-06）。
- [ ] 测试/验收：分别打出 Win 与 Mac 安装包并安装运行。
- 断点提交：
  ```bash
  git add manifests/ apps/desktop/electron-builder.yml
  git commit -m "build: Win/Mac打包配置"
  ```

> 🎯 **M6 验收**：双端可安装运行、可对话（DoD 第 5、6 条）。

---

## M7 监控与反馈

- 实现需求：BR-12（监控/反馈要素，§7.2）· NFR-05（可观测）
- 目标：Agent 执行可观测，用户反馈可收集迭代。
- 验收：监控可查、反馈可写。

### Step 7-1 Agent 执行链落盘与监控区

- 涉及文件：`src/agents/trace.py`、`apps/desktop/src/monitor/`
- 实现 BR-12
- 实现 NFR-05
- [ ] 操作：每次 Agent 执行记录 `agent_name / tools_called / tokens / latency / status / error`，落 `data/monitor/`；UI 监控区展示。
- [ ] 测试/验收：跑一次流程后监控区能看到执行链。
- 断点提交：
  ```bash
  git add src/agents/trace.py apps/desktop/src/monitor/
  git commit -m "feat(monitor): Agent执行链落盘"
  ```

### Step 7-2 用户反馈库

- 涉及文件：`src/agents/feedback.py`、`api/routes/feedback.py`
- 实现 BR-12
- [ ] 操作：点赞/修正入 `data/feedback/`，用于 Prompt 与评分校准迭代（dev-guide §7.2 反馈要素）。
- [ ] 测试/验收：UI 点赞后 `data/feedback/` 有记录。
- 断点提交：
  ```bash
  git add src/agents/feedback.py api/routes/feedback.py
  git commit -m "feat(feedback): 用户反馈库"
  ```

### Step 7-3 端到端验收与文档定稿

- 涉及文件：`README.md`、`CHANGELOG.md`、`docs/architecture.md`
- [ ] 操作：按 dev-guide §12.3 DoD 逐项核对；定稿 `README.md` 与 `CHANGELOG.md`、`docs/architecture.md`。
- [ ] 测试/验收：跑一遍 DoD 清单全部打勾。
- 断点提交：
  ```bash
  git add README.md CHANGELOG.md docs/architecture.md
  git commit -m "docs: 定稿CHANGELOG/README/架构文档"
  ```

> 🎯 **M7 验收**：DoD 全部打勾。

---

## 附：里程碑与提交总览

| 里程碑 | Step 数 | 提交数 | 需求覆盖（dev-guide §9） | 验收命令 | 推送方式 |
|---|---|---|---|---|---|
| M0 工程骨架 | 4 | 4 | 工程基线（支撑全部 FR/NFR） | `uv run pytest` | 直接推 main |
| M1 数据采集 | 5 | 5 | BR-01/02 · FR-DATA-01~10 · FR-UPDATE-02/03 · NFR-03 | 全量批量采集 + 5 股冒烟，csv 字段齐全 | 直接推 main |
| M2 评分评级 | 4 | 4 | BR-03/04/05 · FR-SCORE-01~09 · FR-RATE-01~04 | 阈值单测全覆盖；`-评分`/`-评级` csv | 直接推 main |
| M3 报告输出 | 3 | 3 | BR-06/07 · FR-REPORT-01~07 | step1~4 一键跑通 | 直接推 main |
| M4 Agent 编排 | 4 | 4 | BR-12/14/17 · AR-* · FR-CHAT-01~05 | 对话触发各 Agent | 直接推 main |
| M5 监控推送 | 4 | 4 | BR-08/09/10/11 · FR-HOTSPOT/PORT/PUSH · FR-UPDATE-01 | 09/17 定时 + 推送 | 直接推 main |
| M6 桌面端 | 4 | 4 | BR-13/15/16 · FR-UI-01~07 · NFR-01/02 | Win/Mac 可安装 | 直接推 main |
| M7 监控反馈 | 3 | 3 | BR-12（监控/反馈）· NFR-05 | DoD 全勾 | 直接推 main |

**合计**：31 个断点提交、8 个里程碑，全部直接推 main（不开分支、不开 PR），覆盖 dev-guide §9 全部 BR/FR。

---

## 附：断点学习小贴士

1. **每步只做一件事**：不要顺手改别的，保持 commit 干净，出问题好回滚（`git revert`）。
2. **提交前必验证**：`uv run ruff check . && uv run pytest -m "not network"` 是你的安全带。
3. **看不懂就停下来查**：每个 Step 的"学习点"是刻意写的，遇到陌生概念先搞懂再往下。
4. **用 `git log --oneline` 回顾**：定期看自己的提交历史，能直观看到成长轨迹。
5. **卡住了就回到上一个断点**：`git status` 看改动，`git checkout .` 丢弃未提交改动重试。
6. **提交说明按 dev-guide §12.2 写**：目的/摘要/验证/未验证项/风险/回滚——这是职业习惯，越早养成越好（不开 PR，所以写进 commit message）。
7. **对照需求覆盖**：每完成一个里程碑，回看本里程碑的「实现需求」行，确认对应 BR/FR 都已实现。
8. **断点即推送**：每完成一个 Step，`git commit` 后立即 `git push origin main`；main 永远保持可用基线，出问题用 `git revert` 回滚。

---

## 关联文档

- 总纲：[dev-guide.md](./dev-guide.md)（§9 功能需求清单 / §13 里程碑 / §12 验证门禁）
- 业务：[brd.md](./brd.md)
- 产品：prd.md（待补充）
- 日志：[dev-log.md](./dev-log.md)
