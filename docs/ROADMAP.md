---
tags: [roadmap, 路线图]
status: active
version: 2.3.0
date: 2026-07-28
依据: [dev-guide.md](./dev-guide.md) §9 功能需求清单 + §13 里程碑 + §12 验证门禁
---

# alpha-jerry 项目工程路线图

> 基于 [dev-guide.md](./dev-guide.md) 生成，可追溯需求（每步标注实现 BR-/FR-），步骤按严格开发逻辑顺序。
> 每个断点提交后直接 `git push origin main`（不开分支、不开 PR）；main 永远保持可用基线，出问题用 `git revert` 回滚。

## M0 工程骨架

- 实现需求：工程基线（支撑全部 FR/NFR）

### Step 0-1 初始化仓库与基础文件

- 涉及文件：`.gitignore`、`README.md`、`CHANGELOG.md`
- 实现 BR-*（工程基线）

- [x] 操作
  - [x] 在项目根目录初始化 git 仓库
  - [x] 创建 `.gitignore`（Python/Node/系统文件/密钥/数据目录）
  - [x] 创建 `README.md`（项目定位 + 快速开始 + 技术栈 + 免责声明）
  - [x] 创建 `CHANGELOG.md`（Keep a Changelog + SemVer 格式）
- [x] 测试
  - [x] `git status` 确认文件已创建
  - [x] 仓库可正常 `git add` 和 `git commit`
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（不适用，纯工程文件）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`.gitignore` / `README.md` / `CHANGELOG.md`）
  - [x] 本步骤产出物位置合规（项目根目录）
- [x] 提交
  - [x] `git commit -m "chore: 初始化仓库与基础文件"`

### Step 0-2 依赖管理与工具配置

- 涉及文件：`pyproject.toml`、`uv.lock`、`.env.example`
- 实现 BR-*（工程基线）

- [x] 操作
  - [x] 用 `uv` 初始化 Python 项目，配置 `pyproject.toml`
  - [x] 加入 hatchling 构建后端（`uv run python scripts/*.py` 无需设 `PYTHONPATH`）
  - [x] 加入 ruff（`select = ["E","F","W","I","UP"]`，行宽 120，双引号）
  - [x] 加入 pytest（含 `pytest-cov`，markers 区分 network/mock）
  - [x] 创建 `.env.example` 配置样板（TUSHARE_TOKEN / DEEPSEEK_API_KEY 等）
- [x] 测试
  - [x] `uv sync` 成功安装全部依赖
  - [x] `uv run ruff check .` 无警告
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（不适用）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`pyproject.toml` / `.env.example`）
  - [x] 本步骤产出物位置合规（项目根目录）
- [x] 提交
  - [x] `git commit -m "chore: 依赖管理与工具配置"`

### Step 0-3 目录骨架与配置入口

- 涉及文件：`AGENTS.md`、`src/config.py`、`src/__init__.py`、`src/main.py`、`.env.example`
- 实现 BR-*（工程基线）

- [x] 操作
  - [x] 按 dev-guide §5 创建源码目录结构（`src/` / `tests/` / `scripts/` / `docs/`）
  - [x] 写 `AGENTS.md`（项目级 AI 行为规范，含业务意图/关键决策/管道逻辑/约束）
  - [x] 写 `src/config.py` 的 `Settings` 单例 + `get_settings()` + 数据子目录映射
  - [x] 建 `src/main.py` 运行入口（dev-guide §10.3）
- [x] 测试
  - [x] `uv run python -c "from src.config import Settings; print(Settings())"` 可加载
  - [x] `uv run python src/main.py` 无异常退出
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（不适用）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`src/config.py` / `src/main.py` / `AGENTS.md`）
  - [x] 本步骤产出物位置合规（`src/` 根目录）
- [x] 提交
  - [x] `git commit -m "feat(config): 目录骨架与Settings配置入口"`

### Step 0-4 CI 门禁与第一个骨架测试

- 涉及文件：`.github/workflows/ci.yml`、`tests/test_skeleton.py`
- 实现 BR-*（工程基线）

- [x] 操作
  - [x] 创建 `.github/workflows/ci.yml`（push/PR 触发 main 分支）
  - [x] CI 三步：`ruff format --check` → `ruff check` → `pytest -m "not network"`
  - [x] 写 `tests/test_skeleton.py` 骨架测试（Settings 可导入/单例/默认值/data_path 自动创建）
- [x] 测试
  - [x] `uv run pytest tests/test_skeleton.py` 全部通过（6 项）
  - [x] 本地模拟 CI 三步全部通过
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（config.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`.github/workflows/ci.yml` / `tests/test_skeleton.py`）
  - [x] 本步骤产出物位置合规
- [x] 提交
  - [x] `git commit -m "ci: GitHub Actions门禁与骨架测试"`

---

## M1 数据采集

- 实现需求：BR-01/02 · FR-DATA-01~10 · FR-UPDATE-02/03（季度基本面/月度资金面更新）· NFR-03（全量 A 股采集可一晚完成）
- 目标：能从 Tushare 采集 A 股财务数据并落地为 `data/fin/full_collect/YYMMDD.csv`。支持两种模式：逐股（增量/持仓）与批量（首次全量/季度财报季全量刷新）。
- 验收：5 股冒烟通过 + 全量批量采集产出 `data/fin/full_collect/YYMMDD.csv`（≥5000 行），csv 字段对齐 dev-guide §8.1。

### Step 1-1 数据源抽象与字段模型

- 涉及文件：`src/data/contract.py`、`src/data/provider.py`、`tests/data/test_contract.py`
- 实现 BR-01
- 实现 FR-DATA-01、FR-DATA-08

- [x] 操作
  - [x] 在 `src/data/provider.py` 定义 `BaseFetcher` 抽象接口（fetch_stock_list / fetch_financials / fetch_financials_batch）
  - [x] 定义 `TUSHARE_INTERFACES` 接口注册表（20 个，vip 优先）
  - [x] 在 `src/data/contract.py` 定义 `StockFeatures`（extra=allow，~460 输出列）+ `StockInfo`
  - [x] 定义 `REQUIREMENT_ALIGNMENT`（53 需求→Tushare 字段对齐表）
  - [x] 定义 `SUPPLEMENTARY_FIELDS`（3 个：money_cap/free_cashflow/inv_turn）
  - [x] 定义 `FIELD_CN` / `FIELD_UNIT`（4 个 VIP 接口全量字段→中文/单位映射）
  - [x] 定义 `OUTPUT_COLUMNS`（去重排序）和 `PERCENT_FIELDS`
