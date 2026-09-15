"""锐评白名单校验：语言、数字一致性、长度、禁词、规则复述、跨段重复。
只描述"什么是合格输出"，不做黑名单清洗；违规原样反馈给模型重试或触发兜底。
"""

from __future__ import annotations

import re

from src.llm.contracts import REVIEW_FIELDS, ReviewDraft, ReviewFacts, Violation

# (最短, 最长) 字数；上限对齐 docs/brd.md：核心亮点 30 字、点评 50 字。
LIMITS: dict[str, tuple[int, int]] = {
    "highlight": (8, 30),
    "risk": (6, 40),
    "comment": (8, 50),
}

LATIN_WHITELIST: frozenset[str] = frozenset({"ROE", "EPS", "AI", "A", "PE", "PB"})

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "综合来看",
    "值得关注",
    "总体而言",
    "俱佳",
    "看起来",
    "似乎",
    "用户",
    "指令",
    "输出",
    "我需要",
    "instructions",
)

OVERLAP_THRESHOLD = 0.2
_NGRAM = 4

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_LATIN = re.compile(r"[A-Za-z]+")
_NOISE = re.compile(r"[\s，。；、：！？（）()%+\-.,;:!?\"'“”‘’]")


def extract_numbers(text: str) -> list[float]:
    return [float(token) for token in _NUMBER.findall(text)]


def _ngrams(text: str) -> set[str]:
    cleaned = _NOISE.sub("", text)
    if len(cleaned) < _NGRAM:
        return set()
    return {cleaned[i : i + _NGRAM] for i in range(len(cleaned) - _NGRAM + 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _validate_field(
    field: str, text: str, facts: ReviewFacts, allowed: frozenset[float]
) -> list[Violation]:
    violations: list[Violation] = []
    minimum, maximum = LIMITS[field]
    if not text:
        return [Violation("empty", field, f"{field} 为空")]
    if len(text) < minimum:
        violations.append(
            Violation(
                "too_short", field, f"{field} 仅 {len(text)} 字，少于 {minimum} 字"
            )
        )
    if len(text) > maximum:
        violations.append(
            Violation(
                "too_long", field, f"{field} 共 {len(text)} 字，超过 {maximum} 字上限"
            )
        )

    latin = [
        token for token in _LATIN.findall(text) if token.upper() not in LATIN_WHITELIST
    ]
    if latin:
        violations.append(
            Violation("latin", field, f"{field} 含英文：{'、'.join(latin)}")
        )

    strangers = [
        token for token in _NUMBER.findall(text) if float(token) not in allowed
    ]
    if strangers:
        violations.append(
            Violation(
                "number_not_in_facts",
                field,
                f"{field} 出现数据中不存在的数字：{'、'.join(strangers)}",
            )
        )

    hits = [phrase for phrase in FORBIDDEN_PHRASES if phrase in text]
    if hits:
        violations.append(
            Violation("forbidden_phrase", field, f"{field} 含禁用词：{'、'.join(hits)}")
        )

    echoes = [
        verdict
        for verdict in (facts.rating, facts.advice, facts.position)
        if verdict and verdict in text
    ]
    if echoes:
        violations.append(
            Violation(
                "rule_echo",
                field,
                f"{field} 复述了评级/操作建议/仓位：{'、'.join(echoes)}",
            )
        )
    return violations


def validate_draft(draft: ReviewDraft, facts: ReviewFacts) -> list[Violation]:
    """返回全部违规；空列表即合格。"""
    allowed = facts.allowed_numbers()
    texts = {field: draft.get(field).strip() for field in REVIEW_FIELDS}
    violations: list[Violation] = []
    for field in REVIEW_FIELDS:
        violations.extend(_validate_field(field, texts[field], facts, allowed))

    seen_numbers: dict[float, str] = {}
    seen_ngrams: dict[str, set[str]] = {}
    for field in REVIEW_FIELDS:
        text = texts[field]
        if not text:
            continue
        repeated = sorted(
            {number for number in extract_numbers(text) if number in seen_numbers}
        )
        if repeated:
            violations.append(
                Violation(
                    "repeated_number",
                    field,
                    f"{field} 重复引用了其他段落已用的数字：{'、'.join(f'{n:g}' for n in repeated)}",
                )
            )
        for number in extract_numbers(text):
            seen_numbers.setdefault(number, field)

        grams = _ngrams(text)
        for other, other_grams in seen_ngrams.items():
            if _jaccard(grams, other_grams) >= OVERLAP_THRESHOLD:
                violations.append(
                    Violation("overlap", field, f"{field} 与 {other} 内容大量重复")
                )
        seen_ngrams[field] = grams
    return violations
