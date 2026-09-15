# alpha-jerry

![alpha-jerry](assets/icon/alpha-jerry-logo.png)

本地 CLI：Tushare 采集 → 规则评分 → DeepSeek / GLM 锐评，输出荐股 Top20。数据只留在本机。

## 快速开始

需要 [Tushare](https://tushare.pro) VIP（5000 积分）和 DeepSeek 或 GLM 的 API Key。Windows / macOS，`uv sync` 会装好 Python 3.12。

先进入本仓库目录。入口是 `uv run alpha-jerry`，换目录会找不到命令。

```bash
cd /path/to/alpha-jerry
uv sync
cp .env.example .env
# 填写 TUSHARE_TOKEN，以及 DEEPSEEK_API_KEY 或 GLM_API_KEY

uv run alpha-jerry --help               # 查看全部命令
uv run python scripts/sw_industry.py    # 首次约 11 分钟
uv run alpha-jerry collect
uv run alpha-jerry scores
uv run alpha-jerry report --provider deepseek
```

产物在 `data/fin/`。

## 免责声明

输出仅供参考，不构成投资建议。