- [x] 测试
  - [x] `uv run pytest tests/data/test_contract.py` 全部通过（20 项）
  - [x] 测试需求对齐表覆盖（53 项）、接口注册表（20 个）、vip 接口名正确
  - [x] 测试 StockFeatures 必填/缺失/额外字段、BaseFetcher 抽象性
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（contract.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求（53 需求对齐全 + ~460 输出列 + 20 接口注册）
  - [x] 本步骤产出物命名合规（`contract.py` / `provider.py` / `test_contract.py`）
  - [x] 本步骤产出物位置合规（`src/data/` / `tests/data/`）
- [x] 提交
  - [x] `git commit -m "feat(data): 数据源抽象与字段契约模型"`

### Step 1-2 Tushare 适配器与限流重试

- 涉及文件：`src/data/provider.py`、`.env`、`tests/data/test_provider.py`
- 实现 BR-01
- 实现 FR-DATA-03、FR-DATA-04、FR-DATA-07

- [x] 操作
  - [x] 实现 `RateLimiter` 滑动窗口限流器（limit/window/sleep/clock 可注入）
  - [x] 实现 `TushareFetcher` 适配器（_call / _call_raw / _call_no_fields）
  - [x] 实现指数退避重试（默认 3 次，1/2/4 秒）
  - [x] 实现 `fetch_stock_list()`（stock_basic 按 ts_code/symbol/name/industry）
  - [x] 实现 `fetch_financials(ts_code, period)` 逐股聚合 4 个 VIP 接口
  - [x] 实现 `_latest()` / `_clean_record()` / `_str()` / `_merge_non_none()` 辅助方法
  - [x] 实现 SW 二级行业→五大类映射表（`_SW_L2_TO_CATEGORY`，~130 行业）
  - [x] 实现 `sw_l2_to_category()`（含罗马数字后缀剥离）
- [x] 测试
  - [x] `uv run pytest tests/data/test_provider.py` 全部通过（48 项）
  - [x] 覆盖：token 缺失报错、限流阻塞/不阻塞、重试成功/耗尽
  - [x] 覆盖：VIP 接口名优先、NaN→None 归一化、period 透传
  - [x] 覆盖：fetch_financials 取最新/聚合/end_date 锁定/4 接口全调
  - [x] 覆盖：SW 行业映射（已知/空/罗马后缀/未知/L1 回退/L3 回退）
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（provider.py 99%）
  - [x] 本步骤全部产出物符合预期功能需求（限流/重试/聚合/SW 映射）
  - [x] 本步骤产出物命名合规（`provider.py` / `test_provider.py`）
  - [x] 本步骤产出物位置合规
- [x] 提交
  - [x] `git commit -m "feat(provider): Tushare适配器与限流重试"`

### Step 1-3 采集编排、缓存与失败隔离

- 涉及文件：`src/data/collect.py`、`src/data/output.py`、`tests/data/test_collect.py`
- 实现 BR-02
- 实现 FR-DATA-05、FR-DATA-06

- [x] 操作
  - [x] 实现 `Cache` 类（文件缓存 + TTL 过期，disabled 模式用于测试）
  - [x] 实现 `Failure` 与 `CollectionResult` 结果模型
  - [x] 实现 `CollectionPipeline`（run / run_batch / to_rows / write_failures / context manager）
  - [x] 实现 `_fetch_one()`（缓存命中→返回；未命中→调接口→写缓存）
  - [x] 实现 `expected_latest_period()` 报告期推算（Q1 4-30 / 半年 8-31 / Q3 10-31 / 年报次年 4-30）
  - [x] 实现 `src/data/output.py`（format_value / to_output_row / write_features_csv / write_data_source_csv）
  - [x] 实现数值格式化（亿/万/%/倍/次/元/股/比率，按 FIELD_UNIT 逐字段匹配）
- [x] 测试
  - [x] `uv run pytest tests/data/test_collect.py` 全部通过（17 项）
  - [x] 覆盖：缓存 key/读写/禁用/损坏/过期、百分比格式化、输出列顺序
  - [x] 覆盖：pipeline 成功/缓存命中/失败隔离/None 处理/codes 过滤
  - [x] 覆盖：to_rows、write_failures、context manager、线程池冒烟
  - [x] 覆盖：报告期推算 9 个日期边界（含 Q1 截止日/半年截止日/Q3 截止日/年初等）
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（collect.py 100%，output.py 96%）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`collect.py` / `output.py` / `test_collect.py`）
  - [x] 本步骤产出物位置合规
- [x] 提交
  - [x] `git commit -m "feat(collect): 采集编排、缓存与CSV输出"`

### Step 1-4 随机 5 股冒烟测试与 csv 落地

- 涉及文件：`scripts/smoke_collect.py`、`src/data/output.py`、`integrated_tests/test_smoke_collect.py`、`src/data/collect.py`、`tests/data/test_collect.py`、`src/data/provider.py`
- 实现 BR-02
- 实现 FR-DATA-09、FR-DATA-10

- [x] 操作
  - [x] 写 `scripts/smoke_collect.py`（随机选 5 股真实采集，落地 `data/fin/smoke_collect/YYMMDD.csv`）
  - [x] 写 `run_smoke()` 函数（可注入 fetcher/settings/seed，便于集成测试复用）
  - [x] SW 行业分类策略：`ts_code → index_member_all(ts_code, is_new='Y') → l2_name → sw_l2_to_category() → 五大类`
  - [x] 实现 SW 缓存增量写盘（`data/ref/sw_industry.csv`）
  - [x] CSV 中文列头（`FIELD_CN` 映射）+ 数值格式化（`format_value`，含亿/万/两位小数）
  - [x] 单列 `YYMMDD-数据来源.csv`（接口/字段/中文/单位/单位来源/文档URL）
  - [x] `end_date` 锁定 income 报告期 + 缓存 TTL（默认 24h）防止数据陈旧
  - [x] 集成测试交叉校验 end_date 与 Tushare 独立重查一致
