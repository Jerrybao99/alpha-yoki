# alpha-jerry

> A 股基本面分析的 AI Native 工具集——覆盖"数据采集 → 个股评分 → 个股评级 → 报告输出 → 持仓监控 → 热点追踪 → 推送通知"完整业务闭环，帮助个人投资者识别优质公司并持续监控持仓风险。

**当前阶段**：M1 数据采集已完成，M2 评分评级待开发。

## 快速开始

```bash
uv sync                          # 安装依赖
cp .env.example .env             # 填入 TUSHARE_TOKEN
uv run python scripts/smoke_collect.py --sample 5   # 随机 5 股采集
uv run pytest -m "not network"   # 运行测试
```

## 技术栈

Python 3.12+ · uv · pydantic-settings · Tushare Pro · DeepSeek V4 Pro · pytest · ruff

## 项目结构

```
src/
├── config.py              # Settings 全局配置
├── main.py                # 运行入口
└── data/                  # 数据采集与输出
    ├── contract.py        # 字段契约（44 字段 + 55 需求对齐表）
    ├── provider.py        # Tushare 适配器 + 接口注册表 + 行业分类
    ├── collect.py         # 采集编排 + 缓存 + 报告期推算
    └── reports.py         # CSV 写盘 + 亿/万/百分比格式化
tests/                     # 单元测试（与 src/data/ 镜像）
integrated_tests/          # 集成测试
scripts/                   # 辅助脚本
docs/                      # 文档
```

## 定位

- **本地优先**：数据本地存储，不上传云端
- **规则可审计**：评分/评级走纯函数 + 单测，一票否决可追溯
- **非套壳 Agent**：多 Agent 编排 + RAG + 路由 + 工具 + 记忆 + 监控 + 反馈

## 文档

- [开发指南](docs/dev-guide.md) — 单一事实来源（业务规则 §8 RIGID）
- [路线图](docs/ROADMAP.md) — M0~M7 里程碑

## 免责声明

本项目输出仅供参考，不构成投资建议。投资决策由用户自行完成并自担风险。
