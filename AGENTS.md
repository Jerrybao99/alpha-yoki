# AGENTS.md

> alpha-jerry 项目级 AI 行为规范，作为项目的上下文入口。记录业务意图、关键决策与管道逻辑。
> 只放影响 AI 行为的指令（缺了就会做错或必须遵守的刚性规则）。冲突时项目级优先（就近原则）。
> 单文件尽可能 300 行内，越少越好。

## 业务意图

alpha-jerry 是面向 A 股基本面分析的 AI Native 工具集，覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送通知"完整闭环。帮助个人投资者识别优质公司并持续监控持仓风险。

- 本地优先：数据本地存储，不上传云端（NFR-01）。
- 非套壳 Agent：多 Agent 编排 + RAG + 路由 + 工具 + 记忆 + 监控 + 反馈（C-03）。
- 规则可审计：评分/评级走纯函数 + 单测，一票否决可追溯。

完整业务规则见 [docs/dev-guide.md](docs/dev-guide.md) §8（RIGID 契约）。

## 管道逻辑

```
全 A 股清单 → 采集(Tushare) → data/fin/YYMMDD.csv
  → 评分(否决→三维→行业权重→综合分) → data/fin/YYMMDD-评分.csv
  → 评级(四级+AI点评)              → data/fin/YYMMDD-评级.csv
  → 报告(Top20荐股+持仓表)         → data/analysis/YYMMDD-荐股.csv / data/hold/
每日 09:00/17:00 → 热点追踪 + 持股分析 → 推送(邮件/微信)
```

数据子目录英文简写：`fin`(财务) / `analysis`(荐股) / `hold`(持股) / `hot`(热点) / `monitor`(监控) / `feedback`(反馈) / `rag`(知识库)。文件名后缀（-评分/-评级/-荐股）保留中文。

## Commands

- 安装依赖: `uv sync`
- 运行测试: `uv run pytest -m "not network"`
- Lint: `uv run ruff check .`
- 格式化: `uv run ruff format .`
- 运行应用: `uv run python src/main.py`

## Stack

- Runtime: Python 3.12+
- Package Manager: uv
- LLM: DeepSeek V4 Pro（OpenAI 兼容接口，C-04）
- 数据源: Tushare Pro（C-05）
- Agent 框架: LangGraph 0.2+
- RAG: ChromaDB + bge-small-zh（本地）
- 后端 API: FastAPI 0.110+
- 桌面端: Electron + React + Vite
- 配置: pydantic-settings + `.env`
- 测试: pytest 8+；Lint/Format: ruff

## Key Files

- `docs/dev-guide.md` — 单一事实来源（业务规则 §8 RIGID / 里程碑 §13 / 验证门禁 §12）
- `docs/ROADMAP.md` — M0~M7 断点学习路线图
- `src/config.py` — 全局配置入口（Settings 类）
- `pyproject.toml` — 依赖与工具配置
- `.env.example` — 配置样板（新增配置项必须同步）

## Constraints

- 不阅读 `dev-log.md`、`.env`（含 API Key/Token 等敏感凭据）；需要配置值时通过 `Settings` 读取（如 `get_settings().tushare_token`），仅查看长度/是否为空等非敏感属性，禁止 read/cat/print 其内容。
- 代码文件抬头注释三句话简要写明该代码功能。
- 业务规则（docs/dev-guide.md §8）不可漂移；与代码冲突时改代码不修规则，除非业务评审通过并记录于 CHANGELOG。
- 评分/评级/权重为纯函数，单测覆盖全部阈值边界（8.5/7.0/5.5 等）（§6.3 原则 4）。
- 配置抽离：路径/超时/模型/API Key 全走 `Settings`，禁止硬编码。
- 数据目录小写 `data/`，子目录英文简写（见管道逻辑）；`.env` 不入库，新增配置项须同步 `.env.example`。
- 单 PR 单功能，≤ 20 文件；不含构建产物（`__pycache__/`/`node_modules/`/`build/`/`dist/`）。
- 数据源固定 Tushare（C-05）；预留 `BaseFetcher` 抽象便于未来扩展。
- 关键决策走规则引擎，LLM 仅生成文案并由规则校验（防幻觉，R-04）。

## Verification

修改代码后必须运行：

1. `uv run ruff check .` — 无新警告
2. `uv run pytest -m "not network"` — 测试通过
3. `uv run python -c "from src.config import Settings; print(Settings())"` — 配置可加载

涉及业务规则（§8）的改动，须补纯函数单测对齐阈值边界。
