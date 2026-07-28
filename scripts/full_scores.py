"""全量 A 股评分评级脚本（ROADMAP Step 2-4）。

读取 ``data/fin/full_collect/`` 最新日期 csv，逐行调用 scores.py 纯函数计算
三维评分/综合分/评级，追加五列后落盘 ``data/fin/full_scores/YYMMDD.csv``，
触发一票否决的股票记入 ``-否决.csv``。

用法：
  uv run python scripts/full_scores.py
  uv run python scripts/full_scores.py --input data/fin/full_collect/260724.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import re
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.data.contract import ALL_OUTPUT_COLUMNS, PERCENT_FIELDS, StockFeatures
from src.data.output import FIELD_CN, FIELD_UNIT, format_value
from src.scoring.scores import (
    check_veto,
    score_composite,
    score_growth,
    score_rating,
    score_return,
    score_stability,
)

SCORING_HEADERS = ("成长性", "稳健性", "资金回报", "综合分", "评级")

_CN_TO_FIELD: dict[str, str] = {cn: en for en, cn in FIELD_CN.items()}


def _find_latest(csv_dir: Path) -> Path | None:
    """返回目录下最新 YYMMDD.csv（不含短横线后缀的连接文件）。"""
    if not csv_dir.exists():
        return None
    candidates = [p for p in csv_dir.glob("*.csv") if re.fullmatch(r"\d{6}", p.stem)]
    return max(candidates) if candidates else None


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


def _parse_value(text: str, field: str) -> float | str | None:
    """将 format_value 格式化后的 CSV 文本还原为原始 float/str/None。"""
    if not text:
        return None
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
    try:
        return float(text)
    except ValueError:
        return text


def _load_features(csv_path: Path) -> list[StockFeatures]:
    """从 full_collect CSV 反序列化为 StockFeatures 列表（中文列头→英文字段名）。"""
    content = csv_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    reader = csv.DictReader(content.splitlines())
    cn_cols = reader.fieldnames or []
    features: list[StockFeatures] = []
    for row in reader:
        kwargs: dict[str, Any] = {}
        for cn in cn_cols:
            en = _CN_TO_FIELD.get(cn, cn)
            kwargs[en] = _parse_value(row.get(cn, ""), en)
        if "ts_code" not in kwargs:
            kwargs["ts_code"] = kwargs.get("symbol", "")
        features.append(StockFeatures(**kwargs))
    return features


def run_scores(
    features: list[StockFeatures],
) -> tuple[list[dict], list[dict]]:
    """对 StockFeatures 列表逐行评分，返回 (评分结果行列表, 否决行列表)。"""
    results: list[dict] = []
    vetoes: list[dict] = []

    for feat in features:
        veto_triggers = check_veto(feat)
        row = feat.model_dump()
        row["成长性"] = score_growth(feat)
        row["稳健性"] = score_stability(feat)
        row["资金回报"] = score_return(feat)
        row["综合分"] = score_composite(
            row["成长性"],
            row["稳健性"],
            row["资金回报"],
            feat.industry or "未分类",
        )
        row["评级"] = score_rating(row["综合分"])

        if veto_triggers:
            vetoes.append(
                {
                    "ts_code": feat.ts_code,
                    "name": row.get("name", ""),
                    "否决项": ",".join(vt.rule for vt in veto_triggers),
                    "原因": "; ".join(vt.reason for vt in veto_triggers),
                }
            )
        else:
            results.append(row)

    return results, vetoes


def _write_scoring_csv(
    out_path: Path,
    rows: list[dict],
    columns: tuple[str, ...],
) -> None:
    """写评分结果 CSV：原始列（format_value 格式化）+ 评分列（原值）。"""
    all_cols = list(columns) + list(SCORING_HEADERS)
    headers = [FIELD_CN.get(c, c) for c in all_cols]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(headers)
        for row in rows:
            formatted = []
            for c in all_cols:
                if c in SCORING_HEADERS:
                    formatted.append(str(row.get(c, "")))
                else:
                    formatted.append(format_value(c, row.get(c)))
            w.writerow(formatted)


def _write_veto_csv(out_path: Path, vetoes: list[dict]) -> None:
    """写一票否决清单。"""
    if not vetoes:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["ts_code", "name", "否决项", "原因"])
        for v in vetoes:
            w.writerow([v["ts_code"], v["name"], v["否决项"], v["原因"]])


def main() -> None:
    parser = argparse.ArgumentParser(description="全量 A 股评分评级并落地 CSV")
    parser.add_argument(
        "--input", default=None, help="full_collect CSV 路径（默认取最新）"
    )
    parser.add_argument(
        "--out-dir", default=None, help="输出目录（默认 data/fin/full_scores/）"
    )
    args = parser.parse_args()

    settings = get_settings()
    date = _dt.date.today()
    stamp = date.strftime("%y%m%d")

    if args.input:
        csv_path = Path(args.input)
    else:
        collect_dir = settings.data_path("fin") / "full_collect"
        csv_path = _find_latest(collect_dir)
        if csv_path is None:
            raise SystemExit(
                "找不到采集数据，请先运行 uv run python scripts/full_collect.py"
            )

    print(f"读取采集数据：{csv_path}")
    features = _load_features(csv_path)
    print(f"共 {len(features)} 条记录")

    results, vetoes = run_scores(features)
    print(f"评分完成：{len(results)} 股通过，{len(vetoes)} 股否决")

    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else settings.data_path("fin") / "full_scores"
    )

    out_path = out_dir / f"{stamp}.csv"
    _write_scoring_csv(out_path, results, ALL_OUTPUT_COLUMNS)
    print(f"评分结果：{out_path}")

    if vetoes:
        veto_path = out_dir / f"{stamp}-否决.csv"
        _write_veto_csv(veto_path, vetoes)
        print(f"否决清单：{veto_path}")


if __name__ == "__main__":
    main()
