"""Step 3.3 荐股 Top20 集成测试。真实评分数据 + LLM 调用，校验 13 列完整、
亮点≤120 字、风险提示≤120 字、点评≤180 字。CI 通过 ``-m 'not network'`` 跳过。
"""

from __future__ import annotations

import pytest

from scripts.full_report import build_top20
from scripts.full_scores import _find_latest
from src.config import get_settings
from src.reports.reporting import OUTPUT_HEADERS_CN, write_recommend_csv

# ===== network 测试 =====


@pytest.mark.network
def test_real_recommend_top20() -> None:
    """真实评分数据 + LLM 调用，生成荐股 Top20 CSV。

    ``uv run pytest -m network integrated_tests/test_full_report.py::test_real_recommend_top20``
    """
    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")
    if not settings.deepseek_api_key.strip():
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = _find_latest(scoring_dir)
    if csv_path is None:
        pytest.skip("无评分 CSV，请先运行 full_scores.py")

    print(f"评分数据：{csv_path}")
    result = build_top20(csv_path)

    assert len(result.rows) > 0, "荐股 Top20 为空"
    assert len(result.rows) <= 20

    for i, row in enumerate(result.rows, start=1):
        for h in OUTPUT_HEADERS_CN:
            assert h in row, f"第 {i} 行缺少列 {h}"

        assert row["核心亮点"], f"第 {i} 行核心亮点为空"
        assert row["风险提示"], f"第 {i} 行风险提示为空"
        assert row["点评"], f"第 {i} 行点评为空"
        assert len(row["核心亮点"]) <= 120, (
            f"第 {i} 行核心亮点超长: {len(row['核心亮点'])}字"
        )
        assert len(row["风险提示"]) <= 120, (
            f"第 {i} 行风险提示超长: {len(row['风险提示'])}字"
        )
        assert len(row["点评"]) <= 180, f"第 {i} 行点评超长: {len(row['点评'])}字"
        assert row["综合分"], f"第 {i} 行综合分为空"
        assert row["评级"], f"第 {i} 行评级为空"
        assert row["公司类型"], f"第 {i} 行公司类型为空"
        assert row["操作建议"], f"第 {i} 行操作建议为空"

        print(
            f"  [{i}] {row['股票名称']} | {row['评级'].encode('ascii', errors='replace').decode('ascii')} | {row['公司类型'].encode('ascii', errors='replace').decode('ascii')} | 亮点:{row['核心亮点'][:20]}..."
        )

    # 输出 CSV 到 data/test/full_report/
    out_dir = settings.data_root / "test" / "full_report"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = write_recommend_csv(result, out_dir / "260728.csv")
    print(f"荐股 Top20 产出：{out_path}")


@pytest.mark.network
def test_recommend_top3_quick_smoke() -> None:
    """快速冒烟：只跑前 3 名，验证 LLM 调用链路正常。

    ``uv run pytest -m network integrated_tests/test_full_report.py::test_recommend_top3_quick_smoke``
    """
    settings = get_settings()
    if not settings.deepseek_api_key.strip():
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = _find_latest(scoring_dir)
    if csv_path is None:
        pytest.skip("无评分 CSV")

    from scripts.full_report import _generate_single
    from src.agents.llm_adapter import LLMClient
    from src.reports.evaluation import classify_company_type
    from src.reports.reporting import (
        build_llm_context,
        load_scoring_rows,
        make_features,
        parse_back,
    )

    rows = load_scoring_rows(csv_path)
    parsed = sorted(
        [(r, parse_back(r)) for r in rows],
        key=lambda x: float(x[1].get("综合分", 0) or 0),
        reverse=True,
    )
    client = LLMClient()

    for i, (raw, p) in enumerate(parsed[:3], start=1):
        feat = make_features(p)
        company = classify_company_type(feat)
        context = build_llm_context(
            p,
            p.get("成长性"),
            p.get("稳健性"),
            p.get("资金回报"),
            p.get("综合分"),
            str(p.get("评级", "")),
            company.type_label,
        )

        hl = _generate_single(
            client,
            "你是资深A股基本面分析师。基于数据提炼核心亮点，直接输出精炼中文。",
            f"总结这只股票的核心亮点：\n\n{context}",
            300,
            120,
        )
        assert hl, f"第 {i} 名亮点为空: {p.get('name')}"
        print(f"  [{i}] {p.get('name')} 亮点: {hl[:60]}...")
