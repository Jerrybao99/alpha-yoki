"""格式化财务 CSV 的查找与反序列化。"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from src.data.contract import FIELD_CN, FIELD_UNIT, PERCENT_FIELDS, StockFeatures

CN_TO_FIELD: dict[str, str] = {cn: en for en, cn in FIELD_CN.items()}

_NON_NUMERIC_FIELDS = frozenset(
    {
        "ts_code",
        "symbol",
        "name",
        "industry",
        "ann_date",
        "f_ann_date",
        "end_date",
        "report_type",
        "comp_type",
        "end_type",
        "update_flag",
    }
)


def find_latest_csv(csv_dir: Path) -> Path | None:
    """返回目录下最新的 YYMMDD.csv，忽略带短横线后缀的文件。"""
    if not csv_dir.exists():
        return None
    candidates = [p for p in csv_dir.glob("*.csv") if re.fullmatch(r"\d{6}", p.stem)]
    return max(candidates) if candidates else None


def parse_formatted_value(text: str, field: str) -> float | str | None:
    """将 format_value 生成的文本还原为 float、str 或 None。"""
    if not text:
        return "" if field in _NON_NUMERIC_FIELDS else None
    if field in _NON_NUMERIC_FIELDS:
        return text
    if field in PERCENT_FIELDS:
        return float(text.rstrip("%"))
    if "亿" in text:
        cleaned = re.sub(r"[亿万元/股次倍]", "", text)
        return float(cleaned) * 1e8
    if "万" in text:
        cleaned = re.sub(r"[万元/股次倍]", "", text)
        return float(cleaned) * 1e4
    unit = FIELD_UNIT.get(field, "")
    if unit in ("元/股", "倍", "次"):
        return float(text.rstrip("元/股倍次"))
    if unit == "比率":
        return float(text)
    if unit == "元":
        stripped = text.rstrip("元")
        try:
            return float(stripped)
        except ValueError:
            return text
    if unit == "股":
        stripped = text.rstrip("股")
        try:
            return float(stripped)
        except ValueError:
            return text
    if unit == "户":
        stripped = text.rstrip("户")
        try:
            return int(float(stripped))
        except ValueError:
            return text
    try:
        return float(text)
    except ValueError:
        return text


def load_features_csv(csv_path: Path) -> list[StockFeatures]:
    """从采集 CSV 反序列化 StockFeatures 列表。"""
    content = csv_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    reader = csv.DictReader(content.splitlines())
    columns = reader.fieldnames or []
    features: list[StockFeatures] = []
    for row in reader:
        kwargs: dict[str, Any] = {}
        for column in columns:
            field = CN_TO_FIELD.get(column, column)
            kwargs[field] = parse_formatted_value(row.get(column, ""), field)
        if "ts_code" not in kwargs:
            kwargs["ts_code"] = kwargs.get("symbol", "")
        features.append(StockFeatures(**kwargs))
    return features
