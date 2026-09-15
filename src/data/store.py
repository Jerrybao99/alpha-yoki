"""机读 raw CSV 与产物新鲜度：人读 CSV 并行落盘，步骤间优先读 raw。"""

from __future__ import annotations

import ast
import csv
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.config import Settings, get_settings
from src.data.collect import expected_latest_period
from src.data.contract import StockFeatures
from src.data.readers import find_latest_csv, load_features_csv

KIND_DIRS: dict[str, str] = {
    "collect": "full_collect",
    "scores": "full_scores",
    "report": "full_report",
}


class Kind(StrEnum):
    COLLECT = "collect"
    SCORES = "scores"
    REPORT = "report"


class Freshness(BaseModel):
    """产物相对法定最新报告期的新鲜度。"""

    model_config = ConfigDict(extra="forbid")

    kind: Kind
    path: Path | None
    stamp: str | None
    period: str | None
    expected_period: str
    is_stale: bool
    reason: str


def raw_path(directory: Path, stamp: str) -> Path:
    return directory / f"{stamp}-raw.csv"


def sibling_raw(human_path: Path) -> Path:
    return human_path.with_name(f"{human_path.stem}-raw.csv")


def kind_dir(kind: Kind, settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return resolved.data_path("fin") / KIND_DIRS[kind]


def _cell_out(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return repr(value)
    return str(value)


def _cell_in(text: str) -> Any:
    if text == "":
        return None
    if len(text) == 8 and text.isdigit():
        return text
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def write_raw_csv(rows: list[dict[str, Any]], out_path: Path, columns: Sequence[str]) -> Path:
    """英文列头、UTF-8 无 BOM、LF；数值用 repr 保精度。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(list(columns))
        for row in rows:
            writer.writerow([_cell_out(row.get(col)) for col in columns])
    return out_path


def load_raw(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8").lstrip("\ufeff")
    reader = csv.DictReader(content.splitlines())
    return [{key: _cell_in(value or "") for key, value in row.items()} for row in reader]


def latest(kind: Kind, settings: Settings | None = None) -> Path | None:
    return find_latest_csv(kind_dir(kind, settings))


def _period_from_artifact(human_path: Path) -> str | None:
    raw = sibling_raw(human_path)
    if raw.exists():
        rows = load_raw(raw)
        if rows:
            period = rows[0].get("end_date")
            return str(period) if period else None
    if human_path.exists():
        features = load_features_csv(human_path)
        if features and features[0].end_date:
            return features[0].end_date
    return None


def freshness(kind: Kind, today: date, settings: Settings | None = None) -> Freshness:
    expected = expected_latest_period(today)
    path = latest(kind, settings)
    if path is None:
        return Freshness(
            kind=kind,
            path=None,
            stamp=None,
            period=None,
            expected_period=expected,
            is_stale=True,
            reason="missing",
        )
    period = _period_from_artifact(path)
    if period is None:
        return Freshness(
            kind=kind,
            path=path,
            stamp=path.stem,
            period=None,
            expected_period=expected,
            is_stale=True,
            reason="missing_period",
        )
    stale = period < expected
    return Freshness(
        kind=kind,
        path=path,
        stamp=path.stem,
        period=period,
        expected_period=expected,
        is_stale=stale,
        reason="stale" if stale else "fresh",
    )


_STRING_FIELDS = frozenset({"ts_code", "symbol", "name", "industry"})


def load_features_prefer_raw(human_path: Path) -> list[StockFeatures]:
    raw = sibling_raw(human_path)
    if raw.exists():
        features: list[StockFeatures] = []
        for row in load_raw(raw):
            for key in _STRING_FIELDS:
                if row.get(key) is None:
                    row[key] = ""
            features.append(StockFeatures(**row))
        return features
    return load_features_csv(human_path)
