# Changelog

本文件记录 alpha-jerry 的所有显著变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed (M1)

- **VIP 接口取全量字段**：`income_vip` / `balancesheet_vip` / `cashflow_vip` / `fina_indicator_vip` 不再传 `fields` 参数，直接获取各接口全部默认字段，输出列从 44 列扩展至 ~460 列。
- `StockFeatures` 采用 `ConfigDict(extra="allow")` + 显式声明评分所需字段，其余字段由模型动态接受。
- `FIELD_CN` / `FIELD_UNIT`（全量字段→中文/单位映射）从独立文件 `field_mappings.py` 合并入 `contract.py`。

## 版本规划

- `0.1.0` — M0 工程骨架（目录/AGENTS.md/pyproject/Settings/CI）
- `0.2.0` — M1 数据采集（Tushare 适配 + 特征字段落地）
- `0.3.0` — M2 评分评级（纯函数 + 单测 + 行业权重 + 否决）
- `0.4.0` — M3 报告输出（荐股 Top20 + 持仓表）
