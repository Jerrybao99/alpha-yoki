"""Step 1.4 冒烟采集集成测试。mock 数据源验证两张 CSV 落地与格式化
（中文列头/百分比/亿万/CJK 对齐/数据来源表）。不触网络。
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from scripts.smoke_collect import run_smoke
from src.config import Settings, get_settings
from src.data.contract import StockFeatures, StockInfo
from src.data.provider import BaseFetcher, TushareFetcher


class _FakeFetcher(BaseFetcher):
    def __init__(self, features: dict[str, StockFeatures]) -> None:
        self.features = features

    def fetch_stock_list(self) -> list[StockInfo]:
        return [
            StockInfo(ts_code=c, symbol=c.split(".")[0], name=c)
            for c in sorted(self.features)
        ]

    def fetch_financials(self, ts_code, period=None):
        return StockFeatures(**self.features[ts_code].model_dump())


def _settings(data_dir: Path) -> Settings:
    return Settings(tushare_token="t", data_dir=str(data_dir), concurrency=2)


def _feat(ts_code: str) -> StockFeatures:
    return StockFeatures(
        ts_code=ts_code,
        symbol=ts_code.split(".")[0],
        name=ts_code,
        industry="银行",
        end_date="20241231",
        revenue=1.5e10,  # 150亿
        n_income_attr_p=3.4e9,  # 34亿
        roe=12.5,
        netprofit_yoy=20.0,  # 百分比
    )


def test_smoke_writes_two_csvs(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(
        {c: _feat(c) for c in ("600000.SH", "000001.SZ", "000002.SZ")}
    )
    out = tmp_path / "test"
    feat_path, src_path, ok, fail = run_smoke(
        fetcher,
        _settings(tmp_path),
        sample=2,
        out_dir=out,
        date=_dt.date(2026, 7, 23),
        seed=1,
    )
    assert ok == 2 and fail == 0
    assert feat_path.name == "260723.csv"
    assert src_path.name == "260723-数据来源.csv"
    assert feat_path.exists() and src_path.exists()


def test_features_csv_chinese_header_and_format(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(
        {"600000.SH": _feat("600000.SH"), "000001.SZ": _feat("000001.SZ")}
    )
    out = tmp_path / "test"
    feat_path, _, _, _ = run_smoke(
        fetcher, _settings(tmp_path), 2, out, date=_dt.date(2026, 7, 23)
    )
    text = feat_path.read_text(encoding="utf-8-sig")
    header = text.strip().split("\n")[0].lstrip("\ufeff")
    # 中文列头存在（首列：name → 无映射回退原字段名；次列：ts_code → "TS代码"）
    assert "name" in header
    assert "TS代码" in header
    assert "营业收入" in header
    # symbol 列不再出现
    assert "股票代码(ts_code)" not in header
    # 已删除/不再输出的列不应出现
    assert "上市日期" not in header
    assert "公告日期" in header  # ann_date 已恢复为输出列
    assert "财务费用利息收入" not in header
    assert "每股分红" not in header
    assert "分红进度" not in header
    # 百分比带 % 两位小数
    assert "20.00%" in text
    # 大数用亿/万（非科学计数法）；金额字段加「元」后缀
    assert "150.00亿元" in text
    assert "34.00亿元" in text
    # 非金额字段（百分比）不加「元」
    assert "20.00%元" not in text
    # 无科学计数法
    assert "e+" not in text.lower() and "E+" not in text
    # 已删除的列不再出现
    assert "交易日" not in header
    assert "流通股本" not in header
    assert "市盈率" not in header
    assert "市净率" not in header
    assert "股息率" not in header
    assert "总市值" not in header
    assert "流通市值" not in header
    assert "审计结果" not in header
    assert "会计事务所" not in header
    assert "质押比例" not in header


def test_features_csv_cells_clean_no_trailing_spaces(tmp_path: Path) -> None:
    """单元格无首尾空格，Excel 双击列边界即可自适应列宽。"""
    fetcher = _FakeFetcher(
        {"600000.SH": _feat("600000.SH"), "000001.SZ": _feat("000001.SZ")}
    )
    out = tmp_path / "test"
    feat_path, _, _, _ = run_smoke(
        fetcher, _settings(tmp_path), 2, out, date=_dt.date(2026, 7, 23)
    )
    text = feat_path.read_text(encoding="utf-8-sig")
    if text.endswith("\n"):
        text = text[:-1]
    for lineno, line in enumerate(text.split("\n"), start=1):
        for colno, cell in enumerate(line.split(","), start=1):
            assert cell == cell.strip(), f"行{lineno}列{colno}有首尾空格: {cell!r}"


def test_data_source_csv_content(tmp_path: Path) -> None:
    fetcher = _FakeFetcher({"600000.SH": _feat("600000.SH")})
    out = tmp_path / "test"
    _, src_path, _, _ = run_smoke(
        fetcher, _settings(tmp_path), 1, out, date=_dt.date(2026, 7, 23)
    )
    text = src_path.read_text(encoding="utf-8-sig")
    assert text.startswith("接口,字段,字段中文,单位,单位来源,文档URL")
    # 含 vip 接口名与文档 URL
    assert "income_vip" in text
    assert "https://tushare.pro/document/2?doc_id=" in text
    # 不再使用 dividend 接口
    assert "dividend" not in text
    # ts_code 归属 stock_basic 接口（不因 income 也含 ts_code 而被覆写）
    assert "stock_basic,ts_code,TS代码," in text
    # 单位与来源：推断（百分比 %），FIELD_CN 来自 field_mappings
    assert "netprofit_yoy,归属母公司股东的净利润同比增长率,%,推断," in text
    # 每行 6 列（5 个逗号）
    for ln in text.strip().split("\n")[1:]:
        assert ln.count(",") == 5


def test_smoke_sample_clamped(tmp_path: Path) -> None:
    """采样数超过清单时自动收敛到清单大小。"""
    fetcher = _FakeFetcher({"600000.SH": _feat("600000.SH")})
    out = tmp_path / "test"
    _, _, ok, _ = run_smoke(
        fetcher, _settings(tmp_path), 5, out, date=_dt.date(2026, 7, 23)
    )
    assert ok == 1


@pytest.mark.network
def test_smoke_regenerates_latest_csv() -> None:
    """真实采集 5 股，用最新数据覆盖落地到 ``data/test/smoke_collect_test.csv``（固定文件名）。

    每次清空缓存以确保取最新报告期；同名文件直接覆盖。
    校验 end_date 与 Tushare 独立重查一致，且不早于法定最新报告期。
    本地运行：``uv run pytest -m network \
    integrated_tests/test_smoke_collect.py::test_smoke_regenerates_latest_csv``
    无 TUSHARE_TOKEN 时 skip；CI 因 ``-m "not network"`` 跳过。
    """
    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")
    cache_dir = settings.data_root / "cache"
    if cache_dir.exists():
        for p in cache_dir.glob("*.json"):
            p.unlink()
    fetcher = TushareFetcher(settings)
    out_dir = settings.data_root / "test" / "smoke_collect"
    feat_path, src_path, ok, fail = run_smoke(
        fetcher, settings, 5, out_dir, filename="smoke_collect_test"
    )
    assert ok == 5 and fail == 0, f"采集未全部成功：ok={ok} fail={fail}"
    assert feat_path.exists() and src_path.exists()

    # 交叉校验：end_date 与 Tushare 独立重查一致，且不早于法定最新报告期
    import csv

    import tushare as ts

    from src.data.collect import expected_latest_period
    from src.data.contract import ALL_OUTPUT_COLUMNS

    ts.set_token(settings.tushare_token)
    pro = ts.pro_api()
    expected = expected_latest_period(_dt.date.today())

    text = feat_path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(text.splitlines()))
    idx = {c: i for i, c in enumerate(ALL_OUTPUT_COLUMNS)}
    checked = 0
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        cells = [c.strip() for c in r]
        ts_code = cells[idx["ts_code"]]
        csv_end = cells[idx["end_date"]]
        tushare_end = max(
            rr["end_date"]
            for rr in pro.query(
                "income_vip", ts_code=ts_code, fields="ts_code,end_date"
            ).to_dict("records")
            if rr.get("end_date")
        )
        assert csv_end == tushare_end, (
            f"{ts_code} end_date CSV={csv_end} != Tushare={tushare_end}"
        )
        assert csv_end >= expected, f"{ts_code} end_date {csv_end} 早于预期 {expected}"
        checked += 1
    assert checked >= 1, "CSV 无有效数据行"
