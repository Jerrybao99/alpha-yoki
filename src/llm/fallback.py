"""规则模板兜底：LLM 完全失效时，直接由 ReviewFacts 拼出三段中文，天然满足白名单校验。"""

from __future__ import annotations

from src.llm.contracts import ReviewDraft, ReviewFacts
from src.llm.validate import LIMITS, extract_numbers

NO_RISK_SENTENCE = "当前财务指标未发现重大风险信号"
_SEPARATOR = "，"
_RISK_SEPARATOR = "；"
_HIGHLIGHT_METRICS = 2


def _join_within(pieces: list[str], separator: str, maximum: int, limit: int) -> str:
    """按顺序拼接片段，超出字数上限或条数上限即停止；至少保留首段。"""
    chosen: list[str] = []
    for piece in pieces:
        candidate = separator.join([*chosen, piece])
        if chosen and (len(candidate) > limit or len(chosen) >= maximum):
            break
        chosen.append(piece)
    return separator.join(chosen)


def _render_risk(facts: ReviewFacts) -> str:
    notes = [flag.note for flag in facts.flags if flag.note]
    if not notes:
        return NO_RISK_SENTENCE
    return _join_within(notes, _RISK_SEPARATOR, len(notes), LIMITS["risk"][1])


def _render_highlight(facts: ReviewFacts, used_numbers: set[float]) -> str:
    pieces: list[str] = []
    for metric in facts.metrics:
        if not metric.highlightable or (metric.signed and metric.value < 0):
            continue
        rendered = metric.render()
        if any(number in used_numbers for number in extract_numbers(rendered)):
            continue
        pieces.append(rendered)
    if not pieces:
        return f"综合分{facts.composite:.1f}分，{facts.company_type}属性标的"
    return _join_within(pieces, _SEPARATOR, _HIGHLIGHT_METRICS, LIMITS["highlight"][1])


def _render_comment(facts: ReviewFacts) -> str:
    return f"{facts.industry}{facts.company_type}，重点盯住{facts.watch_variable}"


def render_fallback(facts: ReviewFacts) -> ReviewDraft:
    """风险段先渲染，亮点段避开风险段已引用的数字，避免跨段重复。"""
    risk = _render_risk(facts)
    highlight = _render_highlight(facts, set(extract_numbers(risk)))
    return ReviewDraft(highlight=highlight, risk=risk, comment=_render_comment(facts))
