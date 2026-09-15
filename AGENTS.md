# AGENTS.md - Agent 工作指南

- alpha-jerry 项目级 AI 刚性规范与上下文入口；冲突时本指南优先；业务规则以 `docs/brd.md` 表格为准（RIGID）。
- 个人单人开发，Windows / macOS 双端对齐，直推 `main`。交付形态为纯本地 CLI 工具集，不自研套壳 Agent。

## 相关文档

- `README.md` — 项目说明与快速开始 | `CHANGELOG.md` — 变更日志（SemVer）
- `docs/brd.md` — 业务需求基线 + 否决/评分/评级/建议 RIGID 规则表
- `ROADMAP.md` — 3 大需求路线图（CLI 接驳与数据升级 / 侏儒兔 banner 与微信 iLink 直连 / 多模型锐评子系统）

## 项目概述

面向 A 股基本面分析的本地命令行工具：Tushare 采集（含股东人数）→ 一票否决 → 三维评分 → 行业加权评级 → LLM 锐评（DeepSeek/GLM 双 Provider）→ 荐股 Top50（13 列）。

### 关键决策

1. **本地优先与纯文件存储**：数据本地存储不上云，`data/` 不入库；全量双落盘（人读 CSV + 机读 raw CSV），无外部数据库。
2. **规则可审计**：否决/评分/评级为纯函数 + 全阈值边界单测；业务规则改代码不修 `docs/brd.md`。
3. **步骤解耦与无损传递**：步骤间只传内存对象或读 raw CSV，彻底废除 `format_value → _parse_value` 精度损耗式往返。
4. **CLI 契约化 + 微信直连 iLink，不自研通用 Agent**：本项目只做内核 + LLM 子系统 + `src/tools/` 工具封装 + `src/wechat/` iLink 收发；不自研套壳多智能体。
5. **LLM 输出不可信**：结构化 JSON → 白名单校验（字数/禁词/数字一致性）→ 重试 → 跨模型切换 → 规则兜底 → 缓存 → 追踪。
6. **配置集约**：路径/超时/密钥/模型参数全走 `Settings`，严禁硬编码；`.env` 不入库，新增配置同步 `.env.example`。
7. **数据源单一真源**：Tushare VIP 接口优先，不传 `fields` 取全量；以 `expected_latest_period()` 支持披露日增量更新。
8. **双端一致与防乱码**：Python 3.12，LF 换行，文件读写显式 `encoding="utf-8"`，路径全 `pathlib.Path`。
9. **依赖先行与 Fail-Fast**：新增库先入 `pyproject.toml` 并锁定 `uv.lock`；核心依赖缺失直接阻断，严禁静默吞异常。
10. **状态与日志规整**：状态字段使用英文枚举字符串（如 `'pending'/'success'/'fallback'`），严禁神秘数字；追踪日志只追加不更新。

### 技术栈

- Runtime: Python 3.12 · uv 0.10 · hatchling · 标准库 `argparse`（零重型 CLI 依赖）
- Data & Config: Tushare Pro 1.4（VIP 接口需 5000 积分）· pandas 3.x · pydantic-settings 2.x
- LLM: DeepSeek + 智谱 GLM（OpenAI 兼容协议，支持 SOCKS 代理）
- Quality: pytest 9 + pytest-cov (≥80%) · ruff 0.15

## 项目目录

```
alpha-jerry
├── src/
│   ├── config.py            # Settings 单例 + data 子目录映射
│   ├── data/                # 采集层：contract / provider / collect / output / store
│   ├── scoring/             # 评分层：scores（纯函数，阈值全单测）
│   ├── reports/             # 报告层：evaluation / reporting（纯函数）
│   ├── llm/                 # 锐评子系统：client / review / fallback / cache / trace
│   ├── tools/               # 工具层：market / holdings / status / wechat（CLI 契约）
│   ├── wechat/              # iLink 直连：ilink / session / router / bot / notify
│   ├── cli.py               # CLI 入口（argparse，统一 UTF-8 与退出码 0/2/3/4）
│   └── banner.py            # 侏儒兔 banner（ANSI / 🐰 / ASCII 三档降级）
├── scripts/                 # 批处理薄包装：full_collect / full_scores / full_report / sw_industry
├── tests/ & integrated_tests/ # 单元测试（镜像 src）与集成测试（mock + network）
├── manifests/               # 部署清单（可选后续项）
├── assets/icon/             # 品牌资产：巧克力色侏儒兔源图 png / ico / icns
└── data/                    # 运行期本地数据（不入库）：fin / cache / hold / monitor / ref / wechat
```

### 关键文件

