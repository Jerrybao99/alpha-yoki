"""锐评契约单测：可引用数字集合、指标渲染、序列化稳定性。"""

from __future__ import annotations

import json

from src.llm.contracts import (
    REVIEW_FIELDS,
    Flag,
    FlagCode,
    Metric,
    ReviewDraft,
    ReviewFacts,
    ReviewResult,
    ReviewStatus,
)


def _facts(**overrides) -> ReviewFacts:
    values = {
        "code": "000807",
        "name": "云铝股份",
        "industry": "周期资源",
        "company_type": "现金牛",
        "rating": "皇冠明珠",
        "advice": "重仓买入",
        "position": "10-20%",
        "composite": 9.5,
        "growth": 8,
        "stability": 10,
        "return_score": 10,
        "metrics": (
            Metric("or_yoy", "营收同比", 20.30, "%", signed=True),
            Metric("netprofit_yoy", "归母净利同比", 177.61, "%", signed=True),
            Metric("roe", "ROE", 21.89, "%"),
            Metric("free_cashflow", "自由现金流", -13.456, "亿元", signed=True),
        ),
        "flags": (Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def test_review_fields_order_matches_output_columns() -> None:
    assert REVIEW_FIELDS == ("highlight", "risk", "comment")


def test_metric_render_signed_and_unsigned() -> None:
    assert (
        Metric("or_yoy", "营收同比", 20.30, "%", signed=True).render()
        == "营收同比+20.3%"
    )
    assert (
        Metric("or_yoy", "营收同比", -5.25, "%", signed=True).render()
        == "营收同比-5.2%"
    )
    assert Metric("roe", "ROE", 21.89, "%").render(2) == "ROE 21.89%"
    assert Metric("current_ratio", "流动比率", 3.2, "倍").render() == "流动比率3.2倍"


def test_allowed_numbers_cover_rounding_variants() -> None:
    allowed = _facts().allowed_numbers()
    assert {20.3, 20.0, 177.61, 177.6, 178.0, 21.89, 21.9, 22.0} <= allowed


def test_allowed_numbers_include_scores_and_absolute_values() -> None:
    allowed = _facts().allowed_numbers()
    assert {9.5, 8.0, 10.0} <= allowed
    assert 13.46 in allowed and 13.5 in allowed and 13.0 in allowed
    assert 807.0 in allowed


def test_allowed_numbers_reject_derived_values() -> None:
    allowed = _facts().allowed_numbers()
    assert 3.0 not in allowed
    assert 12.0 not in allowed


def test_allowed_numbers_skip_missing_scores() -> None:
    allowed = _facts(growth=None, stability=None, return_score=None).allowed_numbers()
    assert 9.5 in allowed
    assert 8.0 not in allowed


def test_to_dict_is_json_serializable_and_stable() -> None:
    facts = _facts()
    first = json.dumps(facts.to_dict(), ensure_ascii=False, sort_keys=True)
    second = json.dumps(_facts().to_dict(), ensure_ascii=False, sort_keys=True)
    assert first == second
    assert '"code": "cyclical"' in first


def test_review_draft_get_by_field() -> None:
    draft = ReviewDraft(highlight="亮点", risk="风险", comment="点评")
    assert [draft.get(name) for name in REVIEW_FIELDS] == ["亮点", "风险", "点评"]


def test_review_status_values_are_english_enums() -> None:
    assert {status.value for status in ReviewStatus} == {
        "success",
        "retry",
        "switched",
        "fallback",
        "cache_hit",
    }


def test_review_result_defaults() -> None:
    result = ReviewResult(
        highlight="a", risk="b", comment="c", status=ReviewStatus.FALLBACK
    )
    assert result.attempts == 0
    assert result.violations == ()
    assert result.status == "fallback"
