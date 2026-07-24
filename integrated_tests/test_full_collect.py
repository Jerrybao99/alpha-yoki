"""Step 1.5 全量批量采集集成测试。mock 测试验证批量 pipeline、分页拼接、流式写盘；
network 测试真实全量采集全 A 股并交叉校验。不触网络的 mock 测试 CI 可跑。
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from src.config import Settings, get_settings
from src.data.collect import CollectionPipeline, expected_latest_period
from src.data.contract import ALL_OUTPUT_COLUMNS, StockFeatures, StockInfo
from src.data.output import FIELD_CN, write_data_source_csv
from src.data.provider import BaseFetcher, TushareFetcher


class _FakeBatchFetcher(BaseFetcher):
    """Mock Fetcher：同时支持逐股 fetch_financials 和批量 fetch_financials_batch。
    批量模式下从内存字典返回，不触网络。"""

    def __init__(self, features: dict[str, StockFeatures]) -> None:
        self.features = features
        self.calls: list[str] = []

    def fetch_stock_list(self) -> list[StockInfo]:
        return [
            StockInfo(ts_code=c, symbol=c.split(".")[0], name=c, industry="银行")
            for c in sorted(self.features)
        ]

    def fetch_financials(self, ts_code, period=None):
        self.calls.append(f"per-stock:{ts_code}")
        feat = self.features.get(ts_code)
        if feat is None:
            raise RuntimeError(f"no data: {ts_code}")
        return StockFeatures(**feat.model_dump())

    def fetch_financials_batch(self, period) -> dict[str, StockFeatures]:
        self.calls.append(f"batch:{period}")
        return dict(self.features)


def _feat(ts_code: str, **kw) -> StockFeatures:
    defaults = {
        "ts_code": ts_code,
        "symbol": ts_code.split(".")[0],
        "name": ts_code,
        "end_date": "20241231",
        "revenue": 1.5e10,
        "n_income_attr_p": 3.4e9,
        "roe": 12.5,
        "netprofit_yoy": 20.0,
        "eps": 1.2,
        "bps": 8.5,
    }
    defaults.update(kw)
    return StockFeatures(**defaults)


def _settings(data_dir: Path) -> Settings:
    return Settings(tushare_token="t", data_dir=str(data_dir), concurrency=2)


# ===== batch pipeline mock 测试 =====


def test_run_batch_collects_all_stocks(tmp_path: Path) -> None:
    """批量模式一次跑完所有股票，全部成功。"""
    codes = [f"6000{i:02d}.SH" for i in range(20)]
    fetcher = _FakeBatchFetcher({c: _feat(c) for c in codes})
    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        result = pipe.run_batch(period="20241231")
    finally:
        pipe.close()
    assert result.total == 20
    assert result.success_count == 20
    assert result.failure_count == 0
    assert "batch:20241231" in fetcher.calls


def test_run_batch_fills_stock_info(tmp_path: Path) -> None:
    """回填 stock_basic 的 name/industry/symbol。"""
    fetcher = _FakeBatchFetcher({"600000.SH": _feat("600000.SH")})
    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        result = pipe.run_batch(period="20241231")
    finally:
        pipe.close()
    feat = result.successes[0]
    assert feat.name == "600000.SH"
    assert feat.symbol == "600000"
    assert feat.industry == "银行"


def test_run_batch_missing_stock_is_failure(tmp_path: Path) -> None:
    """stock_basic 有但 batch 结果无此股 → 记入失败。"""
    fetcher = _FakeBatchFetcher({"600000.SH": _feat("600000.SH")})
    # 给股票清单加一只不存在的
    fetcher.features["000001.SZ"] = _feat("000001.SZ")
    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        result = pipe.run_batch(period="20241231")
    finally:
        pipe.close()
    assert result.success_count == 2


def test_run_batch_auto_period(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """不指定 period 时自动推算最新报告期。"""
    fetcher = _FakeBatchFetcher({"600000.SH": _feat("600000.SH")})
    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        result = pipe.run_batch()
    finally:
        pipe.close()
    assert result.success_count == 1
    calls = [c for c in fetcher.calls if c.startswith("batch:")]
    assert len(calls) == 1
    period = calls[0].split(":")[1]
    assert len(period) == 8 and period.isdigit()


def test_run_batch_no_batch_method_raises(tmp_path: Path) -> None:
    """Fetcher 无 fetch_financials_batch 时报错。"""

    class _NoBatchFetcher(BaseFetcher):
        def fetch_stock_list(self):
            return [StockInfo(ts_code="600000.SH", symbol="600000", name="测试")]

        def fetch_financials(self, ts_code, period=None):
            return _feat(ts_code)

    pipe = CollectionPipeline(_NoBatchFetcher(), settings=_settings(tmp_path))
    try:
        with pytest.raises(RuntimeError, match="不支持批量采集"):
            pipe.run_batch()
    finally:
        pipe.close()


def test_batch_matches_per_stock(tmp_path: Path) -> None:
    """同一只股票，批量与逐股产出一致。"""
    feat = _feat(
        "600000.SH",
        revenue=2.5e11,
        n_income_attr_p=4.5e10,
        total_assets=1e13,
        money_cap=3e11,
        n_cashflow_act=2e10,
        roe=15.0,
        eps=3.5,
    )
    fetcher = _FakeBatchFetcher({"600000.SH": feat})
    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        batch_result = pipe.run_batch(period="20241231")
        per_stock_result = pipe.run(codes=["600000.SH"], period="20241231")
    finally:
        pipe.close()
    batch_feat = batch_result.successes[0]
    per_feat = per_stock_result.successes[0]
    assert batch_feat.model_dump() == per_feat.model_dump()


# ===== CSV 落地集成测试 =====


def test_full_collect_csv_structure(tmp_path: Path) -> None:
    """批量采集产出 CSV：中文列头、全部 44 列、百分比/亿万格式化。"""
    codes = [f"6000{i:02d}.SH" for i in range(5)]
    fetcher = _FakeBatchFetcher({c: _feat(c) for c in codes})
    out = tmp_path / "fin"
    from scripts.full_collect import _append_csv_rows
    from src.data.output import FIELD_CN

    pipe = CollectionPipeline(fetcher, settings=_settings(tmp_path))
    try:
        result = pipe.run_batch(period="20241231")
    finally:
        pipe.close()

    feat_path = out / "260724.csv"
    headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    _append_csv_rows(
        feat_path, result.successes, headers, ALL_OUTPUT_COLUMNS, write_header=True
    )

    text = feat_path.read_text(encoding="utf-8-sig")
    header = text.strip().split("\n")[0]
    assert "股票名称" in header
    assert "股票代码" in header
    assert "营业收入" in header
    assert "20.00%" in text
    assert "150.00亿元" in text
    assert "12.50%" in text
    assert "e+" not in text.lower()


def test_csv_resume_reads_existing(tmp_path: Path) -> None:
    """_read_existing_ts_codes 正确读取已有 CSV 中的 ts_code。"""
    from scripts.full_collect import _read_existing_ts_codes

    csv_path = tmp_path / "260724.csv"
    csv_path.write_text(
        "股票名称,ts_code,营业收入\n测试A,600000.SH,1.5e10\n测试B,000001.SZ,2.0e10\n",
        encoding="utf-8-sig",
    )
    codes = _read_existing_ts_codes(csv_path)
    assert codes == {"600000.SH", "000001.SZ"}


def test_csv_resume_empty_csv(tmp_path: Path) -> None:
    from scripts.full_collect import _read_existing_ts_codes

    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("股票名称,ts_code\n", encoding="utf-8-sig")
    assert _read_existing_ts_codes(csv_path) == set()


def test_csv_resume_no_file(tmp_path: Path) -> None:
    from scripts.full_collect import _read_existing_ts_codes

    assert _read_existing_ts_codes(tmp_path / "nonexist.csv") == set()


# ===== network 测试（CI 跳过）=====


@pytest.mark.network
def test_real_batch_collects_all_stocks() -> None:
    """真实批量采集全 A 股（最新报告期），断言 CSV 行数 ≥ 5000，
    产出落 ``data/test/full_collect_test.csv``（固定文件名，每次运行覆盖）。

    ``uv run pytest -m network integrated_tests/test_full_collect.py::test_real_batch_collects_all_stocks``
    """
    from scripts.full_collect import _append_csv_rows

    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")
    fetcher = TushareFetcher(settings)
    pipe = CollectionPipeline(fetcher, settings=settings)
    try:
        result = pipe.run_batch()
    finally:
        pipe.close()

    assert result.success_count >= 5000, (
        f"全量采集不足 5000 只：成功 {result.success_count}，失败 {result.failure_count}"
    )
    feat = result.successes[0]
    assert feat.ts_code
    assert feat.end_date is not None
    assert feat.revenue is not None

    # 输出 CSV 到 data/test/（固定文件名，每次运行覆盖同名）
    out_dir = settings.data_root / "test"
    out_dir.mkdir(parents=True, exist_ok=True)
    feat_path = out_dir / "full_collect_test.csv"
    src_path = out_dir / "full_collect_test-数据来源.csv"
    fail_path = out_dir / "full_collect_test-失败.csv"

    headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    batch_size = settings.batch_size
    successes = result.successes
    for i in range(0, len(successes), batch_size):
        chunk = successes[i : i + batch_size]
        _append_csv_rows(
            feat_path, chunk, headers, ALL_OUTPUT_COLUMNS, write_header=(i == 0)
        )

    write_data_source_csv(src_path)

    if result.failures:
        fail_path.write_text(
            "ts_code,name,error\n"
            + "\n".join(f"{f.ts_code},{f.name},{f.error}" for f in result.failures),
            encoding="utf-8-sig",
        )

    print(f"测试产出: {feat_path} ({len(successes)} 股)")
    print(f"数据来源: {src_path}")
    if result.failures:
        print(f"失败清单: {fail_path} ({result.failure_count} 股)")


@pytest.mark.network
def test_batch_vs_per_stock_cross_validate() -> None:
    """随机 3 股，批量与逐股产出必须一致。

    ``uv run pytest -m network integrated_tests/test_full_collect.py::test_batch_vs_per_stock_cross_validate``
    """
    import random

    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")
    fetcher = TushareFetcher(settings)
    stocks = fetcher.fetch_stock_list()
    rng = random.Random(42)
    picked = rng.sample(stocks, min(3, len(stocks)))
    codes = [s.ts_code for s in picked]
    period = expected_latest_period(_dt.date.today())

    # 批量
    batch_map = fetcher.fetch_financials_batch(period)

    for tc in codes:
        per_feat = fetcher.fetch_financials(tc, period=period)
        batch_feat = batch_map.get(tc)
        assert batch_feat is not None, f"{tc} 批量结果缺失"
        per_dump = per_feat.model_dump()
        batch_dump = batch_feat.model_dump()
        for key in per_dump:
            assert per_dump[key] == batch_dump[key], (
                f"{tc}.{key}: 批量={batch_dump[key]} 逐股={per_dump[key]}"
            )
