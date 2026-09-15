"""锐评 Prompt 单测：事实渲染、反馈段、JSON 解析容错、字数目标与校验上限一致。"""

from __future__ import annotations

from src.llm.contracts import (
    Flag,
    FlagCode,
    Metric,
    ReviewDraft,
    ReviewFacts,
    Violation,
)
from src.llm.prompt import (
    DEFAULT_PROMPT,
    PROMPT_VERSION,
    TARGET_CHARS,
    PromptSpec,
    parse_draft,
)
from src.llm.validate import LIMITS


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
            Metric("roe", "ROE", 21.89, "%"),
            Metric("free_cashflow", "自由现金流", 12.34, "亿元", signed=True),
        ),
        "flags": (Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def test_system_prompt_mentions_json_and_hard_rules() -> None:
    system = DEFAULT_PROMPT.system
    assert "json" in system.lower()
    for keyword in ("可用数字", "评级", "仓位", "综合来看"):
        assert keyword in system


def test_user_prompt_renders_facts_with_one_decimal() -> None:
    """一位小数：省字数，且与校验器接受的取整一致。"""
    user = DEFAULT_PROMPT.render(_facts())
    assert "云铝股份（000807）" in user
    assert "周期资源" in user and "现金牛" in user
    assert "营收同比+20.3%" in user
    assert "ROE 21.9%" in user
    assert "自由现金流+12.3亿元" in user
    assert "20.30" not in user
    assert "周期资源行业，盈利随产品价格波动" in user
    assert "产品价格周期与盈利弹性" in user


def test_system_prompt_demands_single_sentence_risk_and_comment() -> None:
    system = DEFAULT_PROMPT.system
    assert "一位小数" in system
    assert "合并成一句" in system
    assert "重点盯住" in system


def test_user_prompt_never_leaks_rule_verdicts() -> None:
    user = DEFAULT_PROMPT.render(_facts())
    for verdict in ("皇冠明珠", "重仓买入", "10-20%"):
        assert verdict not in user


def test_user_prompt_without_flags_says_none() -> None:
    user = DEFAULT_PROMPT.render(_facts(flags=()))
    assert "【风险提示】无" in user


def test_user_prompt_feedback_section_lists_violations_and_previous_draft() -> None:
    previous = ReviewDraft(highlight="AMC 业务", risk="风险", comment="点评")
    feedback = [Violation("latin", "highlight", "highlight 含英文：AMC")]
    user = DEFAULT_PROMPT.render(_facts(), feedback, previous)
    assert "上一次输出" in user
    assert "highlight 含英文：AMC" in user
    assert '"highlight": "AMC 业务"' in user
    assert user.rstrip().endswith("json：")


def test_prompt_spec_version_is_stable_identifier() -> None:
    assert PROMPT_VERSION and DEFAULT_PROMPT.version == PROMPT_VERSION
    custom = PromptSpec(version="review-test", system="只输出 json")
    assert custom.version == "review-test"
    assert "只输出 json" == custom.system


def test_target_chars_sit_inside_validation_limits_with_margin() -> None:
    """目标上限至少比校验上限低 6 字：模型计数偏差常在 3-5 字。"""
    for field, (low, high) in TARGET_CHARS.items():
        minimum, maximum = LIMITS[field]
        assert minimum <= low < high <= maximum - 6
        assert f"{low}-{high}" in DEFAULT_PROMPT.system


# ===== parse_draft =====
def test_parse_plain_json() -> None:
    draft = parse_draft('{"highlight": "亮", "risk": "险", "comment": "评"}')
    assert draft == ReviewDraft(highlight="亮", risk="险", comment="评")


def test_parse_fenced_json_with_surrounding_text() -> None:
    text = (
        '好的：\n```json\n{"highlight": "亮", "risk": "险", "comment": "评"}\n```\n完毕'
    )
    assert parse_draft(text) == ReviewDraft(highlight="亮", risk="险", comment="评")


def test_parse_missing_keys_become_empty_strings() -> None:
    assert parse_draft('{"highlight": "亮"}') == ReviewDraft(
        highlight="亮", risk="", comment=""
    )


def test_parse_non_string_values_are_stringified_and_stripped() -> None:
    draft = parse_draft('{"highlight": "  亮 ", "risk": 12, "comment": null}')
    assert draft == ReviewDraft(highlight="亮", risk="12", comment="")


def test_parse_invalid_or_non_object_returns_none() -> None:
    assert parse_draft("") is None
    assert parse_draft("不是 json") is None
    assert parse_draft('["a", "b"]') is None
    assert parse_draft('{"highlight": "未闭合"') is None
