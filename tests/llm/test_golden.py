"""黄金样本回归：20 只真实 Top20 股票的事实 + 人工认可的三段文案。
锁定的是"什么是合格输出"——校验器改动若误杀合格样本、或兜底模板不再自洽，这里先红。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.llm.contracts import Flag, FlagCode, Metric, ReviewDraft, ReviewFacts
from src.llm.fallback import render_fallback
from src.llm.prompt import DEFAULT_PROMPT, parse_draft
from src.llm.validate import validate_draft

_SAMPLES_PATH = Path(__file__).parent / "golden" / "samples.json"
_SAMPLES: list[dict] = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
_IDS = [f"{s['facts']['code']}-{s['facts']['name']}" for s in _SAMPLES]


def _facts_from_dict(payload: dict) -> ReviewFacts:
    return ReviewFacts(
        code=payload["code"],
        name=payload["name"],
        industry=payload["industry"],
        company_type=payload["company_type"],
        rating=payload["rating"],
        advice=payload["advice"],
        position=payload["position"],
        composite=payload["composite"],
        growth=payload["growth"],
        stability=payload["stability"],
        return_score=payload["return_score"],
        metrics=tuple(Metric(**metric) for metric in payload["metrics"]),
        flags=tuple(Flag(FlagCode(flag["code"]), flag["note"]) for flag in payload["flags"]),
        watch_variable=payload["watch_variable"],
    )


def test_golden_set_has_twenty_distinct_stocks() -> None:
    assert len(_SAMPLES) == 20
    assert len({s["facts"]["code"] for s in _SAMPLES}) == 20


@pytest.mark.parametrize("sample", _SAMPLES, ids=_IDS)
def test_golden_draft_passes_whitelist(sample: dict) -> None:
    facts = _facts_from_dict(sample["facts"])
    draft = ReviewDraft(**sample["draft"])
    assert validate_draft(draft, facts) == []


@pytest.mark.parametrize("sample", _SAMPLES, ids=_IDS)
def test_golden_fallback_passes_whitelist(sample: dict) -> None:
    facts = _facts_from_dict(sample["facts"])
    assert validate_draft(render_fallback(facts), facts) == []


@pytest.mark.parametrize("sample", _SAMPLES, ids=_IDS)
def test_golden_draft_round_trips_through_json_parser(sample: dict) -> None:
    draft = ReviewDraft(**sample["draft"])
    encoded = json.dumps(sample["draft"], ensure_ascii=False)
    assert parse_draft(f"```json\n{encoded}\n```") == draft


@pytest.mark.parametrize("sample", _SAMPLES, ids=_IDS)
def test_golden_prompt_only_exposes_facts(sample: dict) -> None:
    facts = _facts_from_dict(sample["facts"])
    user = DEFAULT_PROMPT.render(facts)
    assert facts.name in user and facts.code in user
    for verdict in (facts.rating, facts.advice, facts.position):
        assert verdict not in user
