"""把评分行的数字与规则结论装配成 ReviewFacts：指标白名单、阈值派生风险标记、盯住变量。
纯函数，不调 LLM；模型只负责把这里给出的事实改写成中文。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.data.contract import StockFeatures
from src.llm.contracts import Flag, FlagCode, Metric, ReviewFacts
from src.reports.evaluation import (
    CAT_CYCLICAL,
    TYPE_HUCHENGHE,
    TYPE_QIANLIMA,
    TYPE_XIANJINNIU,
    AdviceResult,
    CompanyTypeResult,
)
from src.reports.reporting import clean_ts_code

LOW_BASE_NETPROFIT_YOY = 500.0
HIGH_LEVERAGE_DEBT_TO_ASSETS = 60.0
EXTREME_ROE = 50.0
WEAK_DIMENSION_SCORE = 7

CYCLICAL_WATCH_VARIABLE = "产品价格周期与盈利弹性"
WATCH_VARIABLES: dict[str, str] = {
    TYPE_QIANLIMA: "增速能否延续",
    TYPE_XIANJINNIU: "现金流与分红稳定性",
    TYPE_HUCHENGHE: "毛利率与品牌溢价能否维持",
}

_DIMENSION_LABELS: tuple[tuple[str, str], ...] = (
    ("growth", "成长性"),
    ("stability", "稳健性"),
    ("return_score", "资金回报"),
)

_PLAIN_LABEL = re.compile(r"[^\u4e00-\u9fff\w·/]")


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    divisor: float = 1.0
    signed: bool = False
    highlightable: bool = True


# 顺序即亮点优先级：景气度 > 盈利质量 > 股东回报；负债与流动性只用于风险段。
METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec("or_yoy", "营收同比", "%", signed=True),
    MetricSpec("netprofit_yoy", "归母净利同比", "%", signed=True),
    MetricSpec("grossprofit_margin", "毛利率", "%"),
    MetricSpec("roe", "ROE", "%"),
    MetricSpec("debt_to_assets", "资产负债率", "%", highlightable=False),
    MetricSpec("current_ratio", "流动比率", "倍", highlightable=False),
    MetricSpec("free_cashflow", "自由现金流", "亿元", divisor=1e8, signed=True),
    MetricSpec("eps", "每股收益", "元"),
)


def plain_label(text: str) -> str:
    """去掉评级 / 公司类型标签中的 emoji 与空格，只留可进 prompt 的文本。"""
    return _PLAIN_LABEL.sub("", text).strip()


def build_metrics(features: StockFeatures) -> tuple[Metric, ...]:
    metrics: list[Metric] = []
    for spec in METRIC_SPECS:
        raw = getattr(features, spec.key, None)
        if raw is None:
            continue
        metrics.append(
            Metric(
                key=spec.key,
                label=spec.label,
                value=float(raw) / spec.divisor,
                unit=spec.unit,
                signed=spec.signed,
                highlightable=spec.highlightable,
            )
        )
    return tuple(metrics)


def derive_flags(
    features: StockFeatures,
    *,
    growth: float | None,
    stability: float | None,
    return_score: float | None,
) -> tuple[Flag, ...]:
    """按阈值派生风险标记；阈值边界值本身不触发。"""
    flags: list[Flag] = []
    netprofit_yoy = features.netprofit_yoy
    if netprofit_yoy is not None and netprofit_yoy > LOW_BASE_NETPROFIT_YOY:
        flags.append(
            Flag(
                FlagCode.LOW_BASE,
                f"归母净利同比{netprofit_yoy:+.1f}%含低基数效应，不可线性外推",
            )
        )
    debt = features.debt_to_assets
    if debt is not None and debt > HIGH_LEVERAGE_DEBT_TO_ASSETS:
        flags.append(Flag(FlagCode.HIGH_LEVERAGE, f"资产负债率{debt:.1f}%偏高"))
    roe = features.roe
    if roe is not None and roe > EXTREME_ROE:
        flags.append(
            Flag(FlagCode.EXTREME_ROE, f"ROE {roe:.1f}%处于极端高位，持续性存疑")
        )
    scores = {"growth": growth, "stability": stability, "return_score": return_score}
    for key, label in _DIMENSION_LABELS:
        score = scores[key]
        if score is not None and score < WEAK_DIMENSION_SCORE:
            flags.append(
                Flag(FlagCode.WEAK_DIMENSION, f"{label}评分{int(score)}分为短板")
            )
    if (features.industry or "").strip() == CAT_CYCLICAL:
        flags.append(Flag(FlagCode.CYCLICAL, "周期资源行业，盈利随产品价格波动"))
    return tuple(flags)


def watch_variable_for(company_type_label: str, industry: str) -> str:
    """点评段应盯住的单一变量：周期行业看价格，其余按公司类型。"""
    if (industry or "").strip() == CAT_CYCLICAL:
        return CYCLICAL_WATCH_VARIABLE
    return WATCH_VARIABLES.get(company_type_label, WATCH_VARIABLES[TYPE_XIANJINNIU])


def _score(value: float | None) -> int | None:
    return None if value is None else int(value)


def build_review_facts(
    features: StockFeatures,
    *,
    growth: float | None,
    stability: float | None,
    return_score: float | None,
    composite: float,
    rating: str,
    company: CompanyTypeResult,
    advice: AdviceResult,
) -> ReviewFacts:
    industry = (features.industry or "").strip()
    return ReviewFacts(
        code=clean_ts_code(features.ts_code),
        name=features.name or "",
        industry=industry,
        company_type=plain_label(company.type_label),
        rating=plain_label(rating),
        advice=advice.advice,
        position=advice.position,
        composite=float(composite),
        growth=_score(growth),
        stability=_score(stability),
        return_score=_score(return_score),
        metrics=build_metrics(features),
        flags=derive_flags(
            features,
            growth=growth,
            stability=stability,
            return_score=return_score,
        ),
        watch_variable=watch_variable_for(company.type_label, industry),
    )
