"""锐评子系统契约：规则层交给模型的事实、模型草稿、校验违规与最终结果。
本模块只有类型，不依赖 src.reports，保证依赖方向 reports → llm 单向。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

REVIEW_FIELDS: tuple[str, ...] = ("highlight", "risk", "comment")

_ROUNDINGS: tuple[int, ...] = (0, 1, 2)


class FlagCode(StrEnum):
    LOW_BASE = "low_base"
    HIGH_LEVERAGE = "high_leverage"
    EXTREME_ROE = "extreme_roe"
    WEAK_DIMENSION = "weak_dimension"
    CYCLICAL = "cyclical"


class ReviewStatus(StrEnum):
    SUCCESS = "success"
    RETRY = "retry"
    SWITCHED = "switched"
    FALLBACK = "fallback"
    CACHE_HIT = "cache_hit"


@dataclass(frozen=True)
class Flag:
    """规则派生的风险标记；note 为可直接进 prompt / 兜底文案的中文一句话。"""

    code: FlagCode
    note: str


@dataclass(frozen=True)
class Metric:
    """白名单指标。value 已按展示单位缩放（如自由现金流以亿元计）。"""

    key: str
    label: str
    value: float
    unit: str = ""
    signed: bool = False
    highlightable: bool = True

    def render(self, digits: int = 1) -> str:
        number = (
            f"{self.value:+.{digits}f}" if self.signed else f"{self.value:.{digits}f}"
        )
        separator = " " if self.label and self.label[-1].isascii() else ""
        return f"{self.label}{separator}{number}{self.unit}"


@dataclass(frozen=True)
class ReviewFacts:
    """模型唯一可见的事实集合：数字来自数据，判断来自规则。"""

    code: str
    name: str
    industry: str
    company_type: str
    rating: str
    advice: str
    position: str
    composite: float
    growth: int | None
    stability: int | None
    return_score: int | None
    metrics: tuple[Metric, ...] = ()
    flags: tuple[Flag, ...] = ()
    watch_variable: str = ""

    def allowed_numbers(self) -> frozenset[float]:
        """输出中允许出现的数字：指标与评分在 0/1/2 位小数下的取整值（取绝对值）。"""
        values: list[float] = [metric.value for metric in self.metrics]
        values.append(self.composite)
        values.extend(
            float(score)
            for score in (self.growth, self.stability, self.return_score)
            if score is not None
        )
        allowed = {
            float(f"{abs(value):.{digits}f}")
            for value in values
            for digits in _ROUNDINGS
        }
        if self.code.isdigit():
            allowed.add(float(self.code))
        return frozenset(allowed)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewDraft:
    """模型返回的原始三段文案，尚未校验。"""

    highlight: str
    risk: str
    comment: str

    def get(self, field: str) -> str:
        return str(getattr(self, field))


@dataclass(frozen=True)
class Violation:
    """一条白名单校验违规；message 为中文说明，可原样反馈给模型重试。"""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class ReviewResult:
    highlight: str
    risk: str
    comment: str
    status: ReviewStatus
    provider: str = ""
    model: str = ""
    attempts: int = 0
    violations: tuple[Violation, ...] = ()
