# alpha-yoki

![alpha-yoki](assets/icon/alpha-yoki-logo.png)

本地 CLI：Tushare 采集 → 规则评分 → DeepSeek / GLM 锐评，输出荐股 Top50（13 列）。产物只写本机 `data/`。

## 第一次跑通

需要 Python 3.12、[uv](https://docs.astral.sh/uv/)、[Tushare](https://tushare.pro) VIP（5000 积分），以及 DeepSeek 或 GLM 的 API Key。Windows / macOS 均可。

先进入本仓库目录。入口是 `uv run alpha-yoki`，换目录会找不到命令。

```bash
cd /path/to/alpha-yoki
python3 scripts/uv_sync.py              # 装依赖；没有 uv 先装 https://docs.astral.sh/uv/ 。Windows 可用 py -3 scripts/uv_sync.py
cp .env.example .env                    # 复制配置样板，下一步填密钥
```

打开 `.env`，至少填数据源 + 一家模型：

1. `TUSHARE_TOKEN`：登录 [tushare.pro](https://tushare.pro) 复制 token。VIP 接口要 **5000** 积分。
2. `DEEPSEEK_API_KEY`：在 [DeepSeek 开放平台](https://platform.deepseek.com) 创建。
3. `GLM_API_KEY`：在 [智谱开放平台](https://open.bigmodel.cn) 创建。

两家模型填一家即可。密钥不要写在命令行参数里。也可以不写进 `.env`：第一次跑 `report` 时终端会隐藏输入，并可存到 macOS 钥匙串 / Windows 凭据管理器。

```bash
uv run python scripts/sw_industry.py    # 首次必做，约 11 分钟；CLI collect 不会自动补这份缓存
uv run alpha-yoki collect              # 全量采集，批量模式通常数分钟；中断后续跑 --resume
uv run alpha-yoki scores
uv run alpha-yoki models use glm       # 或 deepseek；只记偏好，不调模型
uv run alpha-yoki report               # 调 LLM，写出 Top50
```

成功：打开 `data/fin/full_report/` 里当天的 `YYMMDD.csv` 与同名 `.md`，最多 50 只、13 列。评分在 `data/fin/full_scores/`，采集在 `data/fin/full_collect/`。

## 命令速查

```bash
uv run alpha-yoki --help                         # 查看全部命令
uv run alpha-yoki status                         # 看采集 / 评分 / 报告是否过期
uv run alpha-yoki status --check                 # 过期或缺失时退出码 4，给定时任务用
uv run alpha-yoki collect                        # 全量采集财务特征（含股东户数）
uv run alpha-yoki collect --update               # 数据过期或缺失才采集
uv run alpha-yoki collect --force                # 忽略新鲜度，强制重采
uv run alpha-yoki collect --resume               # 断点续采，跳过当日已有股票
uv run alpha-yoki collect --codes 600519.SH      # 只采指定股票
uv run alpha-yoki scores                         # 对最新采集结果评分
uv run alpha-yoki scores --codes 600519.SH       # 只评指定股票
uv run alpha-yoki screen --industry 白酒 --rating 买入  # 按行业 / 评级筛选，不联网
uv run alpha-yoki holdings list                  # 查看本地持仓
uv run alpha-yoki holdings add 600519.SH         # 加入持仓
uv run alpha-yoki holdings remove 600519.SH      # 移除持仓
uv run alpha-yoki models                         # 查看模型目录与当前偏好
uv run alpha-yoki models use glm                 # 记住用 GLM（.env 默认型号），不跑锐评
uv run alpha-yoki models use deepseek            # 记住用 DeepSeek
uv run alpha-yoki models use glm glm-5-turbo     # 记住用指定型号
uv run alpha-yoki report                         # 用已记住的模型生成 Top50 锐评（会调 LLM）
uv run alpha-yoki report --provider glm          # 单次覆盖 Provider，不改记忆时加 --no-save
uv run alpha-yoki wechat login                   # 生成二维码，用微信 Cloud Bot 扫码
uv run alpha-yoki wechat serve                   # 长轮询收微信消息并回复
uv run alpha-yoki wechat status                  # 查看微信登录状态
uv run alpha-yoki wechat push --text "你好"      # 向最近会话推一条文本
```

`models use` 只改本地偏好。`report --provider` / `--model` 仍可单次覆盖。产物在 `data/fin/`。`--json` 只出信封；退出码 0 成功、2 配置、3 上游、4 数据缺失或过期。

## 可选：微信

本仓库直连腾讯 iLink（微信 Cloud Bot / ClawBot），不经过 OpenClaw。需要手机微信已开通该插件（常见于较新的 iOS 微信）。先在本机跑通采集 / 评分 / 报告，再开微信。

```bash
uv run alpha-yoki wechat login         # 生成本机二维码 data/wechat/qrcode.png
# 用微信 Cloud Bot / ClawBot 扫码并确认；token 进系统钥匙串，会话进 data/wechat/session.json
uv run alpha-yoki wechat status        # logged_in 应为 true；false 就再 login
uv run alpha-yoki wechat serve         # 保持运行，才能收消息、回复，以及定时摘要
```

默认只回复扫码的那个人。要加其他人，把对方的 `ilink_user_id` 填进 `.env` 的 `WECHAT_ALLOWED_USERS`。会话过期就重新 `wechat login`。

微信里：

- 只读，直接回复：帮助 / 状态 / 报告 / 摘要 / 持仓 / 查 600519 / 筛选 白酒
- 需确认：更新 / 全量采集 / 评分 / 锐评 / 加仓 600519 / 减仓 600519

「报告」「摘要」只读本机已生成的 Top50，转成 Markdown 发回，并落盘到 `data/fin/full_report/YYMMDD.md`（与同名 CSV 并列）。不跑 LLM。重新锐评请在本机执行 `alpha-yoki report`，或微信里说「锐评」。

`serve` 挂着时，默认每天 09:00、17:00 推一条新鲜度 + 持仓摘要（`WECHAT_DIGEST_TIMES`）。

## 免责声明

输出仅供参考，不构成投资建议。
