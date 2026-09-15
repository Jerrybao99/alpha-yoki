"""alpha-jerry 运行入口：加载配置并打印状态，验证工程基线可用。
CLI（alpha-jerry）落地前的最小入口。
"""

from __future__ import annotations

from src.config import get_settings
from src.llm.credentials import has_api_key


def main() -> None:
    settings = get_settings()
    print("alpha-jerry")
    print(f"  数据目录      : {settings.data_dir}")
    print(f"  默认 LLM      : {settings.llm_provider}")
    print(f"  DeepSeek 模型 : {settings.deepseek_model}")
    print(f"  GLM 模型      : {settings.glm_model}")
    print(f"  Tushare 已配置: {'是' if settings.tushare_token else '否'}")
    print(
        f"  DeepSeek Key  : {'是' if has_api_key('deepseek', settings=settings) else '否'}"
    )
    print(
        f"  GLM Key       : {'是' if has_api_key('glm', settings=settings) else '否'}"
    )


if __name__ == "__main__":
    main()
