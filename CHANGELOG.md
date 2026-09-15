# Changelog

本文件记录 alpha-yoki 的所有显著变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `models use`：终端切换并记住 DeepSeek / GLM 及具体型号，不必先跑 `report`
- `scripts/uv_sync.py`：按探测耗时选择官方 PyPI 或国内镜像后再 `uv sync`
- `collect --resume`：断点续采，跳过当日已有股票并合并写回

### Changed

- 荐股名单由 Top20 调整为 Top50；`report`、微信「报告 / 摘要」与并列 Markdown 均取前 50 并落盘
- README 改为第一次跑通路径，微信降为可选入口

## [1.0.0] - 2026-09-15

### Added

- README 补充微信扫码登录、`status --check` 定时示例，以及 Windows / macOS 双端注意事项
- CI 在 Ubuntu / Windows / macOS 上执行 ruff 与覆盖率 ≥80% 门禁

### Changed

- 将采集、评分、CLI 契约、banner 与微信 iLink 直连作为 1.0 稳定交付面

## [0.8.0] - 2026-09-15

### Added

- 本地直连腾讯 iLink Bot API：`wechat login | serve | push | status`
- 私聊指令路由（帮助 / 状态 / 报告 / 更新 / 持仓 / 加仓 / 减仓 / 查）与 09:00、17:00 定时摘要
- 会话元数据写入 `data/wechat/session.json`，token 仅存系统钥匙串；追踪日志脱敏追加

## [0.7.0] - 2026-09-15

### Added

- 侏儒兔 CLI banner：宽屏彩色 / 窄屏 🐰 / 纯 ASCII 三档，`--json` 与非 TTY 不打印
- 品牌资产 `assets/icon/`（PNG / ICO / ICNS）及 `scripts/build_icons.py`

## [0.6.0] - 2026-09-15

### Added

- `src/tools/` 契约与统一 JSON 信封：`status` / `collect` / `scores` / `screen` / `holdings` / `report` / `models`
- 全局 `--json`：只输出一份信封；退出码保持 0 / 2 / 3 / 4

### Changed

- `src/cli.py` 收缩为 argparse 解析与分发，业务逻辑迁入工具模块

## [0.5.0] - 2026-09-15

### Added

- 采集股东户数 `holder_num`（Tushare `stk_holdernumber`，失败不中断整批）
- `src/data/store.py`：人读 CSV 与 raw CSV 双落盘、raw 优先读取、新鲜度 `Freshness`

### Changed

- 评分与荐股优先读 raw，避免人读格式化往返损失精度

## [0.4.0] - 2026-09-15

### Added

- DeepSeek / GLM 双 Provider 锐评子系统：白名单校验、重试、跨模型切换、规则兜底、缓存与追踪
- `report` / `models` 交互选择与偏好记忆

[unreleased]: https://github.com/Jerrybao99/alpha-yoki/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Jerrybao99/alpha-yoki/compare/v0.8.0...v1.0.0
[0.8.0]: https://github.com/Jerrybao99/alpha-yoki/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Jerrybao99/alpha-yoki/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Jerrybao99/alpha-yoki/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Jerrybao99/alpha-yoki/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Jerrybao99/alpha-yoki/releases/tag/v0.4.0
