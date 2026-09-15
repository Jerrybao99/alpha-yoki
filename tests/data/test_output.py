"""output.py 单测：format_value 各分支、write_features_csv、write_data_source_csv。不触网络。"""

from __future__ import annotations

import csv
from pathlib import Path

from src.data.contract import ALL_OUTPUT_COLUMNS, PERCENT_FIELDS, StockFeatures
from src.data.output import (
    FIELD_CN,
    FIELD_TO_INTERFACE,
    format_value,
    write_data_source_csv,
    write_features_csv,
)
from src.data.readers import parse_formatted_value


def _feat(ts_code: str, **kw) -> StockFeatures:
    return StockFeatures(ts_code=ts_code, **kw)


# ===== format_value =====
def test_format_value_none_returns_empty() -> None:
    assert format_value("revenue", None) == ""


def test_format_value_percent_field() -> None:
    """PERCENT_FIELDS 内的字段返回 .2f% 字符串。"""
    for f in PERCENT_FIELDS:
        assert format_value(f, 30.5) == "30.50%", f
    assert format_value(list(PERCENT_FIELDS)[0], 0) == "0.00%"


def test_format_value_roe_percent() -> None:
    """roe 不在 PERCENT_FIELDS 但 unit 为 %，同样 .2f%。"""
    assert format_value("roe", 15.0) == "15.00%"


def test_format_value_ratio() -> None:
    """ocf_to_shortdebt unit 为比率，仅两位小数无后缀。"""
    assert format_value("ocf_to_shortdebt", 1.5) == "1.50"


def test_format_value_fixed_unit_times() -> None:
    assert format_value("current_ratio", 2.5) == "2.50倍"
    assert format_value("inv_turn", 3.0) == "3.00次"


def test_format_value_yuan_per_share() -> None:
    assert format_value("eps", 1.2) == "1.20元/股"
    assert format_value("bps", 8.5) == "8.50元/股"
    assert format_value("ocfps", 0.5) == "0.50元/股"


def test_format_value_yuan_hundred_million() -> None:
    """>= 1e8 的金额用亿。"""
    assert format_value("revenue", 1.5e10) == "150.00亿元"


def test_format_value_yuan_ten_thousand() -> None:
    """1e4 ≤ v < 1e8 的金额用万。"""
    assert format_value("revenue", 5e6) == "500.00万元"


def test_format_value_yuan_below_ten_thousand() -> None:
    """< 1e4 的金额直接用元。"""
    assert format_value("revenue", 500) == "500.00元"


def test_format_value_yuan_boundary_ten_thousand_to_hundred_million() -> None:
    """接近 1e8 边界的值应正确归入亿级，避免 '10000.00万元' 这种异常显示。"""
    assert format_value("revenue", 99_999_995) == "1.00亿元"
    assert format_value("c_paid_invest", 99_999_950) == "1.00亿元"
    assert format_value("revenue", 99_950_000) == "9995.00万元"
    assert format_value("revenue", 9_999_995) == "1000.00万元"


def test_format_value_gu_hundred_million() -> None:
    """total_share 股份数用亿。"""
    assert format_value("total_share", 3.56e8) == "3.56亿股"


def test_format_value_gu_ten_thousand() -> None:
    assert format_value("total_share", 5e6) == "500.00万股"


def test_format_value_no_unit_field() -> None:
    """无单位字段按数值缩放，无后缀。"""
    assert format_value("assets_to_eqt", 2.0) == "2.00倍"


def test_format_value_non_numeric() -> None:
    assert format_value("ts_code", "600000.SH") == "600000.SH"
    assert format_value("name", "浦发银行") == "浦发银行"


def test_format_value_holder_num_households() -> None:
    """股东户数按整数 + 户输出，不走亿/万缩放。"""
    assert format_value("holder_num", 25135) == "25135户"
    assert format_value("holder_num", 25135.0) == "25135户"
    assert format_value("holder_num", None) == ""


def test_parse_formatted_value_holder_num() -> None:
    """人读「户」可还原为数值。"""
    assert parse_formatted_value("25135户", "holder_num") == 25135
    assert parse_formatted_value("", "holder_num") is None


def test_holder_num_interface_trace() -> None:
    assert FIELD_TO_INTERFACE["holder_num"] == "stk_holdernumber"


# ===== write_features_csv =====
def test_write_features_csv(tmp_path: Path) -> None:
    feats = [_feat("600000.SH", revenue=1.5e10, roe=15.0, netprofit_yoy=20.0)]
    out = write_features_csv(feats, tmp_path / "test.csv")
    assert out.exists()
    content = out.read_text(encoding="utf-8-sig")
    header = list(csv.reader(content.splitlines()))[0]
    assert header == [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    assert "150.00亿元" in content
    assert "15.00%" in content
    assert "20.00%" in content


def test_write_features_csv_permission_error(tmp_path: Path) -> None:
    """目标路径是目录而非文件时，write_text 抛 PermissionError，回落写临时文件。"""
    feats = [_feat("600000.SH", revenue=1.5e10)]
    out_path = tmp_path / "test.csv"
    out_path.mkdir()  # 让 out_path 成为目录 → write_text 失败

    out = write_features_csv(feats, out_path)
    assert out == out_path
    # 临时文件应存在
    tmps = list(tmp_path.glob("test.csv*"))
    assert len(tmps) >= 2  # 原目录 + 临时文件


# ===== write_data_source_csv =====
def test_write_data_source_csv(tmp_path: Path) -> None:
    out = write_data_source_csv(tmp_path / "data_source.csv")
    assert out.exists()
    content = out.read_text(encoding="utf-8-sig")
    lines = content.strip().split("\n")
    assert len(lines) > 1
    header = lines[0].split(",")
    assert header == ["接口", "字段", "字段中文", "单位", "单位来源", "文档URL"]
