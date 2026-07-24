"""alpha-jerry 运行入口（dev-guide §10.3）。

M0 阶段：仅加载配置并打印状态，验证工程基线可用。
后续里程碑接入 pipeline / API / 调度。
"""

from __future__ import annotations

from src.config import get_settings


def main() -> None:
    settings = get_settings()
    print("alpha-jerry")
    print(f"  数据目录      : {settings.data_dir}")
    print(f"  DeepSeek 模型 : {settings.deepseek_model}")
    print(f"  Tushare 已配置: {'是' if settings.tushare_token else '否'}")
    print(f"  LLM 已配置    : {'是' if settings.deepseek_api_key else '否'}")


if __name__ == "__main__":
    main()
