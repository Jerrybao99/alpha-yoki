"""ReviewFacts 装配单测：指标白名单与缩放、风险标记阈值边界、盯住变量映射。"""

from __future__ import annotations

from src.data.contract import StockFeatures
from src.llm.contracts import FlagCode
from src.reports.evaluation import (
    CAT_CYCLICAL,
    CAT_TECH,
    TYPE_HUCHENGHE,
    TYPE_QIANLIMA,
    TYPE_XIANJINNIU,
    AdviceResult,
    CompanyTypeResult,
)
from src.reports.facts import (
    EXTREME_ROE,
    HIGH_LEVERAGE_DEBT_TO_ASSETS,
    LOW_BASE_NETPROFIT_YOY,
    WEAK_DIMENSION_SCORE,
    build_metrics,
    build_review_facts,
    derive_flags,
    watch_variable_for,
)


def _features(**overrides) -> StockFeatures:
    values = {
        "ts_code": "000807.SZ",
        "name": "云铝股份",
        "industry": CAT_CYCLICAL,
        "or_yoy": 20.30,
        "netprofit_yoy": 177.61,
        "grossprofit_margin": 31.84,
        "debt_to_assets": 15.80,
        "current_ratio": 3.2,
        "roe": 21.89,
        "free_cashflow": 1.234e9,
        "eps": 2.22,
    }
    values.update(overrides)
    return StockFeatures(**values)


def _codes(flags) -> list[FlagCode]:
    return [flag.code for flag in flags]


# ===== build_metrics =====
def test_build_metrics_order_and_scaling() -> None:
    metrics = build_metrics(_features())
    keys = [m.key for m in metrics]
    assert keys == [
        "or_yoy",
        "netprofit_yoy",
        "grossprofit_margin",
        "roe",
        "debt_to_assets",
        "current_ratio",
        "free_cashflow",
        "eps",
    ]
    cashflow = next(m for m in metrics if m.key == "free_cashflow")
    assert cashflow.value == 12.34
    assert cashflow.unit == "亿元"


def test_build_metrics_skips_missing_values() -> None:
    metrics = build_metrics(_features(eps=None, free_cashflow=None))
    assert {m.key for m in metrics} == {
        "or_yoy",
        "netprofit_yoy",
        "grossprofit_margin",
        "roe",
        "debt_to_assets",
        "current_ratio",
    }


def test_build_metrics_marks_leverage_metrics_not_highlightable() -> None:
    metrics = {m.key: m for m in build_metrics(_features())}
    assert metrics["or_yoy"].highlightable is True
    assert metrics["debt_to_assets"].highlightable is False
    assert metrics["current_ratio"].highlightable is False


