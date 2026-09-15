"""荐股 Top20 兼容脚本；交互入口优先使用 ``alpha-jerry report``。"""

from __future__ import annotations

from src.config import get_settings
from src.data.readers import find_latest_csv
from src.llm.client import LLMClient
from src.llm.credentials import CredentialError, resolve_api_key
from src.llm.review import build_fallback_client
from src.reports.generator import build_top20
from src.reports.reporting import write_recommend_csv

__all__ = ["build_top20", "main"]


def main() -> None:
    """读取最新评分 CSV，并使用配置的默认 Provider（含备用 Provider）生成报告。"""
    settings = get_settings()
    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = find_latest_csv(scoring_dir)
    if csv_path is None:
        raise SystemExit("无评分 CSV，请先运行 full_scores.py")

    provider = settings.llm_provider
    try:
        api_key = resolve_api_key(provider, settings=settings)
        client = LLMClient(
            provider=provider,
            api_key=api_key,
            settings=settings,
        )
        fallback_client = build_fallback_client(
            provider, settings.review_fallback_provider, settings=settings
        )
    except CredentialError as exc:
        raise SystemExit(str(exc)) from exc

    result = build_top20(
        csv_path, client=client, fallback_client=fallback_client, settings=settings
    )
    out_dir = settings.data_path("fin") / "full_report"
    out_path = write_recommend_csv(result, out_dir / f"{csv_path.stem}.csv")
    print(f"荐股 Top20 产出：{out_path}")


if __name__ == "__main__":
    main()