- `src/config.py` — 配置单例与路径/密钥/模型集中管理
- `src/data/contract.py` — `StockFeatures`、~460 输出列映射、股东人数 `holder_num`
- `src/data/provider.py` + `collect.py` — Tushare 适配器（限流重试）与披露期感知采集流水线
- `src/scoring/scores.py` — 三维评分、一票否决、行业权重综合分与评级映射
- `src/cli.py` + `src/tools/` — 命令行总入口与确定性数据工具契约

## 常用命令

- 依赖与运行：`python3 scripts/uv_sync.py`（或 `uv sync`） · `uv run python -m src.cli`（或 `alpha-jerry`）
- 质量检查：`uv run ruff check .` · `uv run ruff format .` · `uv run pytest -m "not network" --cov=src --cov-fail-under=80`
- 业务流水线：`uv run python scripts/full_collect.py` · `scripts/full_scores.py` · `scripts/full_report.py`
- 修改验证：1. `ruff check .` 无警告；2. `pytest` not network 覆盖率 ≥80%；3. `python -c "from src.config import Settings; Settings()"` 可加载

## 核心原则与硬约束

- **最小干预**：只改用户明确指令范围；发现其他问题报告而不顺手修。
- **测试驱动实现**：新功能先写/补单元测试并自动跑通，再改业务代码去满足测试；跨模块行为最后用集成测试锁，禁止先堆实现再补测、禁止改测试去迁就实现。
- **包边界显式**：`src/` 与 `tests/` 所有子目录必须包含 `__init__.py`，禁止隐式命名空间包。
- **单文件 ≤ 300 行**：逻辑清晰单一（`contract.py` 字段定义除外），模块膨胀及时拆分。
- **命名对齐**：源码 `src/a/b.py` ↔ 测试 `tests/a/test_b.py` ↔ 产物 `data/fin/YYMMDD.csv`。
- **导入三段式**：顶部标准库 → 第三方库 → 本地模块；禁止循环引用与随意懒加载。
- **无叙述型注释**：代码抬头 3 行内 docstring；不写“定义函数/返回结果”等废话注释，仅说明设计意图与边界。
- **原子提交**：单提交单功能（≤ 20 文件），提交前必跑修改验证，直推 `main`。

## 工作流程与验证清单

1. **对齐需求**：对照 `ROADMAP.md` 明确归属需求（1/2/3），查阅相关代码与单测。
2. **单测 → 业务对齐 → 集成测试**：功能类先写/补单元测试并跑通，再改业务代码满足测试，多功能/跨模块最后用集成测试锁。
3. **验证门禁**：
   - [ ] `uv run ruff check .` 与 `uv run ruff format --check .` 均通过
   - [ ] `uv run pytest -m "not network" --cov=src --cov-fail-under=80` 覆盖率达标
   - [ ] 关键阈值边界（8.5 / 7.0 / 5.5）均有测试用例
   - [ ] 新增字段与配置已同步 `contract.py` 与 `.env.example`，无硬编码
   - [ ] 文件读写显式 `encoding="utf-8"`，路径全 `pathlib.Path`
4. **提交推送**：规范 commit message 说明目的、摘要与验证，推送到 `origin main`。

## 常见任务

- **新增评分规则**：确认 `brd.md`（RIGID）→ `test_scores.py` 写阈值边界单测并跑通 → `scores.py` 实现纯函数对齐测试 → 跨步骤用集成测试锁。
- **新增字段/接口**：先写/补 `tests/data/` 单测（字段、映射、契约）并跑通 → `contract.py` / `provider.py` 对齐实现 → mock/network 集成测试锁跨模块。
- **新增 CLI 子命令**：先写/补单测锁入参、JSON 出参与退出码并跑通 → `src/tools/` + `src/cli.py` 对齐实现 → 集成测试锁端到端。
- **更新锐评模型/Prompt**：先写/补单元测试与黄金样本并跑通 → `src/llm/` 与 `Settings` 对齐双 Provider → CI / 集成测试做回归。

## 安全与运行约束

- **敏感信息零暴露**：不读取 `.env` 内容，仅经 `get_settings()` 检查属性；密钥绝对不进日志、trace 与终端。
- **数据与模型隔离**：数据本地存储；LLM 上下文仅传必要特征子集，严禁全量 460 字段裸传。
- **Windows / macOS 双端适配**：终端入口统一 `sys.stdout.reconfigure(encoding="utf-8")`；无 ANSI 支持环境退化纯 ASCII。
- **路线图保护**：严禁擅自修改或打勾 `ROADMAP.md`，需求变更与进度确认权在用户。