# ===== derive_flags 阈值边界 =====
def test_low_base_flag_boundary() -> None:
    at = derive_flags(
        _features(netprofit_yoy=LOW_BASE_NETPROFIT_YOY, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    above = derive_flags(
        _features(netprofit_yoy=LOW_BASE_NETPROFIT_YOY + 0.01, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    assert FlagCode.LOW_BASE not in _codes(at)
    assert FlagCode.LOW_BASE in _codes(above)
    note = next(f.note for f in above if f.code == FlagCode.LOW_BASE)
    assert "500.0%" in note and "低基数" in note


def test_high_leverage_flag_boundary() -> None:
    at = derive_flags(
        _features(debt_to_assets=HIGH_LEVERAGE_DEBT_TO_ASSETS, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    above = derive_flags(
        _features(debt_to_assets=HIGH_LEVERAGE_DEBT_TO_ASSETS + 0.1, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    assert FlagCode.HIGH_LEVERAGE not in _codes(at)
    assert FlagCode.HIGH_LEVERAGE in _codes(above)


def test_extreme_roe_flag_boundary() -> None:
    at = derive_flags(
        _features(roe=EXTREME_ROE, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    above = derive_flags(
        _features(roe=EXTREME_ROE + 0.5, industry=CAT_TECH),
        growth=8,
        stability=8,
        return_score=8,
    )
    assert FlagCode.EXTREME_ROE not in _codes(at)
    assert FlagCode.EXTREME_ROE in _codes(above)


def test_weak_dimension_flag_boundary_and_note() -> None:
    at = derive_flags(
        _features(industry=CAT_TECH),
        growth=WEAK_DIMENSION_SCORE,
        stability=10,
        return_score=10,
    )
    below = derive_flags(
        _features(industry=CAT_TECH),
        growth=10,
        stability=WEAK_DIMENSION_SCORE - 1,
        return_score=WEAK_DIMENSION_SCORE - 1,
    )
    assert FlagCode.WEAK_DIMENSION not in _codes(at)
    weak = [f for f in below if f.code == FlagCode.WEAK_DIMENSION]
    assert [f.note for f in weak] == ["稳健性评分6分为短板", "资金回报评分6分为短板"]


def test_weak_dimension_ignores_missing_scores() -> None:
    flags = derive_flags(
        _features(industry=CAT_TECH), growth=None, stability=None, return_score=None
    )
    assert FlagCode.WEAK_DIMENSION not in _codes(flags)


def test_cyclical_flag_only_for_cyclical_industry() -> None:
    cyclical = derive_flags(_features(), growth=8, stability=8, return_score=8)
    tech = derive_flags(
        _features(industry=CAT_TECH), growth=8, stability=8, return_score=8
    )
    assert FlagCode.CYCLICAL in _codes(cyclical)
    assert FlagCode.CYCLICAL not in _codes(tech)


def test_no_flags_for_clean_features() -> None:
    flags = derive_flags(
        _features(industry=CAT_TECH, netprofit_yoy=40.0, roe=18.0, debt_to_assets=30.0),
        growth=8,
        stability=8,
        return_score=8,
    )
    assert flags == ()


# ===== watch_variable_for =====
def test_watch_variable_by_company_type() -> None:
    assert watch_variable_for(TYPE_QIANLIMA, CAT_TECH) == "增速能否延续"
    assert watch_variable_for(TYPE_XIANJINNIU, CAT_TECH) == "现金流与分红稳定性"
    assert watch_variable_for(TYPE_HUCHENGHE, CAT_TECH) == "毛利率与品牌溢价能否维持"


def test_watch_variable_cyclical_overrides_type() -> None:
    assert watch_variable_for(TYPE_QIANLIMA, CAT_CYCLICAL) == "产品价格周期与盈利弹性"


# ===== build_review_facts =====
def test_build_review_facts_strips_emoji_and_assembles_rule_verdicts() -> None:
    facts = build_review_facts(
        _features(),
        growth=8,
        stability=10,
        return_score=10,
        composite=9.5,
        rating="\U0001f451 皇冠明珠",
        company=CompanyTypeResult(TYPE_XIANJINNIU, "行业默认"),
        advice=AdviceResult("重仓买入", "10-20%", "buy"),
    )
    assert facts.code == "000807"
    assert facts.name == "云铝股份"
    assert facts.company_type == "现金牛"
    assert facts.rating == "皇冠明珠"
    assert facts.advice == "重仓买入"
    assert facts.position == "10-20%"
    assert facts.composite == 9.5
    assert (facts.growth, facts.stability, facts.return_score) == (8, 10, 10)
    assert [m.key for m in facts.metrics][:2] == ["or_yoy", "netprofit_yoy"]
    assert FlagCode.CYCLICAL in _codes(facts.flags)
    assert facts.watch_variable == "产品价格周期与盈利弹性"


def test_build_review_facts_handles_float_scores_and_missing_name() -> None:
    facts = build_review_facts(
        _features(name="", industry=CAT_TECH),
        growth=8.0,
        stability=None,
        return_score=10.0,
        composite=8.8,
        rating="\u2b50 优秀白马",
        company=CompanyTypeResult(TYPE_QIANLIMA, "行业默认"),
        advice=AdviceResult("分批建仓", "5-10%", "accumulate"),
    )
    assert facts.name == ""
    assert (facts.growth, facts.stability, facts.return_score) == (8, None, 10)
    assert facts.rating == "优秀白马"