- [x] 测试
  - [x] `uv run pytest integrated_tests/test_smoke_collect.py -m "not network"`（4 项 mock）全部通过
  - [x] mock 测试覆盖：两张 CSV 落地、中文列头/百分比/亿万格式化、CJK 对齐单位无空格、数据来源表内容
  - [x] `uv run pytest -m network integrated_tests/test_smoke_collect.py`（1 项 network）交叉校验 end_date
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（核心功能 100% 覆盖）
  - [x] 本步骤全部产出物符合预期功能需求（5 股成功采集 + 两张 CSV 落地）
  - [x] 本步骤产出物命名合规（`smoke_collect.py` / `test_smoke_collect.py` / `YYMMDD.csv`）
  - [x] 本步骤产出物位置合规（`scripts/` / `integrated_tests/` / `data/fin/smoke_collect/`）
- [x] 提交
  - [x] `git commit -m "feat(collect): 5股冒烟采集与CSV落地"`

### Step 1-5 全量批量采集与性能策略

- 涉及文件：`src/data/provider.py`（新增 `fetch_financials_batch`）、`src/data/collect.py`（新增 `run_batch`）、`scripts/full_collect.py`、`scripts/sw_industry.py`、`integrated_tests/test_full_collect.py`、`.env.example`
- 实现 BR-02
- 实现 FR-DATA-09、FR-DATA-10、NFR-03。

- [x] 操作
  - [x] **Provider 层**：`TushareFetcher` 加 `fetch_financials_batch(period)` + `_call_paginated`
  - [x] 调用 4 个 VIP 接口只传 `period` 不传 `ts_code`，返回 `dict[str, StockFeatures]`
  - [x] 分页按 `offset/limit` 循环拉取直到返回数 < 上限
  - [x] **Pipeline 层**：`CollectionPipeline.run_batch()` 绑定 batch→enrich→result 流程
  - [x] 流式分批写盘、进度条、断点续采等 I/O 由 `scripts/full_collect.py` 负责
  - [x] **模式切换**：`--mode batch|per-stock`（默认 batch），增量用逐股、全量用批量
  - [x] **配置**：`BATCH_SIZE=500` / `VIP_PAGE_SIZE=5000` / `PERF_MODE=mid`
  - [x] **SW 缓存预构建**：`scripts/sw_industry.py` 多线程并行查询→`data/ref/sw_industry.csv`
  - [x] 两种模式对同一股票产出通过 mock 单测 cross-validate 断言一致
- [x] 测试
  - [x] mock 测试（CI 可跑）：批量全量/回填名称/缺失记失败/自动推算报告期/无批量报错/批量逐股一致
  - [x] CSV 落地测试：全量字段中文列头 + 百分比/亿万格式化 + 断点续采读已有 ts_code
  - [x] network 测试：真实全量采集 ≥5000 股 + 3 股逐字段比对交叉校验
  - [x] `uv run pytest -m "not network"` 全部通过
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（核心功能 100% 覆盖）
  - [x] 本步骤全部产出物符合预期功能需求（5516 股成功，≤15 股失败）
  - [x] 本步骤符合预期性能需求（批量 ~2-5 分钟，逐股 ~40-50 分钟）
  - [x] 本步骤产出物命名合规（`full_collect.py` / `sw_industry.py` / `YYMMDD.csv`）
  - [x] 本步骤产出物位置合规（`data/fin/full_collect/`）
- [x] 提交
  - [x] `git commit -m "feat(collect): 全量批量采集与性能策略"`

---

## M2 评分评级

- 实现需求：BR-03/04/05 · FR-SCORE-01~09 · FR-RATE-01~04
- 目标：把 dev-guide §8 的业务规则（一票否决、三维评分、行业权重、综合分、评级）落地为纯函数 + 单测。
- 验收：阈值表单测全覆盖（263 项，覆盖率 99.3%）；`data/fin/scoring/YYMMDD.csv` + `-否决.csv` 产出。

### Step 2-1 三维评分纯函数 + 单测

- 涉及文件：`src/scoring/scores.py`、`tests/scoring/test_scores.py`
- 实现 BR-04
- 实现 FR-SCORE-02~05

- [x] 操作
  - [x] 实现 `score_growth(f)` 成长性评分（4 维度：营收增速/净利增速/毛利率/现金流匹配）
  - [x] 实现 `score_stability(f)` 稳健性评分（3 维度：资产负债率/流动比率/存货周转率）
  - [x] 实现 `score_return(f)` 资金回报评分（2 维度：ROE/自由现金流归一化）
  - [x] 实现 `_round_score()` 辅助函数（钳位 1-10，无有效维度返回 5）
  - [x] 单测覆盖每个维度的全部 5 档阈值边界（含正值/负值/None/eps=0 除零跳过）
- [x] 测试
  - [x] `uv run pytest tests/scoring/test_scores.py` 全部通过
  - [x] 成长性 4 个子类 20 项：营收增速/净利增速/毛利率/现金流匹配（含除零保护）
  - [x] 稳健性 3 个子类 16 项：资产负债率/流动比率/存货周转率
  - [x] 资金回报 2 个子类 18 项：ROE/自由现金流（含归一化和无 total_assets 兜底）
  - [x] 综合分/否决/评级各子类全覆盖
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（scores.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求（三维评分纯函数 + 全阈值边界覆盖）
  - [x] 本步骤产出物命名合规（`scores.py` / `test_scores.py`）
  - [x] 本步骤产出物位置合规（`src/scoring/` / `tests/scoring/`）
- [x] 提交
  - [x] `git commit -m "feat(scoring): 三维评分纯函数与单测"`

### Step 2-2 行业权重、综合分与一票否决

- 涉及文件：`src/scoring/scores.py`、`tests/scoring/test_scores.py`
- 实现 BR-03、BR-04
- 实现 FR-SCORE-01、FR-SCORE-06、FR-SCORE-07

- [x] 操作
  - [x] 实现 `score_composite(growth, stability, return_, industry)` 按 §8.4 行业权重加权
  - [x] 五大行业权重固化到 `_INDUSTRY_WEIGHTS` dict
  - [x] 实现 `check_veto(f)` 一票否决（货币资金占比 > 30%且 > 1 亿）
  - [x] 定义 `VetoTrigger` frozen dataclass（rule + reason 审计可追溯）
  - [x] 其余否决项（行业毁灭/诚信问题）标记「待实现」
