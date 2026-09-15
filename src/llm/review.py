"""锐评编排：缓存 → 生成 → 白名单校验 → 带反馈重试 → 跨 Provider 切换 → 规则兜底 → 追踪。
本模块是非确定性组件的唯一边界：进 ReviewFacts，出 ReviewResult，任何状态都有文案。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Protocol

from src.config import Settings
from src.llm.client import LLMClient
from src.llm.contracts import (
    ReviewDraft,
    ReviewFacts,
    ReviewResult,
    ReviewStatus,
    Violation,
)
from src.llm.credentials import (
    SUPPORTED_PROVIDERS,
    get_stored_api_key,
    normalize_provider,
)
from src.llm.fallback import render_fallback
from src.llm.prompt import DEFAULT_PROMPT, PromptSpec
from src.llm.validate import validate_draft

ATTEMPT_REJECTED = "rejected"
AUTO_FALLBACK = "auto"
_DETAIL_CHARS = 160
# 提供方报错正文可能带密钥尾号（如 ****ecd7）或长 token，落 trace 前统一脱敏。
_SECRET_LIKE = re.compile(r"\*{2,}\w+|[A-Za-z0-9_-]{20,}")


def describe_error(exc: BaseException) -> str:
    """异常类名 + HTTP 状态码 + 脱敏后的正文，供违规反馈与 trace 使用。"""
    status = getattr(exc, "status_code", None)
    head = f"{type(exc).__name__}" + (f" {status}" if status else "")
    body = _SECRET_LIKE.sub("***", str(exc)).strip()
    return f"{head}: {body[:_DETAIL_CHARS]}" if body else head


class ReviewCache(Protocol):
    def key(
        self, facts: ReviewFacts, prompt_version: str, provider: str, model: str
    ) -> str: ...

    def get(self, key: str) -> ReviewResult | None: ...

    def put(self, key: str, result: ReviewResult) -> None: ...


class ReviewTracer(Protocol):
    def record(self, **fields: Any) -> None: ...


class ChatClient(Protocol):
    spec: Any

    def chat_completion(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ReviewOptions:
    max_retries: int = 1
    max_tokens: int = 600
    temperature: float = 0.3

    @classmethod
    def from_settings(cls, settings: Settings) -> ReviewOptions:
        return cls(
            max_retries=int(settings.review_max_retries),
            max_tokens=int(settings.review_max_tokens),
            temperature=float(settings.review_temperature),
        )


def _identity(client: ChatClient) -> tuple[str, str]:
    spec = getattr(client, "spec", None)
    return str(getattr(spec, "name", "") or ""), str(getattr(spec, "model", "") or "")


def _trace(tracer: ReviewTracer | None, **fields: Any) -> None:
    if tracer is not None:
        tracer.record(**fields)


def _violation_fields(violations: list[Violation]) -> dict[str, list[str]]:
    """trace 里同时落违规码与截断后的中文说明，便于事后按段落/原因聚合。"""
    return {
        "violations": [violation.code for violation in violations],
        "details": [
            f"{violation.field}: {violation.message[:_DETAIL_CHARS]}"
            for violation in violations
        ],
    }


def resolve_fallback_provider(primary: str, configured: str) -> str | None:
    """auto/空 → 另一家 Provider；显式指定同主 Provider → 不切换。"""
    primary_name = normalize_provider(primary)
    wanted = (configured or "").strip().lower()
    if wanted in ("", AUTO_FALLBACK):
        others = [name for name in SUPPORTED_PROVIDERS if name != primary_name]
        return others[0] if others else None
    fallback = normalize_provider(wanted)
    return None if fallback == primary_name else fallback


def build_fallback_client(
    primary_provider: str,
    configured_fallback: str,
    *,
    settings: Settings,
    backend: Any | None = None,
) -> LLMClient | None:
    """按配置构造备用 Provider 客户端；无密钥或与主 Provider 相同时返回 None，不触发交互。"""
    fallback = resolve_fallback_provider(primary_provider, configured_fallback)
    if fallback is None:
        return None
    api_key = get_stored_api_key(fallback, settings=settings, backend=backend)
    if not api_key:
        return None
    return LLMClient(provider=fallback, api_key=api_key, settings=settings)


def _attempt_chain(
    primary: ChatClient, fallback_client: ChatClient | None, options: ReviewOptions
) -> list[tuple[ChatClient, bool]]:
    chain: list[tuple[ChatClient, bool]] = [(primary, False)] * (
        1 + max(options.max_retries, 0)
    )
    if fallback_client is not None:
        chain.append((fallback_client, True))
    return chain


def _to_result(
    draft: ReviewDraft, status: ReviewStatus, provider: str, model: str, attempts: int
) -> ReviewResult:
    return ReviewResult(
        highlight=draft.highlight,
        risk=draft.risk,
        comment=draft.comment,
        status=status,
        provider=provider,
        model=model,
        attempts=attempts,
    )


def review(
    facts: ReviewFacts,
    primary: ChatClient,
    *,
    fallback_client: ChatClient | None = None,
    options: ReviewOptions = ReviewOptions(),
    prompt: PromptSpec = DEFAULT_PROMPT,
    cache: ReviewCache | None = None,
    tracer: ReviewTracer | None = None,
) -> ReviewResult:
    """对单只股票生成并校验三段锐评；永不抛出 Provider 异常，失败以 status 表达。"""
    provider, model = _identity(primary)
    cache_key = cache.key(facts, prompt.version, provider, model) if cache else ""
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            _trace(
                tracer,
                code=facts.code,
                provider=cached.provider,
                model=cached.model,
                attempt=0,
                status=ReviewStatus.CACHE_HIT.value,
                input_tokens=0,
                output_tokens=0,
                **_violation_fields([]),
            )
            return replace(cached, status=ReviewStatus.CACHE_HIT, attempts=0)

    feedback: list[Violation] = []
    previous: ReviewDraft | None = None
    chain = _attempt_chain(primary, fallback_client, options)

    for attempt, (client, switched) in enumerate(chain, start=1):
        attempt_provider, attempt_model = _identity(client)
        input_tokens = output_tokens = 0
        try:
            response = client.chat_completion(
                system=prompt.system,
                user=prompt.render(facts, feedback, previous),
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                reasoning=False,
                json_mode=True,
            )
        except Exception as exc:  # Provider 层任何失败都降级，不中断整批报告
            feedback = [Violation("provider_error", "all", describe_error(exc))]
            previous = None
        else:
            input_tokens, output_tokens = response.input_tokens, response.output_tokens
            draft = prompt.parse(response.content)
            if draft is None:
                feedback = [Violation("bad_json", "all", "输出不是合法 json 对象")]
                previous = None
            else:
                feedback = validate_draft(draft, facts)
                previous = draft

        status: ReviewStatus | None = None
        if previous is not None and not feedback:
            if switched:
                status = ReviewStatus.SWITCHED
            else:
                status = ReviewStatus.SUCCESS if attempt == 1 else ReviewStatus.RETRY
        _trace(
            tracer,
            code=facts.code,
            provider=attempt_provider,
            model=attempt_model,
            attempt=attempt,
            status=status.value if status is not None else ATTEMPT_REJECTED,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            **_violation_fields(feedback),
        )
        if status is not None and previous is not None:
            result = _to_result(
                previous, status, attempt_provider, attempt_model, attempt
            )
            if cache is not None:
                cache.put(cache_key, result)
            return result

    fallback = render_fallback(facts)
    result = ReviewResult(
        highlight=fallback.highlight,
        risk=fallback.risk,
        comment=fallback.comment,
        status=ReviewStatus.FALLBACK,
        attempts=len(chain),
        violations=tuple(feedback),
    )
    _trace(
        tracer,
        code=facts.code,
        provider="",
        model="",
        attempt=len(chain),
        status=ReviewStatus.FALLBACK.value,
        input_tokens=0,
        output_tokens=0,
        **_violation_fields(feedback),
    )
    return result
