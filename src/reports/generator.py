"""荐股报告编排：评分 CSV → 规则结论 → ReviewFacts → review() → 13 列。Provider 无关。
数字与评级由规则层给定，模型只改写文字；任何 Provider 状态下三列锐评都不为空。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.data.contract import StockFeatures
from src.llm.cache import FileReviewCache
from src.llm.client import LLMClient
from src.llm.contracts import ReviewFacts, ReviewResult
from src.llm.review import (
    ChatClient,
    ReviewCache,
    ReviewOptions,
    ReviewTracer,
    review,
)
from src.llm.trace import JsonlReviewTracer
from src.reports.evaluation import classify_company_type, get_advice
from src.reports.facts import build_review_facts
from src.reports.reporting import (
    TOP_N,
    Top20Result,
    clean_ts_code,
    load_score_rows_prefer_raw,
    make_features,
)

_MAX_WORKERS = 6
_REVIEW_COLUMNS: dict[str, str] = {
    "highlight": "核心亮点",
    "risk": "风险提示",
    "comment": "点评",
}


@dataclass(frozen=True)
class Candidate:
    parsed: dict[str, Any]
    features: StockFeatures
    composite: float


def select_top(csv_path: Path, limit: int = TOP_N) -> list[Candidate]:
    """读取评分产物（raw 优先），按综合分降序取前 limit 只可构造特征的股票。"""
    candidates: list[Candidate] = []
    for parsed in load_score_rows_prefer_raw(csv_path):
        composite = parsed.get("综合分")
        if composite is None:
            continue
        try:
            features = make_features(parsed)
        except Exception:
            continue
        candidates.append(Candidate(parsed, features, float(composite)))
    candidates.sort(key=lambda item: item.composite, reverse=True)
    return candidates[:limit]


def _score_text(value: Any) -> str:
    return str(int(value)) if value else ""


def _prepare(candidate: Candidate) -> tuple[dict[str, str], ReviewFacts]:
    parsed = candidate.parsed
    growth = parsed.get("成长性")
    stability = parsed.get("稳健性")
    return_score = parsed.get("资金回报")
    rating = str(parsed.get("评级") or "")
    company = classify_company_type(candidate.features)
    advice = get_advice(rating)
    facts = build_review_facts(
        candidate.features,
        growth=growth,
        stability=stability,
        return_score=return_score,
        composite=candidate.composite,
        rating=rating,
        company=company,
        advice=advice,
    )
    row = {
        "股票代码": clean_ts_code(str(parsed.get("ts_code", ""))),
        "股票名称": str(parsed.get("name", "")),
        "公司类型": company.type_label,
        "行业分类": str(parsed.get("industry", "")),
        "核心亮点": "",
        "成长性": _score_text(growth),
        "稳健性": _score_text(stability),
        "回报性": _score_text(return_score),
        "综合分": str(candidate.composite),
        "评级": rating,
        "操作建议": f"{advice.advice}（{advice.position}）",
        "风险提示": "",
        "点评": "",
    }
    return row, facts


def _print_progress(result: Top20Result) -> None:
    total = len(result.rows)
    for index, (row, status) in enumerate(zip(result.rows, result.statuses), start=1):
        print(f"  [{index:>2}/{total}] {row['股票名称']} | {status:<9} | {row['核心亮点']}")
    summary = " ".join(f"{status}={result.statuses.count(status)}" for status in dict.fromkeys(result.statuses))
    if summary:
        print(f"锐评状态：{summary}")


def build_top20(
    csv_path: Path,
    client: ChatClient | None = None,
    *,
    fallback_client: ChatClient | None = None,
    settings: Settings | None = None,
    cache: ReviewCache | None = None,
    tracer: ReviewTracer | None = None,
) -> Top20Result:
    """读取评分 CSV，选取综合分 TopN，经锐评子系统生成三列文案。"""
    resolved_settings = settings or get_settings()
    primary: ChatClient = client or LLMClient(settings=resolved_settings)
    options = ReviewOptions.from_settings(resolved_settings)
    if cache is None and resolved_settings.review_cache_enabled:
        cache = FileReviewCache(resolved_settings.data_path("cache") / "review")
    if tracer is None:
        tracer = JsonlReviewTracer(resolved_settings.data_path("monitor"))

    result = Top20Result()
    facts_list: list[ReviewFacts] = []
    for candidate in select_top(csv_path):
        row, facts = _prepare(candidate)
        result.rows.append(row)
        facts_list.append(facts)

    def _review(facts: ReviewFacts) -> ReviewResult:
        return review(
            facts,
            primary,
            fallback_client=fallback_client,
            options=options,
            cache=cache,
            tracer=tracer,
        )

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        outcomes = list(executor.map(_review, facts_list))

    for row, outcome in zip(result.rows, outcomes):
        for field, column in _REVIEW_COLUMNS.items():
            row[column] = getattr(outcome, field)
        result.statuses.append(outcome.status.value)

    _print_progress(result)
    return result