- [x] 测试
  - [x] 综合分：五大行业计算 + 未知行业兜底 + 1 位小数精度
  - [x] 一票否决：触发/不触发（含 30%边界/绝对值门槛/missing/zero 边界/frozen dataclass）
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（scores.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求（行业权重加权+一票否决可追溯）
  - [x] 本步骤产出物命名合规
  - [x] 本步骤产出物位置合规
- [x] 提交
  - [x] `git commit -m "feat(scoring): 行业权重综合分与一票否决"`

### Step 2-3 评级纯函数与边界单测

- 涉及文件：`src/scoring/scores.py`、`tests/scoring/test_scores.py`
- 实现 BR-05
- 实现 FR-RATE-01

- [x] 操作
  - [x] 实现 `score_rating(composite: float) -> str` 四级评级映射
  - [x] 阈值降序列表：8.5 皇冠明珠 / 7.0 优秀白马 / 5.5 鸡肋·观察 / 0.0 垃圾
  - [x] 边界值归属测试（8.5→皇冠、7.0→优秀、5.5→鸡肋、5.4→垃圾）
- [x] 测试
  - [x] 评级边界单测：8.5/10.0→皇冠明珠，7.0/8.49→优秀白马，5.5/6.99→鸡肋，5.4/0.0/-1.0→垃圾
  - [x] 含 8.49 和 6.99 的浮点精度边界验证
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（scores.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求（四级评级 + 三边界全测）
  - [x] 本步骤产出物命名合规
  - [x] 本步骤产出物位置合规
- [x] 提交
  - [x] `git commit -m "feat(scoring): 评级映射与边界单测"`

### Step 2-4 评分评级串联 csv 落地

- 涉及文件：`scripts/full_scores.py`、`integrated_tests/test_full_scores.py`
- 实现 BR-05
- 实现 FR-RATE-02~04、FR-SCORE-08、FR-SCORE-09

- [x] 操作
  - [x] 写 `scripts/full_scores.py`（读取采集 CSV → 反序列化 → 评分 → 追加五列 → 落盘 `data/fin/full_scores/`）
  - [x] 实现 `_load_features()` 中文列头→英文字段名反序列化
  - [x] 实现 `_parse_value()` 逆向解析格式化数值（亿×1e8/万×1e4/%移除符号等）
  - [x] 实现 `run_scores()` 逐行评分+否决分离
  - [x] 实现 `_write_scoring_csv()` 和 `_write_veto_csv()` 写盘
  - [x] 实现 `_find_latest()` 自动取最新 YYMMDD 采集文件
- [x] 测试
  - [x] `uv run pytest integrated_tests/test_full_scores.py -m "not network"`（8 项 mock）全部通过
  - [x] 覆盖：评分列追加/否决剔除/行业权重/评级边界/CSV 产物结构/空边界/缺失容错
  - [x] network 测试走真实 CSV 全量评分（4880 股通过 + 636 股否决）
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（核心功能 100% 覆盖）
  - [x] 本步骤全部产出物符合预期功能需求（评分 CSV + 否决 CSV 产出）
  - [x] 本步骤产出物命名合规（`full_scores.py` / `test_full_scores.py` / `YYMMDD.csv`）
  - [x] 本步骤产出物位置合规（`scripts/` / `integrated_tests/` / `data/fin/full_scores/` / `data/test/full_scores/`）
- [x] 提交
  - [x] `git commit -m "feat(scoring): 评分评级串联CSV落地"`

---

## M3 报告输出

- 实现需求：BR-06/14 · FR-REPORT-01~04、FR-REPORT-07 · FR-CHAT-04（BR-07 持仓表挪至 M5，用户通过 UI 对话生成）
- 目标：LLM 接入 + 荐股 Top20 报告生成，含 AI 核心亮点与风险提示。
- 验收：`data/fin/full_report/YYMMDD.csv` 生成。

### Step 3-1 公司类型与操作建议

- 涉及文件：`src/reports/evaluation.py`、`tests/reports/test_evaluation.py`
- 实现 BR-06
- 实现 FR-REPORT-02、FR-REPORT-04

- [x] 操作
  - [x] 实现 `classify_company_type()` 公司类型判断（千里马/现金牛/护城河，§8.7）
  - [x] 实现 `get_advice()` 评级→操作建议映射（§8.9）
  - [x] 申万二级→五大分类复用 M1 Step 1-4 的 `sw_l2_to_category()`
  - [x] 写 unit tests 覆盖三种类型边界与四种评级操作建议
- [x] 测试
  - [x] `uv run pytest tests/reports/test_evaluation.py -m "not network"` 全部通过
  - [x] 覆盖：三种公司类型判断/全部四种评级的操作建议映射
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%，核心功能 100% 覆盖
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`evaluation.py` / `test_evaluation.py`）
  - [x] 本步骤产出物位置合规（`src/reports/` / `tests/reports/`）
- [x] 提交
  - [x] `git commit -m "feat(report): 公司类型分类与操作建议规则引擎"`

### Step 3-2 LLM 适配层与 DeepSeek 接入

- 涉及文件：`src/agents/llm_adapter.py`、`tests/agents/test_llm_adapter.py`、`pyproject.toml`
- 实现 BR-14
- 实现 FR-CHAT-04

