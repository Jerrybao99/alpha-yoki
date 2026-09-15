"""荐股报告纯逻辑：常量、评分 CSV 解析、13 列 CSV / Markdown 写盘。不触网络。
锐评文案的生成、校验与兜底见 src/llm/，编排见 src/reports/generator.py。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.data.contract import StockFeatures
from src.data.readers import (
    CN_TO_FIELD as _CN_TO_FIELD,
)
from src.data.readers import (
    parse_formatted_value as _parse_value,
)
from src.data.store import load_raw, sibling_raw

SCORING_KEYS = ("成长性", "稳健性", "资金回报", "综合分", "评级")

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

TOP_N = 50


@dataclass
class Top20Result:
    """13 列行数据 + 与行对齐的锐评状态（ReviewStatus 枚举值），供终端汇总与审计。"""

    rows: list[dict[str, str]] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)


def load_scoring_rows(csv_path: Path) -> list[dict[str, Any]]:
    """读取评分 CSV，返回中文列头 key + 原始值的行列表。"""
    content = csv_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    reader = csv.DictReader(content.splitlines())
    return [dict(row) for row in reader]


def load_score_rows_prefer_raw(human_path: Path) -> list[dict[str, Any]]:
    """有 raw 则读机读评分；否则回退人读 CSV 并反序列化。"""
    raw = sibling_raw(human_path)
    if raw.exists():
        return load_raw(raw)
    return [parse_back(row) for row in load_scoring_rows(human_path)]


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


def clean_ts_code(ts_code: str) -> str:
    """600000.SH → 600000，自动补零至 6 位。"""
    raw = ts_code.split(".")[0] if "." in ts_code else ts_code
    return raw.zfill(6)


def _cell(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "").strip()


def render_top20_markdown(rows: list[dict[str, Any]], *, stamp: str = "") -> str:
    """把荐股 13 列全文转成 Markdown，最多 TOP_N 条。"""
    title = f"# 荐股 Top{TOP_N}" + (f" · {stamp}" if stamp else "")
    blocks = [title]
    for index, row in enumerate(rows[:TOP_N], start=1):
        name = _cell(row, "股票名称") or _cell(row, "name")
        code = _cell(row, "股票代码") or _cell(row, "ts_code")
        blocks.append(f"## {index}. {name}（{code}）")
        for header in OUTPUT_HEADERS_CN[2:]:
            blocks.append(f"- {header}：{_cell(row, header)}")
    return "\n".join(blocks) + "\n"


def write_recommend_markdown(
    rows: list[dict[str, Any]],
    out_path: Path,
    *,
    stamp: str | None = None,
) -> Path:
    """UTF-8 Markdown，与同名 CSV 并列落在 full_report/。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = render_top20_markdown(rows, stamp=stamp if stamp is not None else out_path.stem)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def write_recommend_csv(result: Top20Result, out_path: Path) -> Path:
    """写荐股 TopN CSV，并并列写同名 Markdown。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_ALL)
        writer.writerow(OUTPUT_HEADERS_CN)
        for row in result.rows:
            writer.writerow([row.get(h, "") for h in OUTPUT_HEADERS_CN])
    write_recommend_markdown(result.rows, out_path.with_suffix(".md"), stamp=out_path.stem)
    return out_path
