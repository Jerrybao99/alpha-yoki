"""store.py：raw 双落盘精度、latest 忽略短横线后缀、freshness 边界。"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from src.config import Settings
from src.data.collect import expected_latest_period
from src.data.contract import ALL_OUTPUT_COLUMNS, StockFeatures
from src.data.store import (
    Kind,
    freshness,
    latest,
    load_features_prefer_raw,
    load_raw,
    raw_path,
    write_raw_csv,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path))


def test_raw_path_uses_stamp_suffix(tmp_path: Path) -> None:
    assert raw_path(tmp_path, "260915") == tmp_path / "260915-raw.csv"


def test_write_load_raw_float_repr_roundtrip(tmp_path: Path) -> None:
    """float 用 repr 落盘，读回与原值相等。"""
    awkward = 0.1 + 0.2
    path = raw_path(tmp_path, "260915")
    write_raw_csv(
        [{"ts_code": "600000.SH", "revenue": awkward, "holder_num": 25135, "end_date": "20260630"}],
        path,
        ("ts_code", "revenue", "holder_num", "end_date"),
    )
    text = path.read_text(encoding="utf-8")
    assert not text.startswith("\ufeff")
    loaded = load_raw(path)
    assert loaded[0]["revenue"] == awkward
    assert loaded[0]["holder_num"] == 25135
    assert loaded[0]["end_date"] == "20260630"


def test_latest_ignores_hyphen_suffix(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    collect = settings.data_path("fin") / "full_collect"
    collect.mkdir(parents=True)
    (collect / "260914.csv").write_text("ts_code\n", encoding="utf-8")
    (collect / "260915.csv").write_text("ts_code\n", encoding="utf-8")
    (collect / "260915-raw.csv").write_text("ts_code\n", encoding="utf-8")
    (collect / "260915-失败.csv").write_text("ts_code\n", encoding="utf-8")
    assert latest(Kind.COLLECT, settings=settings) == collect / "260915.csv"


def test_latest_missing_returns_none(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert latest(Kind.SCORES, settings=settings) is None


def test_freshness_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    today = _dt.date(2026, 9, 15)
    info = freshness(Kind.COLLECT, today, settings=settings)
    assert info.is_stale is True
    assert info.reason == "missing"
    assert info.expected_period == expected_latest_period(today)
    assert info.path is None


def test_freshness_stale_and_fresh_boundaries(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    collect = settings.data_path("fin") / "full_collect"
    collect.mkdir(parents=True)
    human = collect / "260915.csv"
    human.write_text("name,ts_code\n", encoding="utf-8")
    today = _dt.date(2026, 9, 15)
    expected = expected_latest_period(today)
    write_raw_csv(
        [{"ts_code": "600000.SH", "end_date": "20260331"}],
        raw_path(collect, "260915"),
        ("ts_code", "end_date"),
    )
    stale = freshness(Kind.COLLECT, today, settings=settings)
    assert stale.is_stale is True
    assert stale.period == "20260331"
    assert stale.stamp == "260915"
    assert stale.reason == "stale"
    assert stale.expected_period == expected

    write_raw_csv(
        [{"ts_code": "600000.SH", "end_date": expected}],
        raw_path(collect, "260915"),
        ("ts_code", "end_date"),
    )
    fresh = freshness(Kind.COLLECT, today, settings=settings)
    assert fresh.is_stale is False
    assert fresh.reason == "fresh"
    assert fresh.period == expected


def test_load_features_prefer_raw_over_human(tmp_path: Path) -> None:
    human = tmp_path / "260915.csv"
    human.write_text("股票代码,营业收入\n600000.SH,1.00元\n", encoding="utf-8-sig")
    write_raw_csv(
        [{"ts_code": "600000.SH", "revenue": 1.5e10, "name": "浦发银行"}],
        raw_path(tmp_path, "260915"),
        ("ts_code", "revenue", "name"),
    )
    features = load_features_prefer_raw(human)
    assert features[0].revenue == 1.5e10
    assert features[0].name == "浦发银行"


def test_load_features_falls_back_to_human(tmp_path: Path) -> None:
    from src.data.output import write_features_csv

    feat = StockFeatures(ts_code="600000.SH", name="浦发银行", revenue=2.0e8)
    human = write_features_csv([feat], tmp_path / "260915.csv")
    loaded = load_features_prefer_raw(human)
    assert loaded[0].ts_code == "600000.SH"
    assert loaded[0].name == "浦发银行"


def test_freshness_report_inherits_period_from_same_stamp_scores(tmp_path: Path) -> None:
    """荐股 CSV 无 end_date，按同日评分 raw 的报告期判断，避免 missing_period 误判。"""
    settings = _settings(tmp_path)
    today = _dt.date(2026, 9, 15)
    expected = expected_latest_period(today)
    scores = settings.data_path("fin") / "full_scores"
    report = settings.data_path("fin") / "full_report"
    scores.mkdir(parents=True)
    report.mkdir(parents=True)
    (scores / "260915.csv").write_text("ts_code\n", encoding="utf-8")
    write_raw_csv(
        [{"ts_code": "600000.SH", "end_date": expected}],
        raw_path(scores, "260915"),
        ("ts_code", "end_date"),
    )
    (report / "260915.csv").write_text("股票代码,点评\n000807,盯住增速\n", encoding="utf-8")
    info = freshness(Kind.REPORT, today, settings=settings)
    assert info.is_stale is False
    assert info.reason == "fresh"
    assert info.period == expected


def test_write_raw_uses_all_output_columns(tmp_path: Path) -> None:
    feat = StockFeatures(ts_code="600000.SH", holder_num=99, revenue=1.0)
    path = raw_path(tmp_path, "260915")
    write_raw_csv([feat.model_dump()], path, ALL_OUTPUT_COLUMNS)
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == list(ALL_OUTPUT_COLUMNS)
    assert load_raw(path)[0]["holder_num"] == 99