- [x] 操作
  - [x] 在 `src/agents/llm_adapter.py` 封装 DeepSeek（OpenAI 兼容接口）
  - [x] 统一 provider 接口（`chat_completion` / `stream_completion`）
  - [x] `reasoning_effort="max"` 启用最高深度思考模式（DeepSeek V4 Pro）
  - [x] `.env.example` 已含 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`
  - [x] 新增 `openai` SDK 依赖同步 `pyproject.toml`
- [x] 测试
  - [x] mock 测试验证调用参数正确 + `reasoning_content` 回退 + 流式混合输出（7 项）
  - [x] 真实调用冒烟测试（3 项 `@pytest.mark.network`，CI 不跑）
- [x] 验收
  - [x] 本步骤各文件单元测试覆盖率 ≥ 80%（llm_adapter.py 100%）
  - [x] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`llm_adapter.py` / `test_llm_adapter.py`）
  - [x] 本步骤产出物位置合规（`src/agents/` / `tests/agents/`）
- [x] 提交
  - [x] `git commit -m "feat(llm): DeepSeek适配层"`

### Step 3-3 荐股 Top20 生成

- 涉及文件：`src/reports/reporting.py`（纯逻辑）、`scripts/full_report.py`（LLM 编排）、`tests/reports/test_reporting.py`（31 项单测）、`integrated_tests/test_full_report.py`（网络集成）
- 实现 BR-06
- 实现 FR-REPORT-01、FR-REPORT-03

**AI 参考字段**（14 个，传入 LLM 时附带中文释义与单位）：

| 角色 | 字段 | 中文释义 | 单位 |
|---|---|---|---|
| 身份 | `ts_code` | 股票代码 | — |
| | `name` | 股票名称 | — |
| | `industry` | 行业分类 | — |
| | `公司类型` | 公司类型 | 千里马/现金牛/护城河 |
| 评分 | `成长分` | 成长性评分 | 1-10 |
| | `稳健分` | 稳健性评分 | 1-10 |
| | `回报分` | 资金回报评分 | 1-10 |
| | `综合分` | 综合评分 | 0-10 |
| | `评级` | 综合评级 | 皇冠明珠/优秀白马/鸡肋·观察/垃圾 |
| 增长 | `or_yoy` | 营业收入同比增长率 | % |
| | `netprofit_yoy` | 归母净利润同比增长率 | % |
| | `grossprofit_margin` | 销售毛利率 | % |
| 安全 | `debt_to_assets` | 资产负债率 | % |
| | `current_ratio` | 流动比率 | 倍 |
| 回报 | `roe` | 净资产收益率 | % |
| | `free_cashflow` | 企业自由现金流 | 元 |
| | `eps` | 基本每股收益 | 元/股 |

LLM prompt 模板写入 `data/ref/prompt-library.md`（Step 3-4）。

**输出列**（按 dev-guide §8.10，共 13 列）：

| 列名 | 来源 |
|---|---|
| 股票代码 | `ts_code`（去后缀） |
| 股票名称 | `name` |
| 公司类型 | `classify_company_type()` |
| 行业分类 | `industry` |
| 核心亮点 | LLM 生成 ≤120 字（`_generate_single` + `_clean_llm_output` 清洗回声） |
| 成长性 | `成长分` |
| 稳健性 | `稳健分` |
| 回报性 | `回报分` |
| 综合分 | `综合分` |
| 评级 | `评级` |
| 操作建议 | `get_advice()` |
| 风险提示 | LLM 生成 ≤120 字 |
| 点评 | LLM 生成 ≤180 字 |

- [x] 操作
  - [x] 实现 `build_top20(csv_path)` 读取评分 CSV → 降序 Top20 → 并发 LLM（6 worker，`reasoning_effort="max"`）
  - [x] 实现 `src/reports/reporting.py` 纯逻辑：`parse_back`/`make_features`/`build_llm_context`/`clean_llm_output`/`write_full_report_csv`
  - [x] 实现 `_generate_single()` 统一调 LLM 生成亮点/风险/点评（token=300/300/500，chars≤120/120/180，temperature=0.3→0.6 重试）
  - [x] 实现三层分层 system prompt：基本面分析师/风控分析师/投资顾问，各自独立角色约束与禁止项
  - [x] 实现 user prompt 含 few-shot 示例（好/差对照）、公司类型差异化焦点（千里马重增速/现金牛重现金流/护城河重壁垒）
  - [x] 实现字段子集裁剪：`_HL_FIELDS`(6)、`_RISK_FIELDS`(7)、`_CMT_FIELDS`(7)，prompt 不提及 LLM 看不到的字段
  - [x] 实现 `clean_llm_output()` 噪声剥离：`_RE_NOISE`（30+ 句首模式）+ `_RE_DATA_READOUT` + `_RE_HAS_CONTENT`（50+ 关键词）+ 中文引号剥离
  - [x] 元推理抑制：去编号化 system prompt（禁止"规则1/2/3"触发 checklist 行为）、软化"必须带数据"为"有数据用数据"、禁止语助词（'这里''那么''但''或许'）
  - [x] 调用 `classify_company_type()` + `get_advice()` 确定公司类型与操作建议
  - [x] 输出到 `data/fin/full_report/YYMMDD.csv`（并发 6 worker，~50s）
- [x] 测试
  - [x] `tests/reports/test_reporting.py`（31 项 mock）— 解析/上下文/清洗/写盘全覆盖，99% 覆盖率
  - [x] `uv run pytest integrated_tests/test_full_report.py -m network` — 真实评分 + 60 次 LLM 调用，校验 13 列完整、亮点/风险 ≤120 字、点评 ≤180 字
- [ ] 验收
  - [ ] 本步骤全部产出物符合预期功能需求
  - [x] 本步骤产出物命名合规（`reporting.py` / `full_report.py` / `test_reporting.py` / `test_full_report.py` / `YYMMDD.csv`）
  - [x] 本步骤产出物位置合规（`src/reports/` / `scripts/` / `tests/reports/` / `integrated_tests/` / `data/fin/full_report/` / `data/test/full_report/`）
- [ ] 提交
  - [ ] `git commit -m "feat(report): 荐股Top20生成与纯逻辑单测"`

### Step 3-4 字段契约与 Prompt 文档

- 涉及文件：`docs/dev-guide.md`（§8.1 字段契约）、`data/ref/prompt-library.md`
- 实现 BR-06
- 实现 FR-REPORT-07
- 总结精华/设计巧思：字段计算口径已合并入 `docs/dev-guide.md` §8.1 作为单一事实来源，无需独立 `data-contract.md`；`data/ref/prompt-library.md` 存放亮点/风险提示 Prompt 模板（含 13 字段的中文释义+单位拼装示例），与 SW 行业缓存同目录，`data/ref/` 为参考数据统一存放地。

- [x] 操作
  - [x] 字段计算口径已合并入 `docs/dev-guide.md` §8.1（无需单独文件）
- [ ] 操作
  - [ ] 待补 `data/ref/prompt-library.md`（亮点/风险提示 Prompt 模板，含 14 字段拼装格式）
  - [ ] 人工核对字段口径与代码一致
- [ ] 测试
  - [ ] Prompt 模板经 5+ 样本输出人工验证
- [ ] 验收
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规（`prompt-library.md`）
  - [ ] 本步骤产出物位置合规（`data/ref/`）
- [ ] 提交
  - [ ] `git commit -m "docs: Prompt文档"`

> M3 验收：荐股 Top20 落到 `data/fin/full_report/YYMMDD.csv`，LLM prompt 模板在 `data/ref/prompt-library.md`。

---

## M4 多 Agent 编排

- 实现需求：BR-12/17 · AR-*（§7）· FR-CHAT-01~03、FR-CHAT-05（LLM 适配层已迁至 M3 Step 3-2）
- 目标：把单线 pipeline 升级为多 Agent 编排，支持自然语言对话驱动。
- 验收：对话可触发各 Agent。

### Step 4-1 RAG 知识库

- 涉及文件：`src/rag/store.py`、`src/rag/indexer.py`、`src/rag/retriever.py`、`tests/test_rag_retriever.py`
- 实现 BR-12
- 实现 AR-RAG（§7.2）
- 总结精华/设计巧思：ChromaDB 本地向量库 + bge-small-zh 中文嵌入模型，不依赖云服务；行业对照表/否决规则/评分阈值入库后 Agent 决策前检索对齐，防止 LLM 幻觉漂移导致评分出错。

- [ ] 操作
  - [ ] 用 ChromaDB + bge-small-zh 构建本地向量库
  - [ ] 入库内容：行业对照表、否决规则、评分阈值、行业分类逻辑
  - [ ] 实现 `indexer.py`（文档索引）/ `retriever.py`（语义检索）
- [ ] 测试
  - [ ] `uv run pytest tests/test_rag_retriever.py` 全部通过
  - [ ] 验证检索结果与规则文本一致
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规（`store.py` / `indexer.py` / `retriever.py`）
  - [ ] 本步骤产出物位置合规（`src/rag/` / `tests/`）
- [ ] 提交
  - [ ] `git commit -m "feat(rag): 本地知识库构建"`

### Step 4-2 RouterAgent 与 Agent 编排

- 涉及文件：`src/agents/router.py`、`src/agents/data_agent.py`、`src/agents/scoring_agent.py` 等、`src/agents/graph.py`、`tests/test_agents_router.py`
- 实现 BR-12、BR-17
- 实现 AR-Router（§7.1）
- 总结精华/设计巧思：LangGraph 状态机做多 Agent 编排，RouterAgent 基于 LLM 意图分类+规则正则兜底做意图路由，无法识别时回退 ChatAgent；决策可日志回溯；业务 Agent 复用 M1/M2 的纯函数和采集管道，不做重复实现。

- [ ] 操作
  - [ ] 用 LangGraph 实现 RouterAgent（意图路由 + 规则兜底）
  - [ ] 封装已有管道为 DataAgent / ScoringAgent / RatingAgent / ReportAgent
  - [ ] 组装 LangGraph 状态机（`graph.py`）
- [ ] 测试
  - [ ] `uv run pytest tests/test_agents_router.py` 全部通过
  - [ ] 覆盖：各意图路由正确/未知意图回退/状态流转无误
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规（`router.py` / `graph.py` / `*_agent.py`）
  - [ ] 本步骤产出物位置合规（`src/agents/` / `tests/`）
- [ ] 提交
  - [ ] `git commit -m "feat(agents): 路由与Agent编排"`

### Step 4-3 ChatAgent、记忆与流式对话 API

- 涉及文件：`src/agents/chat_agent.py`、`src/agents/memory.py`、`api/routes/chat.py`、`tests/test_chat.py`
- 实现 BR-14
- 实现 FR-CHAT-01、FR-CHAT-02、FR-CHAT-03、FR-CHAT-05
- 总结精华/设计巧思：SSE 流式输出提供"逐字吐出"的对话体验；分层记忆（短期会话/长期偏好/RAG）让 Agent 跨会话记得持仓与偏好；FastAPI `POST /chat` 通过本地回环地址通信，数据不出本机。

- [ ] 操作
  - [ ] 实现 ChatAgent（自由对话，可调用其他 Agent）
  - [ ] 实现分层记忆（短期会话 + 长期偏好 + RAG 检索）
  - [ ] 加 `POST /chat`（SSE 流式，§11.1）
- [ ] 测试
  - [ ] mock 测试验证 SSE 流式输出格式
  - [ ] 本地起服务 curl 测 `/chat` 流式返回
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`src/agents/` / `api/routes/`）
- [ ] 提交
  - [ ] `git commit -m "feat(chat): 记忆与流式对话API"`

> M4 验收：自然语言可触发采集/评分/报告。

---

## M5 热点追踪 + 持股监控 + 推送

- 实现需求：BR-08/09/10/11 · FR-HOTSPOT-01~05 · FR-PORT-01~05 · FR-PUSH-01~05 · FR-UPDATE-01
- 目标：每日 09:00/17:00 自动跑热点与持仓分析并推送。
- 验收：定时任务与推送链路打通。

### Step 5-1 定时调度器

- 涉及文件：`src/scheduler/scheduler.py`、`.env.example`（补 cron 配置，对齐 §10.2）、`tests/test_scheduler.py`
- 实现 BR-11
- 实现 FR-UPDATE-01
- 总结精华/设计巧思：APScheduler 内嵌 FastAPI 进程，cron 表达式放 `.env` 配置不硬编码；09:00 跑热点+持仓，17:00 跑持仓复核，各自独立任务互不阻塞。

- [ ] 操作
  - [ ] 用 APScheduler 实现 09:00/17:00 触发
  - [ ] cron 配置从 `.env` 读取（`HOTSPOT_CRON_09` / `PORTFOLIO_CRON_09` 等）
- [ ] 测试
  - [ ] 把 cron 改成 1 分钟后触发，观察日志验证
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规
- [ ] 提交
  - [ ] `git commit -m "feat(scheduler): 09/17定时任务"`

### Step 5-2 HotspotAgent 热点追踪

- 涉及文件：`src/agents/hotspot_agent.py`、`src/data/hot_search_fetcher.py`、`tests/test_hotspot_agent.py`
- 实现 BR-08
- 实现 FR-HOTSPOT-01~05
- 总结精华/设计巧思：热搜来源（百度/微博/东财）多来源 fallback，单个失败不拖垮；LLM 识别受益行业→RAG 映射个股 Top5；结果落地 `data/hot/YYMMDD-HH.csv` 供 UI 查询和推送引用。

- [ ] 操作
  - [ ] 实现热搜采集（百度/微博/东财）
  - [ ] LLM 识别受益行业 → RAG 映射个股 Top5
  - [ ] 落盘 `data/hot/YYMMDD-HH.csv`
- [ ] 测试
  - [ ] `uv run pytest tests/test_hotspot_agent.py` 全部通过
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规
- [ ] 提交
  - [ ] `git commit -m "feat(hotspot): 热点追踪Agent"`

### Step 5-3 PortfolioAgent 持股监控

- 涉及文件：`src/agents/portfolio_agent.py`、`tests/test_portfolio_agent.py`
- 实现 BR-07、BR-09
- 实现 FR-REPORT-05、FR-REPORT-06、FR-PORT-01~05
- 总结精华/设计巧思：用户通过 UI 对话录入持仓（代码+名称），系统生成 `data/hold/YYMMDD.csv` 基线表（字段同荐股表 §8.10）；复用已有采集+评分管道重算持仓；一票否决触发→高亮提醒；与上次评分做差值对比输出趋势；自动生成操作建议但不自动执行。

- [ ] 操作
  - [ ] 实现 UI 对话录入持仓，生成 `data/hold/YYMMDD.csv` 持仓基线表
  - [ ] 实现持仓重算（重爬+重评）
  - [ ] 风险高亮（一票否决触发时标注）
  - [ ] 趋势对比（与上次评分差值计算）
  - [ ] 操作建议生成（持有/加仓/减仓/止损）
  - [ ] 输出 `data/hold/YYMMDD-09.csv` / `-17.csv`
- [ ] 测试
  - [ ] `uv run pytest tests/test_portfolio_agent.py` 全部通过
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`data/hold/`）
- [ ] 提交
  - [ ] `git commit -m "feat(portfolio): 持仓录入与持股监控Agent"`

### Step 5-4 推送通知（邮件/微信）

- 涉及文件：`src/notifications/email_notifier.py`、`src/notifications/wechat_notifier.py`、`.env.example`（补 `SMTP_*`/`WECHAT_PUSH_ENABLED`，对齐 §10.2）、`tests/test_notifications.py`
- 实现 BR-10
- 实现 FR-PUSH-01~05
- 总结精华/设计巧思：邮件发完整 HTML 表格（含持仓摘要+热点 Top5），微信发纯文本摘要；单渠道失败不拖垮主流程——推送是旁路通知，挂了不影响分析链路。

- [ ] 操作
  - [ ] 实现邮件推送（完整 HTML 表格）
  - [ ] 实现微信推送（摘要文本，可选）
  - [ ] 单渠道失败不拖垮主流程（FR-PUSH-05）
- [ ] 测试
  - [ ] 配置 SMTP 后真实发一封测试邮件
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规
- [ ] 提交
  - [ ] `git commit -m "feat(notify): 邮件与微信推送"`

> M5 验收：09:00/17:00 自动跑并推送（DoD 第 4 条）。

---

## M6 桌面端 UI

- 实现需求：BR-13/15/16 · FR-UI-01~07 · NFR-01/02
- 目标：Win/Mac 双端桌面应用可安装运行、可对话。
- 验收：Win/Mac 可安装运行。

### Step 6-1 FastAPI 路由完善

- 涉及文件：`api/routes/*.py`
- 实现 BR-15
- 实现 FR-UI-01
- 总结精华/设计巧思：FastAPI 作为桌面端本地后端，所有路由通过 `localhost` 回环地址通信，数据不出本机；`/chat` 已在 M4 完成，此步补齐 pipeline/报告/持仓/热点/健康检查等 REST 端点。

- [ ] 操作
  - [ ] 补齐 dev-guide §11.1 剩余路由
  - [ ] `POST /pipeline/run`（触发全流程）
  - [ ] `GET /report/{date}`（获取荐股/持仓/热点报告）
  - [ ] `POST /portfolio`（录入/更新持仓）
  - [ ] `GET /hotspot/{date}`（获取热点分析）
  - [ ] `GET /health`（健康检查）
- [ ] 测试
  - [ ] `uv run uvicorn api.app:app --reload`，逐个 curl 验证
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规（`api/routes/*.py`）
  - [ ] 本步骤产出物位置合规（`api/`）
- [ ] 提交
  - [ ] `git commit -m "feat(api): 补齐FastAPI路由"`

### Step 6-2 Electron + React 骨架

- 涉及文件：`apps/desktop/` 全部
- 实现 BR-13、BR-15
- 实现 FR-UI-03
- 总结精华/设计巧思：Electron 用网页技术做桌面应用，启动时自动拉起本地 FastAPI 后端进程；前端通过 HTTP/SSE 与本地后端通信，所有数据不出本机；对话区+报告区作为核心交互入口。

- [ ] 操作
  - [ ] 在 `apps/desktop` 初始化 Electron + React + Vite
  - [ ] 套壳本地 FastAPI（启动时自动拉起后端进程）
  - [ ] 实现对话区（聊天界面）与报告区（数据展示）
- [ ] 测试
  - [ ] `cd apps/desktop && npm run dev` 能打开窗口并对话
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`apps/desktop/`）
- [ ] 提交
  - [ ] `git commit -m "feat(desktop): Electron+React骨架"`

### Step 6-3 图标与完整仪表盘

- 涉及文件：`apps/desktop/assets/icon.*`、各页面组件
- 实现 BR-16
- 实现 FR-UI-02、FR-UI-07
- 总结精华/设计巧思：巧克力色荷兰侏儒兔图标（C-08）；五区仪表盘（对话/报告/持仓/热点/监控）切换流畅；UI 明示"数据本地存储"（FR-UI-07）增强用户信任。

- [ ] 操作
  - [ ] 制作巧克力色荷兰侏儒兔图标（`.ico`/`.icns`，C-08，FR-UI-02）
  - [ ] 补持仓区、热点区、监控区页面组件
  - [ ] UI 明示"数据本地存储，不上传云端"（FR-UI-07）
- [ ] 测试
  - [ ] 视觉评审图标风格
  - [ ] 五个区都能正常显示数据
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`apps/desktop/assets/` / `apps/desktop/src/`）
- [ ] 提交
  - [ ] `git commit -m "feat(desktop): 图标与仪表盘区域"`

### Step 6-4 Win/Mac 打包

- 涉及文件：`manifests/win.yml`、`manifests/mac.yml`、`apps/desktop/electron-builder.*`
- 实现 BR-13
- 实现 FR-UI-06
- 总结精华/设计巧思：平台差异收敛到打包配置文件（nsis/portable for Win, dmg for Mac），UI 代码共享一份；`manifests/` 集中管理部署清单，不污染源码。

- [ ] 操作
  - [ ] 在 `manifests/` 配置 Win（nsis/portable）与 Mac（dmg）打包
  - [ ] 配好 `electron-builder` 对应配置
- [ ] 测试
  - [ ] 分别打出 Win 与 Mac 安装包并安装运行
- [ ] 验收
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`manifests/`）
- [ ] 提交
  - [ ] `git commit -m "build: Win/Mac打包配置"`

> M6 验收：双端可安装运行、可对话（DoD 第 5、6 条）。

---

## M7 监控与反馈

- 实现需求：BR-12（监控/反馈要素，§7.2）· NFR-05（可观测）
- 目标：Agent 执行可观测，用户反馈可收集迭代。
- 验收：监控可查、反馈可写。

### Step 7-1 Agent 执行链落盘与监控区

- 涉及文件：`src/agents/trace.py`、`apps/desktop/src/monitor/`
- 实现 BR-12
- 实现 NFR-05
- 总结精华/设计巧思：每次 Agent 执行记录 `agent_name / tools_called / tokens / latency / status / error` 落盘为结构化日志；UI 监控区展示执行链时间线，方便排查问题。

- [ ] 操作
  - [ ] 实现 Agent 执行跟踪（agent_name/tools_called/tokens/latency/status/error）
  - [ ] 落盘 `data/monitor/` 结构化日志
  - [ ] UI 监控区展示执行链时间线
- [ ] 测试
  - [ ] 跑一次流程后，监控区能看到完整执行链记录
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`src/agents/` / `apps/desktop/src/monitor/`）
- [ ] 提交
  - [ ] `git commit -m "feat(monitor): Agent执行链落盘"`

### Step 7-2 用户反馈库

- 涉及文件：`src/agents/feedback.py`、`api/routes/feedback.py`
- 实现 BR-12
- 总结精华/设计巧思：点赞/修正入 `data/feedback/` 结构化存储；反馈数据用于 Prompt 迭代与评分校准——闭环学习是 Agent 持续进化的关键。

- [ ] 操作
  - [ ] 实现用户反馈采集（点赞/修正）
  - [ ] 落盘 `data/feedback/` 结构化存储
  - [ ] 提供 `api/routes/feedback.py` 端点
- [ ] 测试
  - [ ] UI 点赞后 `data/feedback/` 有记录
- [ ] 验收
  - [ ] 本步骤各文件单元测试覆盖率 ≥ 80%
  - [ ] 本步骤全部产出物符合预期功能需求
  - [ ] 本步骤产出物命名合规
  - [ ] 本步骤产出物位置合规（`src/agents/` / `data/feedback/`）
- [ ] 提交
  - [ ] `git commit -m "feat(feedback): 用户反馈库"`

### Step 7-3 端到端验收与文档定稿

- 涉及文件：`README.md`、`CHANGELOG.md`、`docs/architecture.md`
- 总结精华/设计巧思：DoD 逐项核对确保无遗漏；`architecture.md` 记录 ADR 决策，供新加入者理解架构取舍。

- [ ] 操作
  - [ ] 按 dev-guide §12.3 DoD 逐项核对
  - [ ] 定稿 `README.md` 与 `CHANGELOG.md`
  - [ ] 定稿 `docs/architecture.md`
- [ ] 测试
  - [ ] 跑一遍 DoD 清单全部打勾
- [ ] 验收
  - [ ] DoD 全部打勾
  - [ ] 本步骤产出物位置合规（`docs/`）
- [ ] 提交
  - [ ] `git commit -m "docs: 定稿CHANGELOG/README/架构文档"`

> M7 验收：DoD 全部打勾。

---

## 附：里程碑与提交总览

| 里程碑 | Step 数 | 提交数 | 需求覆盖（dev-guide §9） | 验收命令 | 推送方式 |
|---|---|---|---|---|---|
| M0 工程骨架 | 4 | 4 | 工程基线（支撑全部 FR/NFR） | `uv run pytest` | 直接推 main |
| M1 数据采集 | 5 | 5 | BR-01/02 · FR-DATA-01~10 · FR-UPDATE-02/03 · NFR-03 | 全量批量采集 + 5 股冒烟，`data/fin/full_collect/YYMMDD.csv` 字段齐全 | 直接推 main |
| M2 评分评级 | 4 | 4 | BR-03/04/05 · FR-SCORE-01~09 · FR-RATE-01~04 | 阈值单测全覆盖（297 项 mock，cov 99.4%）；`data/fin/scoring/YYMMDD.csv` + `-否决.csv` + 公司类型规则引擎 | 直接推 main |
| M3 报告输出 | 4 | 3/4 | BR-06/14 · FR-REPORT-01~04/07 · FR-CHAT-04 | 荐股 Top20 CSV（13 列，LLM 亮点/风险/点评 30/30/50 字，~30s） | 直接推 main |
| M4 Agent 编排 | 3 | 3 | BR-12/17 · AR-* · FR-CHAT-01~03/05 | 对话触发各 Agent | 直接推 main |
| M5 监控推送 | 4 | 4 | BR-07/08/09/10/11 · FR-REPORT-05/06 · FR-HOTSPOT/PORT/PUSH · FR-UPDATE-01 | 09/17 定时 + 推送 | 直接推 main |
| M6 桌面端 | 4 | 4 | BR-13/15/16 · FR-UI-01~07 · NFR-01/02 | Win/Mac 可安装 | 直接推 main |
| M7 监控反馈 | 3 | 3 | BR-12（监控/反馈）· NFR-05 | DoD 全勾 | 直接推 main |

**合计**：31 个断点提交、8 个里程碑，全部直接推 main（不开分支、不开 PR），覆盖 dev-guide §9 全部 BR/FR。

---

## 附：断点学习小贴士

1. **每步只做一件事**：不要顺手改别的，保持 commit 干净，出问题好回滚（`git revert`）。
2. **提交前必验证**：`uv run ruff check . && uv run pytest -m "not network" --cov=src --cov-fail-under=80` 是你的安全带（当前覆盖率 99.4%，297 项测试）。
3. **看不懂就停下来查**：每个 Step 的"总结精华"是刻意写的，遇到陌生概念先搞懂再往下。
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
