"""荐股报告纯逻辑：常量、CSV 解析、上下文构建、LLM 输出清洗、CSV 写盘。不触网络/I/O。
LLM 调用与编排由 scripts/full_report.py 负责。
"""

from __future__ import annotations

import csv
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.full_scores import (
    _CN_TO_FIELD,
    _parse_value,
)
from src.data.contract import StockFeatures
from src.data.output import FIELD_UNIT

SCORING_KEYS = ("成长性", "稳健性", "资金回报", "综合分", "评级")

_LLM_FIELDS: dict[str, str] = {
    "成长分": "成长性评分",
    "稳健分": "稳健性评分",
    "回报分": "资金回报评分",
    "综合分": "综合评分",
    "评级": "综合评级",
    "or_yoy": "营业收入同比增长率",
    "netprofit_yoy": "归母净利润同比增长率",
    "grossprofit_margin": "销售毛利率",
    "debt_to_assets": "资产负债率",
    "current_ratio": "流动比率",
    "roe": "净资产收益率",
    "free_cashflow": "企业自由现金流",
    "eps": "基本每股收益",
}

_LLM_UNITS: dict[str, str] = {
    "成长分": "1-10",
    "稳健分": "1-10",
    "回报分": "1-10",
    "综合分": "0-10",
    "评级": "",
    **{
        f: FIELD_UNIT.get(f, "")
        for f in _LLM_FIELDS
        if f not in ("成长分", "稳健分", "回报分", "综合分", "评级")
    },
}

OUTPUT_HEADERS_CN = [
    "股票代码",
    "股票名称",
    "公司类型",
    "行业分类",
    "核心亮点",
    "成长性",
    "稳健性",
    "回报性",
    "综合分",
    "评级",
    "操作建议",
    "风险提示",
    "点评",
]


@dataclass
class Top20Result:
    rows: list[dict[str, str]] = field(default_factory=list)


def load_scoring_rows(csv_path: Path) -> list[dict[str, Any]]:
    """读取评分 CSV，返回中文列头 key + 原始值的行列表。"""
    content = csv_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    reader = csv.DictReader(content.splitlines())
    return [dict(row) for row in reader]


def parse_back(raw_row: dict[str, Any]) -> dict[str, Any]:
    """将中文列头评分行反转回英文字段名 + float 值。"""
    result: dict[str, Any] = {}
    for cn_key, value in raw_row.items():
        en = _CN_TO_FIELD.get(cn_key, cn_key)
        result[en] = _parse_value(str(value), en)
    return result


def make_features(parsed: dict[str, Any]) -> StockFeatures:
    """从解析后的字段构建 StockFeatures。"""
    kwargs: dict[str, Any] = {}
    for en_key in StockFeatures.model_fields:
        if en_key in parsed:
            kwargs[en_key] = parsed[en_key]
    if "ts_code" not in kwargs:
        kwargs["ts_code"] = parsed.get("symbol", "")
    return StockFeatures(**kwargs)


def build_llm_context(
    parsed: dict[str, Any],
    growth: float | None,
    stability: float | None,
    return_score: float | None,
    composite: float | None,
    rating: str | None,
    company_type: str | None,
    *,
    field_set: frozenset[str] | None = None,
) -> str:
    """构建传给 LLM 的上下文文本。field_set 非空时只拼指定字段。"""
    parts: list[str] = [
        f"股票代码: {parsed.get('ts_code', '')}",
        f"股票名称: {parsed.get('name', '')}",
        f"行业分类: {parsed.get('industry', '')}",
        f"公司类型: {company_type or '未知'}",
        "",
        "=== 评分 ===",
        f"成长性评分: {growth or '-'} / 10",
        f"稳健性评分: {stability or '-'} / 10",
        f"资金回报评分: {return_score or '-'} / 10",
        f"综合分: {composite or '-'} / 10",
        f"评级: {rating or '-'}",
        "",
        "=== 关键财务指标 ===",
    ]

    for en_key, cn_name in _LLM_FIELDS.items():
        if en_key in SCORING_KEYS:
            continue
        if field_set and en_key not in field_set:
            continue
        v = parsed.get(en_key)
        if v is not None and not (isinstance(v, float) and v != v):
            unit = _LLM_UNITS.get(en_key, "")
            suffix = f"（{unit}）" if unit else ""
            if isinstance(v, float):
                parts.append(f"{cn_name}{suffix}: {v:.2f}")
            else:
                parts.append(f"{cn_name}{suffix}: {v}")

    return "\n".join(parts)


# 各问题类型裁剪的字段子集
_HL_FIELDS: frozenset[str] = frozenset(
    {"or_yoy", "netprofit_yoy", "grossprofit_margin", "roe", "free_cashflow", "eps"}
)
_RISK_FIELDS: frozenset[str] = frozenset(
    {
        "debt_to_assets",
        "current_ratio",
        "netprofit_yoy",
        "or_yoy",
        "grossprofit_margin",
        "roe",
        "free_cashflow",
    }
)
_CMT_FIELDS: frozenset[str] = frozenset(
    {
        "roe",
        "debt_to_assets",
        "netprofit_yoy",
        "or_yoy",
        "free_cashflow",
        "grossprofit_margin",
        "current_ratio",
    }
)


