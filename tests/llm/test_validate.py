"""白名单校验单测：语言、数字一致性、长度边界、禁词、规则复述、跨段重复。"""

from __future__ import annotations

from src.llm.contracts import Flag, FlagCode, Metric, ReviewDraft, ReviewFacts
from src.llm.validate import (
    LIMITS,
    extract_numbers,
    validate_draft,
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
            Metric("grossprofit_margin", "毛利率", 31.84, "%"),
            Metric("roe", "ROE", 21.89, "%"),
            Metric("debt_to_assets", "资产负债率", 15.80, "%", highlightable=False),
        ),
        "flags": (Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def _draft(**overrides) -> ReviewDraft:
    values = {
        "highlight": "营收同比+20.3%，归母净利同比+177.6%，景气爆发",
        "risk": "周期资源行业，盈利随铝价波动",
        "comment": "周期资源现金牛，重点盯住产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewDraft(**values)


def _codes(violations, field: str | None = None) -> set[str]:
    return {v.code for v in violations if field is None or v.field == field}


# ===== 基线 =====
def test_clean_draft_has_no_violations() -> None:
    assert validate_draft(_draft(), _facts()) == []


def test_limits_follow_brd_spec() -> None:
    assert LIMITS["highlight"][1] == 30
    assert LIMITS["risk"][1] == 40
    assert LIMITS["comment"][1] == 50


# ===== 数字抽取 =====
def test_extract_numbers_parses_decimals_and_integers() -> None:
    assert extract_numbers("营收+20.3%，ROE 21.89%，负债率16%") == [20.3, 21.89, 16.0]


def test_extract_numbers_empty() -> None:
    assert extract_numbers("无数字") == []


# ===== 语言 =====
def test_latin_leak_is_violation_with_token_in_message() -> None:
    violations = validate_draft(
        _draft(risk="All indicators look strong，盈利随铝价波动"), _facts()
    )
    latin = [v for v in violations if v.code == "latin"]
    assert latin and latin[0].field == "risk"
    assert "All" in latin[0].message


def test_whitelisted_abbreviations_pass() -> None:
    draft = _draft(highlight="ROE 21.9%，营收同比+20.3%，A股铝业龙头")
    assert validate_draft(draft, _facts()) == []


# ===== 数字一致性 =====
def test_number_not_in_facts_is_violation() -> None:
    draft = _draft(highlight="营收同比+38%，归母净利同比+177.6%，景气爆发")
    violations = validate_draft(draft, _facts())
    assert _codes(violations, "highlight") == {"number_not_in_facts"}
    assert any("38" in v.message for v in violations)


def test_rounded_numbers_are_accepted() -> None:
    draft = _draft(highlight="营收同比+20%，归母净利同比+178%，景气爆发")
    assert validate_draft(draft, _facts()) == []


def test_derived_multiples_are_rejected() -> None:
    draft = _draft(highlight="归母净利同比增近3倍，营收同比+20.3%，景气爆发")
    assert _codes(validate_draft(draft, _facts()), "highlight") == {
        "number_not_in_facts"
    }


# ===== 长度边界 =====
def test_length_boundary_exact_limit_passes_and_plus_one_fails() -> None:
    limit = LIMITS["highlight"][1]
    exact = "亮" * (limit - 6) + "毛利率32%"
    over = "亮" * (limit - 5) + "毛利率32%"
    assert len(exact) == limit and len(over) == limit + 1
    assert "too_long" not in _codes(validate_draft(_draft(highlight=exact), _facts()))
    assert "too_long" in _codes(validate_draft(_draft(highlight=over), _facts()))


def test_too_short_and_empty_are_violations() -> None:
    empty = validate_draft(_draft(comment="  "), _facts())
    short = validate_draft(_draft(risk="风险"), _facts())
    assert "empty" in _codes(empty, "comment")
    assert "too_short" in _codes(short, "risk")


def test_length_counts_after_strip() -> None:
    limit = LIMITS["risk"][1]
    text = "  " + "险" * (limit - 3) + "波动" + "  "
    assert "too_long" not in _codes(validate_draft(_draft(risk=text), _facts()))


# ===== 禁词与元话语 =====
def test_forbidden_phrases_are_violations() -> None:
    draft = _draft(comment="综合来看该股值得关注，周期资源现金牛盯住价格周期")
    violations = validate_draft(draft, _facts())
    messages = [v.message for v in violations if v.code == "forbidden_phrase"]
    assert messages and "综合来看" in messages[0]


def test_meta_talk_is_forbidden() -> None:
    draft = _draft(risk="用户要求我指出风险，盈利随铝价波动")
    assert "forbidden_phrase" in _codes(validate_draft(draft, _facts()), "risk")


# ===== 规则结论复述 =====
def test_rule_echo_rating_advice_position() -> None:
    draft = _draft(
        highlight="皇冠明珠级现金牛，营收同比+20.3%，景气爆发",
        comment="建议重仓买入，目标仓位10-20%，盯住产品价格周期",
    )
    violations = validate_draft(draft, _facts())
    assert "rule_echo" in _codes(violations, "highlight")
    assert "rule_echo" in _codes(violations, "comment")


# ===== 跨段重复 =====
def test_repeated_number_across_fields_is_violation() -> None:
    draft = _draft(risk="归母净利同比+177.6%含周期高点，盈利随铝价波动")
    violations = validate_draft(draft, _facts())
    repeated = [v for v in violations if v.code == "repeated_number"]
    assert repeated and repeated[0].field == "risk"


def test_high_overlap_across_fields_is_violation() -> None:
    same = "周期资源现金牛，重点盯住产品价格周期与盈利弹性"
    draft = _draft(risk=same, comment=same)
    assert "overlap" in _codes(validate_draft(draft, _facts()))


def test_distinct_fields_have_no_overlap_violation() -> None:
    assert "overlap" not in _codes(validate_draft(_draft(), _facts()))
