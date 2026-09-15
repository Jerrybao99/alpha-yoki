"""锐评编排单测：成功 → 重试 → 换 Provider → 兜底 的状态机，以及缓存/追踪注入点。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from src.config import Settings
from src.llm.client import LLMResponse
from src.llm.contracts import (
    Flag,
    FlagCode,
    Metric,
    ReviewFacts,
    ReviewResult,
    ReviewStatus,
)
from src.llm.fallback import render_fallback
from src.llm.review import (
    ReviewOptions,
    build_fallback_client,
    describe_error,
    review,
)

GOOD = json.dumps(
    {
        "highlight": "营收同比+20.3%，ROE 21.9%，扩张与回报兼备",
        "risk": "周期资源行业，盈利随铝价波动",
        "comment": "周期资源现金牛，重点盯住产品价格周期与盈利弹性",
    },
    ensure_ascii=False,
)
ENGLISH = json.dumps(
    {
        "highlight": "Strong，营收同比+20.3%，ROE 21.9%",
        "risk": "周期资源行业，盈利随铝价波动",
        "comment": "周期资源现金牛，重点盯住产品价格周期与盈利弹性",
    },
    ensure_ascii=False,
)


class _FakeClient:
    """按脚本依次返回内容；元素为 Exception 时抛出。"""

    def __init__(self, provider: str, model: str, script: list) -> None:
        self.spec = SimpleNamespace(name=provider, model=model)
        self._script = list(script)
        self.calls: list[dict] = []

    def chat_completion(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        item = self._script.pop(0) if self._script else GOOD
        if isinstance(item, Exception):
            raise item
        return LLMResponse(
            content=item, model=self.spec.model, input_tokens=1, output_tokens=2
        )


class _MemoryCache:
    def __init__(self) -> None:
        self.store: dict[str, ReviewResult] = {}
        self.keys: list[str] = []

    def key(
        self, facts: ReviewFacts, prompt_version: str, provider: str, model: str
    ) -> str:
        key = f"{facts.code}|{prompt_version}|{provider}|{model}"
        self.keys.append(key)
        return key

    def get(self, key: str) -> ReviewResult | None:
        return self.store.get(key)

    def put(self, key: str, result: ReviewResult) -> None:
        self.store[key] = result


class _Tracer:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **fields) -> None:
        self.records.append(fields)


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
        ),
        "flags": (Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"),),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def test_success_on_first_attempt() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [GOOD])
    result = review(_facts(), primary)
    assert result.status is ReviewStatus.SUCCESS
    assert result.attempts == 1
    assert result.provider == "deepseek" and result.model == "deepseek-flash"
    assert result.highlight == "营收同比+20.3%，ROE 21.9%，扩张与回报兼备"
    assert result.violations == ()


def test_client_is_called_in_json_mode_without_reasoning() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [GOOD])
    review(_facts(), primary, options=ReviewOptions(max_tokens=333, temperature=0.1))
    call = primary.calls[0]
    assert call["json_mode"] is True
    assert call["reasoning"] is False
    assert call["max_tokens"] == 333
    assert call["temperature"] == 0.1
    assert "json" in call["system"].lower()


def test_retry_feeds_violations_back_into_prompt() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH, GOOD])
    result = review(_facts(), primary)
    assert result.status is ReviewStatus.RETRY
    assert result.attempts == 2
    assert "含英文" in primary.calls[1]["user"]
    assert "Strong，营收同比+20.3%" in primary.calls[1]["user"]


def test_switch_to_fallback_provider_after_primary_exhausted() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH, ENGLISH])
    fallback = _FakeClient("glm", "glm-5.3-flash", [GOOD])
    result = review(_facts(), primary, fallback_client=fallback)
    assert result.status is ReviewStatus.SWITCHED
    assert result.attempts == 3
    assert result.provider == "glm" and result.model == "glm-5.3-flash"
    assert len(primary.calls) == 2 and len(fallback.calls) == 1


def test_rule_fallback_when_every_attempt_fails() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH, ENGLISH])
    fallback = _FakeClient("glm", "glm-5.3-flash", [ENGLISH])
    facts = _facts()
    result = review(facts, primary, fallback_client=fallback)
    expected = render_fallback(facts)
    assert result.status is ReviewStatus.FALLBACK
    assert (result.highlight, result.risk, result.comment) == (
        expected.highlight,
        expected.risk,
        expected.comment,
    )
    assert result.attempts == 3
    assert {v.code for v in result.violations} == {"latin"}
    assert result.provider == "" and result.model == ""


def test_provider_errors_are_recorded_and_degrade_to_fallback() -> None:
    primary = _FakeClient(
        "deepseek", "deepseek-flash", [RuntimeError("boom"), RuntimeError("boom")]
    )
    tracer = _Tracer()
    result = review(_facts(), primary, tracer=tracer)
    assert result.status is ReviewStatus.FALLBACK
    assert [v.code for v in result.violations] == ["provider_error"]
    assert "RuntimeError" in result.violations[0].message
    assert [r["status"] for r in tracer.records] == ["rejected", "rejected", "fallback"]
    assert tracer.records[0]["details"] == ["all: RuntimeError: boom"]


def test_describe_error_redacts_key_fragments_and_keeps_status() -> None:
    class _AuthError(Exception):
        status_code = 401

    text = describe_error(
        _AuthError("Authentication Fails, Your api key: ****ecd7 is invalid")
    )
    assert text.startswith("_AuthError 401: ")
    assert "ecd7" not in text and "***" in text
    assert describe_error(RuntimeError("")) == "RuntimeError"
    assert "***" in describe_error(RuntimeError("sk-abcdefghijklmnopqrstuvwxyz0123"))


def test_bad_json_is_fed_back_then_accepted() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", ["不是 json", GOOD])
    result = review(_facts(), primary)
    assert result.status is ReviewStatus.RETRY
    assert "json" in primary.calls[1]["user"]


def test_zero_retries_goes_straight_to_fallback_provider() -> None:
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH])
    fallback = _FakeClient("glm", "glm-5.3-flash", [GOOD])
    result = review(
        _facts(),
        primary,
        fallback_client=fallback,
        options=ReviewOptions(max_retries=0),
    )
    assert result.status is ReviewStatus.SWITCHED
    assert len(primary.calls) == 1


def test_cache_hit_skips_llm_and_marks_status() -> None:
    cache = _MemoryCache()
    primary = _FakeClient("deepseek", "deepseek-flash", [GOOD])
    first = review(_facts(), primary, cache=cache)
    assert first.status is ReviewStatus.SUCCESS
    assert len(cache.store) == 1

    second = review(_facts(), primary, cache=cache)
    assert second.status is ReviewStatus.CACHE_HIT
    assert second.highlight == first.highlight
    assert len(primary.calls) == 1
    assert cache.keys[0].endswith("|deepseek|deepseek-flash")


def test_fallback_results_are_not_cached() -> None:
    cache = _MemoryCache()
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH, ENGLISH])
    result = review(_facts(), primary, cache=cache)
    assert result.status is ReviewStatus.FALLBACK
    assert cache.store == {}


def test_tracer_receives_one_record_per_attempt_plus_final() -> None:
    tracer = _Tracer()
    primary = _FakeClient("deepseek", "deepseek-flash", [ENGLISH, GOOD])
    review(_facts(), primary, tracer=tracer)
    statuses = [r["status"] for r in tracer.records]
    assert statuses == ["rejected", "retry"]
    assert tracer.records[0]["violations"] == ["latin"]
    assert tracer.records[0]["details"] == ["highlight: highlight 含英文：Strong"]
    assert tracer.records[0]["code"] == "000807"
    assert tracer.records[1]["output_tokens"] == 2
    assert tracer.records[1]["details"] == []


def test_review_options_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        review_max_retries=2,
        review_max_tokens=800,
        review_temperature=0.5,
    )
    options = ReviewOptions.from_settings(settings)
    assert (options.max_retries, options.max_tokens, options.temperature) == (
        2,
        800,
        0.5,
    )


class _NoKeyring:
    def get_password(self, service: str, username: str) -> None:
        return None


def test_build_fallback_client_skips_same_provider_and_missing_key() -> None:
    settings = Settings(_env_file=None, glm_api_key="", deepseek_api_key="k")
    backend = _NoKeyring()
    assert (
        build_fallback_client("glm", "glm", settings=settings, backend=backend) is None
    )
    assert (
        build_fallback_client("deepseek", "glm", settings=settings, backend=backend)
        is None
    )
    client = build_fallback_client(
        "glm", "deepseek", settings=settings, backend=backend
    )
    assert client is not None and client.spec.name == "deepseek"


def test_build_fallback_client_auto_picks_the_other_provider() -> None:
    settings = Settings(_env_file=None, glm_api_key="", deepseek_api_key="k")
    backend = _NoKeyring()
    auto = build_fallback_client("glm", "", settings=settings, backend=backend)
    assert auto is not None and auto.spec.name == "deepseek"
    assert (
        build_fallback_client("deepseek", "auto", settings=settings, backend=backend)
        is None
    )