_RE_NOISE = _re.compile(
    r"^(?:我们|我|需要|首先|基于|根据|分析|注意|要求|任务|给出|输出|最终|直接|请"
    r"|作为.{0,12}|数据.{0,12}|关键.{0,12}|代码.{0,12}"
    r"|要求用一句话|被要求|要点[:：]?|可以用|一句总结|核心亮点需基于"
    r"|一句话提炼|所以|可以概括|评分[:：]|综合评分\d|股票是|提炼核心[:：]"
    r"|用一句话|股票.{0,6}[:：]|亮点\s*$"
    r"|规则.{0,15}|那么可能|那么风险|这些指标.{0,6}看"
    r"|没有提供.{0,12}数据|应优先关注|用户给出了"
    r"|这里的?\s*(?:稳健|成长|回报|评分)"
    r"|结合(?:公司类型|评分维度)"
    r"|排查|针对.{0,8}(?:的?稳健|的?成长|的?回报|的?评分|数据)"
    r"|但根据|但规则|但这些|但.{0,4}(?:评分|风险|可能|需要)"
    r"|可能.{0,6}(?:风险|隐含|暗)"
    r"|那就说|那就|只能根据|只能|否则|牵强|比较牵强|没法"
    r"|或许|可能性|有没有可能|怎么说|那就是|也是可以"
    r"|观察.{0,4}数据|结合现有指标|不知道.{0,4}评分"
    r"|财务数据中|我们可以提|可以提.{0,6}数据"
    r"|看起来.{0,6}(?:这些|指标|非常|很好|不错)"
    r"|但可能|但要注意|但需注意|似乎"
    r")[，,。.]?"
)

_RE_ECHO = _re.compile(
    r"(?:用一句话[（(]?\d*字[内以]?[)）]?"
    r"(?:总结|指出|给出|描述|说明)"
    r"(?:这只股票的)?"
    r"(?:核心亮点|主要风险|投资建议)?"
    r"[:：]?\s*)"
)

_SENTENCE_SPLIT = _re.compile(r"[。！;\n]+")

_RE_HAS_CONTENT = _re.compile(
    r"(?:增长|营收|净利|业绩|ROE|财务|负债|毛利|盈利|估值|配置|持有|买入|建议|关注|布局|适合|风险|警惕|担忧|需|可"
    r"|利润|收入|收益|回报|成长|稳健|现金|资产|龙头|行业|市场|产品|技术|研发"
    r"|暴增|激增|飙升|翻倍|高速|高增|健康|防御|优质|分红|回购"
    r"|护城河|白马|千里马|现金牛|满分|优秀|极强|突出|优异|强劲|优势|领先"
    r"|现金流|品牌|壁垒|竞争力|提升|下降|偏低|偏高|合理|充足|紧张"
    r"|中长线|仓位|分批|建仓|重仓|确定性|景气|空间|性价比|驱动"
    r"|当前|暂?未|发现|信号|评级|综合|评分|维度|指标|水平"
    r"|第一|唯一|最高|最低|最大|最小)"
)

_RE_DATA_READOUT = _re.compile(
    r"^(?:[-*#]?\s*(?:股票代码|股票名称|公司类型|行业分类|成长性|稳健性|回报性|综合分|资金回报|评级|评分)[:：]?\s*)"
    r"|^(?:[-*#]?\s*(?:成长分|稳健分|回报分)\s*\d+)"
    r"|^(?:输入|提供|给出)的(?:信息|数据)"
    r"|^(?:\d+(?:\.\d+)?分?\s*[，,。.、;；\s]*)+"
    r"|^(?:.{0,15}(?:用一句话|要求是|任务要求|用户要求))"
    r"|^(?:不许|不要|不得|综合评级|从提供|从数据看|给定信息|一句话总结|精简)"
    r"|^(?:操作建议|定性|由于行业是)[:：]"
    r"|^(?:用户给出的公司类型是|根据给出的数据)"
)

_MIN_CONTENT_LEN = 4


def clean_llm_output(text: str, max_chars: int) -> str:
    """清洗 LLM 输出：剥掉提示词回声、自我对话、多余推理，只保留正文。"""
    text = text.strip()
    text = text.lstrip(
        "\u201c\u201d\u2018\u2019\u300c\u300d\u300e\u300f\"'"
    )  # 剥中文引号

    if (
        len(text) <= max_chars
        and not _RE_NOISE.match(text)
        and not _RE_DATA_READOUT.match(text)
    ):
        return text

    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]
    real: list[str] = []

    for p in parts:
        clean = _RE_ECHO.sub("", p).strip().strip("，,。.")
        if not clean or len(clean) < _MIN_CONTENT_LEN:
            continue
        if _RE_NOISE.match(clean) or _RE_DATA_READOUT.match(clean):
            continue
        if _RE_HAS_CONTENT.search(clean):
            real.append(clean)

    if real:
        text = "；".join(real)
    elif parts:
        filtered = []
        for p in parts:
            clean = _RE_ECHO.sub("", p).strip().strip("，,。.")
            if (
                clean
                and len(clean) >= _MIN_CONTENT_LEN
                and not _RE_DATA_READOUT.match(clean)
            ):
                filtered.append(clean)
        text = filtered[-1] if filtered else parts[-1]
        for r in (_RE_ECHO, _RE_NOISE):
            text = r.sub("", text).strip().strip("，,。.")

    if len(text) > max_chars:
        text = text[:max_chars]
    return text.strip()


def clean_ts_code(ts_code: str) -> str:
    """600000.SH → 600000，自动补零至 6 位。"""
    raw = ts_code.split(".")[0] if "." in ts_code else ts_code
    return raw.zfill(6)


def write_recommend_csv(result: Top20Result, out_path: Path) -> Path:
    """写荐股 Top20 CSV。所有字段加引号以兼容 Excel 前导零。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_ALL)
        writer.writerow(OUTPUT_HEADERS_CN)
        for row in result.rows:
            writer.writerow([row.get(h, "") for h in OUTPUT_HEADERS_CN])
    return out_path
