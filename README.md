# alpha-jerry

> A 股基本面分析的本地命令行工具：Tushare 采集 → 一票否决 → 三维评分 → 行业加权评级 → LLM 锐评，帮助个人投资者识别优质公司。数据本地存储，仅 LLM 推理外联。

**当前阶段**：采集 / 评分 / 荐股 Top20 内核已完成，`alpha-jerry report` 支持 DeepSeek / GLM 交互选择与系统钥匙串存储。其余 CLI 工具与 banner 仍在推进。

## 快速开始

支持 Windows / macOS；Python 3.12 由 `.python-version` 固定，`uv sync` 自动下载。

```bash
uv sync                                              # 安装依赖 + Python 3.12
cp .env.example .env                                 # 采集需填 TUSHARE_TOKEN

uv run python scripts/sw_industry.py                 # 申万行业缓存（首次 ~11 分钟）
uv run python scripts/full_collect.py                # 全量批量采集 → data/fin/full_collect/
uv run python scripts/full_scores.py                 # 评分评级 → data/fin/full_scores/
uv run alpha-jerry models                            # 查看模型 ID、端点与默认配置
uv run alpha-jerry report                            # 交互选择 Provider + 具体模型 → Top20
uv run alpha-jerry report --provider glm --model glm-5-turbo
uv run python scripts/full_report.py                 # 兼容入口，使用 LLM_PROVIDER
uv run python scripts/smoke_collect.py --sample 5    # 随机 5 股冒烟

uv run pytest -m "not network"                       # mock 测试（CI 同款）
uv run ruff check . && uv run ruff format --check .  # lint + 格式
```

`alpha-jerry report` 已落地；`status / collect / scores / screen / holdings` 与 `--json` 仍属路线图需求 1。

### API Key 本地存储

- 环境变量或 `.env` 中的 `DEEPSEEK_API_KEY` / `GLM_API_KEY` 优先。
- 未配置时，交互终端使用隐藏输入，并可保存到 macOS Keychain 或 Windows Credential Locker。
- API Key 不支持命令行参数，避免进入 shell history；非交互环境必须预先配置密钥。

### 模型与接口

模型目录于 2026-09-15 根据官网正文、接口示例与价格页交叉核验；可用 `--model` 输入后续发布的自定义模型 ID。

- DeepSeek：`deepseek-flash`（默认，V4.1 Flash）/ `deepseek-v4-pro`；OpenAI Base URL 为 `https://api.deepseek.com`。两者均支持 1M 上下文、最大 384K 输出、思考开关及 `low/high/max` 推理强度，详见 [官方模型与价格](https://api-docs.deepseek.com/quick_start/pricing)。
- 智谱 GLM：`glm-5.3-flash`（默认）/ `glm-5.3` / `glm-5.2` / `glm-5-turbo` / `glm-5.1` / `glm-5`；OpenAI Chat Base URL 为 `https://open.bigmodel.cn/api/paas/v4/`，详见 [官方模型概览](https://docs.bigmodel.cn/cn/guide/start/model-overview)。
- `glm-5.3` 与 `glm-5.3-flash` 均支持 1M 上下文和最大 128K 输出，强制开启思考，推理强度为 `low/high/max`；Flash 额外支持图片、视频和文件输入。

### 模型选择与自动记忆

- 首次运行 `uv run alpha-jerry report` 会依次显示 Provider 与模型菜单；选择后自动保存到 `data/cache/llm_preferences.json`。
- 之后运行无需选择，自动沿用上次选择；`.env` 中的 `DEEPSEEK_MODEL` / `GLM_MODEL` 仅作为无偏好时的兜底。
- 本次不想覆盖记忆时使用 `--no-save`；显式传 `--provider` 时仍会在运行后更新记忆。

### macOS 注意

- shell 设了 `all_proxy=socks5://...` 时，openai SDK 依赖的 `socksio` 已随 `httpx[socks]` 内置，无需处理
- 系统自带 Python 3.9 不满足要求，无需手动安装，`uv sync` 会按 `.python-version` 下载 3.12

## 技术栈

Python 3.12 · uv · pydantic-settings · Tushare Pro · DeepSeek / GLM（OpenAI 兼容接口）· keyring · pytest · ruff

规划：完整 argparse CLI · OpenClaw 作为对话 / 微信 / 定时外壳（Skill / MCP）

## 项目结构

```
src/
├── cli.py           # alpha-jerry report 入口
├── config.py        # Settings 全局配置
├── data/            # 采集：contract / provider / collect / output
├── scoring/         # 评分：scores（纯函数）
├── reports/         # 报告：evaluation / reporting（纯函数）
├── llm/             # 双 Provider 客户端 + 系统钥匙串凭据
└── agents/          # 旧 LLM 导入路径兼容层
scripts/             # I/O 编排：full_collect / full_scores / full_report / smoke_collect / sw_industry
tests/               # 单元测试，镜像 src/
integrated_tests/    # 集成测试（mock + network）
data/                # 运行期数据，不入库（fin / ref / cache / test）
docs/                # brd（业务 + RIGID 规则）
```

规划新增：其余 CLI 子命令 · `src/tools/` · `src/banner.py` · `assets/icon/`。

## 核心流程

```
stock_basic → 4 个 VIP 接口批量采集（~460 字段）→ check_veto() 一票否决
→ 三维评分 → score_composite() 行业加权 → score_rating() 四级评级
→ 公司类型 + 操作建议 → LLM 亮点 / 风险 / 点评 → 荐股 Top20（13 列）
```

## 定位

- **本地优先**：数据不上云，仅 LLM 推理外联
- **规则可审计**：否决 / 评分 / 评级为纯函数 + 全阈值边界单测
- **组合已有，不自研 Agent**：本项目只做内核、LLM 锐评子系统与 CLI 工具封装；对话外壳交给 OpenClaw

## 免责声明

本项目输出仅供参考，不构成投资建议。投资决策由用户自行完成并自担风险。
