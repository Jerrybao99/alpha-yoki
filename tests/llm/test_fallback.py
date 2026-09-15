"""规则模板兜底单测：无网络时产出的三段文案必须 100% 有据且通过白名单校验。"""

from __future__ import annotations

import pytest

from src.llm.contracts import Flag, FlagCode, Metric, ReviewFacts
from src.llm.fallback import NO_RISK_SENTENCE, render_fallback
from src.llm.validate import LIMITS, validate_draft


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
            Metric("grossprofit_margin", "毛利率", 31.84, "%"),
            Metric("roe", "ROE", 21.89, "%"),
            Metric("debt_to_assets", "资产负债率", 15.80, "%", highlightable=False),
            Metric("current_ratio", "流动比率", 3.2, "倍", highlightable=False),
            Metric("eps", "每股收益", 2.22, "元"),
        ),
        "flags": (),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def test_no_flags_yields_fixed_risk_sentence() -> None:
    draft = render_fallback(_facts())
    assert draft.risk == NO_RISK_SENTENCE


def test_highlight_uses_top_two_highlightable_metrics() -> None:
    draft = render_fallback(_facts())
    assert draft.highlight == "营收同比+20.3%，归母净利同比+177.6%"


def test_highlight_skips_negative_growth_and_leverage_metrics() -> None:
    facts = _facts(
        metrics=(
            Metric("or_yoy", "营收同比", -8.0, "%", signed=True),
            Metric("debt_to_assets", "资产负债率", 15.80, "%", highlightable=False),
            Metric("grossprofit_margin", "毛利率", 31.84, "%"),
            Metric("roe", "ROE", 21.89, "%"),
        )
    )
    assert render_fallback(facts).highlight == "毛利率31.8%，ROE 21.9%"


def test_highlight_avoids_numbers_already_used_in_risk() -> None:
    facts = _facts(
        flags=(
            Flag(FlagCode.LOW_BASE, "归母净利同比+177.6%含低基数效应，不可线性外推"),
        )
    )
    draft = render_fallback(facts)
    assert "177.6" in draft.risk
    assert draft.highlight == "营收同比+20.3%，毛利率31.8%"


def test_risk_joins_flag_notes_within_limit() -> None:
    facts = _facts(
        flags=(
            Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),
            Flag(FlagCode.HIGH_LEVERAGE, "资产负债率65.2%偏高"),
            Flag(FlagCode.WEAK_DIMENSION, "成长性评分6分为短板"),
        )
    )
    draft = render_fallback(facts)
    assert draft.risk.startswith("周期资源行业，盈利随产品价格波动")
    assert len(draft.risk) <= LIMITS["risk"][1]


def test_comment_states_type_and_watch_variable() -> None:
    draft = render_fallback(_facts())
    assert draft.comment == "周期资源现金牛，重点盯住产品价格周期与盈利弹性"


def test_no_metrics_falls_back_to_composite_sentence() -> None:
    draft = render_fallback(_facts(metrics=()))
    assert draft.highlight == "综合分9.5分，现金牛属性标的"


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"metrics": ()},
        {
            "metrics": (
                Metric("or_yoy", "营收同比", 136.26, "%", signed=True),
                Metric("netprofit_yoy", "归母净利同比", 71528.66, "%", signed=True),
                Metric("roe", "ROE", 80.02, "%"),
            ),
            "flags": (
                Flag(
                    FlagCode.LOW_BASE, "归母净利同比+71528.7%含低基数效应，不可线性外推"
                ),
                Flag(FlagCode.EXTREME_ROE, "ROE 80.0%处于极端高位，持续性存疑"),
            ),
            "industry": "科技/制造",
            "company_type": "千里马",
            "watch_variable": "增速能否延续",
        },
        {
            "metrics": (
                Metric("or_yoy", "营收同比", 20.30, "%", signed=True),
                Metric("netprofit_yoy", "归母净利同比", 177.61, "%", signed=True),
                Metric("debt_to_assets", "资产负债率", 65.2, "%", highlightable=False),
            ),
            "flags": (
                Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),
                Flag(FlagCode.HIGH_LEVERAGE, "资产负债率65.2%偏高"),
                Flag(FlagCode.WEAK_DIMENSION, "成长性评分6分为短板"),
                Flag(FlagCode.WEAK_DIMENSION, "稳健性评分5分为短板"),
            ),
            "growth": 6,
            "stability": 5,
        },
    ],
)
def test_fallback_always_passes_validation(overrides: dict) -> None:
    facts = _facts(**overrides)
    assert validate_draft(render_fallback(facts), facts) == []
