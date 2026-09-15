"""荐股 TopN 集成测试：真实评分数据 + 真实 LLM，校验 13 列完整、三列锐评满足白名单上限
（亮点≤30 字、风险≤40 字、点评≤50 字）且数字均可在事实中验证。CI 通过 ``-m 'not network'`` 跳过。
"""

from __future__ import annotations

import pytest

from scripts.full_report import build_top20
from scripts.full_scores import _find_latest
from src.config import get_settings
from src.llm.client import LLMClient
from src.llm.contracts import ReviewDraft, ReviewStatus
from src.llm.credentials import has_api_key
from src.llm.review import review
from src.llm.validate import LIMITS, validate_draft
from src.reports.generator import select_top
from src.reports.reporting import OUTPUT_HEADERS_CN, TOP_N, write_recommend_csv

# ===== network 测试 =====


@pytest.mark.network
def test_real_recommend_top20() -> None:
    """真实评分数据 + LLM 调用，生成荐股 TopN CSV。

    ``uv run pytest -m network integrated_tests/test_full_report.py::test_real_recommend_top20``
    """
    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")
    if not has_api_key("deepseek", settings=settings):
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = _find_latest(scoring_dir)
    if csv_path is None:
        pytest.skip("无评分 CSV，请先运行 full_scores.py")

    print(f"评分数据：{csv_path}")
    client = LLMClient(provider="deepseek", settings=settings)
    result = build_top20(csv_path, client=client, settings=settings)

    assert 0 < len(result.rows) <= TOP_N, f"荐股 Top{TOP_N} 为空或超限"
    assert len(result.statuses) == len(result.rows)

    for i, row in enumerate(result.rows, start=1):
        for h in OUTPUT_HEADERS_CN:
            assert h in row, f"第 {i} 行缺少列 {h}"
        for column, field in (
            ("核心亮点", "highlight"),
            ("风险提示", "risk"),
            ("点评", "comment"),
        ):
            assert row[column], f"第 {i} 行{column}为空"
            assert len(row[column]) <= LIMITS[field][1], f"第 {i} 行{column}超长: {len(row[column])}字"
        assert row["综合分"] and row["评级"] and row["公司类型"] and row["操作建议"]
        print(f"  [{i}] {row['股票名称']} | {result.statuses[i - 1]} | {row['核心亮点']}")

    fallback_count = result.statuses.count(ReviewStatus.FALLBACK.value)
    assert fallback_count < len(result.rows), "全部落入规则兜底，LLM 链路未生效"

    out_dir = settings.data_root / "test" / "full_report"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = write_recommend_csv(result, out_dir / f"{csv_path.stem}.csv")
    print(f"荐股 Top{TOP_N} 产出：{out_path}")


@pytest.mark.network
@pytest.mark.parametrize("provider", ["deepseek", "glm"])
def test_review_top3_quick_smoke(provider: str) -> None:
    """快速冒烟：只跑前 3 名，逐 Provider 验证 JSON 模式 + 白名单校验链路。

    ``uv run pytest -m network integrated_tests/test_full_report.py::test_review_top3_quick_smoke``
    """
    settings = get_settings()
    if not has_api_key(provider, settings=settings):
        pytest.skip(f"未配置 {provider} API Key")

    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = _find_latest(scoring_dir)
    if csv_path is None:
        pytest.skip("无评分 CSV")

    from src.reports.evaluation import classify_company_type, get_advice
    from src.reports.facts import build_review_facts

    client = LLMClient(provider=provider, settings=settings)
    for i, candidate in enumerate(select_top(csv_path, limit=3), start=1):
        parsed = candidate.parsed
        rating = str(parsed.get("评级") or "")
        facts = build_review_facts(
            candidate.features,
            growth=parsed.get("成长性"),
            stability=parsed.get("稳健性"),
            return_score=parsed.get("资金回报"),
            composite=candidate.composite,
            rating=rating,
            company=classify_company_type(candidate.features),
            advice=get_advice(rating),
        )
        result = review(facts, client)
        draft = ReviewDraft(result.highlight, result.risk, result.comment)
        assert validate_draft(draft, facts) == [], f"第 {i} 名输出未通过白名单校验"
        print(
            f"  [{i}] {facts.name} | {provider} | {result.status.value} | "
            f"{result.highlight} | {result.risk} | {result.comment}"
        )
