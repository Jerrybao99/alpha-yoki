"""Step 2.4 评分评级串联集成测试。mock 数据源验证评分列追加、否决剔除、CSV 产物。
network 测试使用全量采集数据真实评分。CI 可通过 ``-m 'not network'`` 跳过 network。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.full_scores import (
    SCORING_HEADERS,
    _write_scoring_csv,
    _write_veto_csv,
    run_scores,
)
from src.config import Settings
from src.data.contract import ALL_OUTPUT_COLUMNS, StockFeatures
from src.data.output import FIELD_CN


def _feat(ts_code: str, **kw) -> StockFeatures:
    defaults: dict = {
        "ts_code": ts_code,
        "symbol": ts_code.split(".")[0],
        "name": ts_code,
        "industry": "大消费",
        "end_date": "20241231",
        "or_yoy": 30.0,
        "netprofit_yoy": 40.0,
        "grossprofit_margin": 35.0,
        "ocfps": 2.0,
        "eps": 1.0,
        "debt_to_assets": 50.0,
        "current_ratio": 1.8,
        "inv_turn": 6.0,
        "roe": 18.0,
        "free_cashflow": 5.0e8,
        "total_assets": 1.0e10,
        "revenue": 1.5e10,
        "n_income_attr_p": 3.4e9,
        "money_cap": 2e9,
    }
    defaults.update(kw)
    return StockFeatures(**defaults)


def _settings(data_dir: Path) -> Settings:
    return Settings(tushare_token="t", data_dir=str(data_dir), concurrency=2)


def test_run_scores_appends_columns() -> None:
    """评分结果追加成长性/稳健性/资金回报/综合分/评级五列。"""
    features = [_feat("600000.SH")]
    results, vetoes = run_scores(features)
    assert len(results) == 1
    assert len(vetoes) == 0
    row = results[0]
    assert row["成长性"] == 8
    assert row["稳健性"] == 8
    assert row["资金回报"] == 8
    assert row["综合分"] == 8.0  # 8×0.30+8×0.30+8×0.40
    assert "优秀白马" in row["评级"]


def test_run_scores_veto_excluded() -> None:
    """触发一票否决的股票不进 results，记入 vetoes。"""
    features = [
        _feat("600000.SH"),
        _feat("000001.SZ", money_cap=3e10, total_assets=5e10),
    ]
    results, vetoes = run_scores(features)
    assert len(results) == 1
    assert results[0]["ts_code"] == "600000.SH"
    assert len(vetoes) == 1
    assert vetoes[0]["ts_code"] == "000001.SZ"
    assert "造假嫌疑" in vetoes[0]["否决项"]


def test_run_scores_industry_weights_applied() -> None:
    """不同行业使用不同的权重。"""
    f1 = _feat("600000.SH", industry="科技/制造")
    f2 = _feat("000001.SZ", industry="公用事业/基建")
    results, _ = run_scores([f1, f2])
    # 科技/制造: 8×0.50+8×0.20+8×0.30=8.0
    assert results[0]["综合分"] == 8.0
    # 公用事业/基建: 8×0.20+8×0.40+8×0.40=8.0
    assert results[1]["综合分"] == 8.0


def test_run_scores_rating_boundary() -> None:
    """评级边界值归属正确。"""
    features = [
        _feat(
            "A.SH",
            or_yoy=1000,
            netprofit_yoy=1000,
            grossprofit_margin=100,
            ocfps=100,
            eps=1,
            debt_to_assets=10,
            current_ratio=100,
            inv_turn=999,
            roe=100,
            free_cashflow=1e12,
            total_assets=1e10,
        ),
        _feat(
            "B.SH",
            or_yoy=-100,
            netprofit_yoy=-100,
            grossprofit_margin=0,
            ocfps=0.1,
            eps=1,
            debt_to_assets=99,
            current_ratio=0.1,
            inv_turn=0.1,
            roe=-100,
            free_cashflow=-1e12,
            total_assets=1e10,
        ),
    ]
    results, _ = run_scores(features)
    assert "皇冠明珠" in results[0]["评级"]
    assert "垃圾" in results[1]["评级"]


def test_write_scoring_csv_output(tmp_path: Path) -> None:
    """产物 CSV 含原始列 + SCORING_HEADERS。"""
    features = [_feat("600000.SH")]
    results, _ = run_scores(features)
    out = tmp_path / "scoring" / "260724.csv"
    _write_scoring_csv(out, results, ALL_OUTPUT_COLUMNS)
    assert out.exists()
    text = out.read_text(encoding="utf-8-sig")
    header = text.strip().split("\n")[0].split(",")
    for h in SCORING_HEADERS:
        assert h in header, h
    original_headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    for h in original_headers:
        assert h in header, h


def test_write_veto_csv_output(tmp_path: Path) -> None:
    """否决清单 CSV 含 ts_code/name/否决项/原因 列。"""
    vetoes = [{"ts_code": "000001.SZ", "name": "测试", "否决项": "造假嫌疑", "原因": "test"}]
    out = tmp_path / "scoring" / "260724-否决.csv"
    _write_veto_csv(out, vetoes)
    assert out.exists()
    text = out.read_text(encoding="utf-8-sig")
    assert "ts_code" in text
    assert "造假嫌疑" in text


def test_run_scores_empty_no_error() -> None:
    """空列表不报错。"""
    results, vetoes = run_scores([])
    assert results == []
    assert vetoes == []


def test_run_scores_missing_fields_defaults() -> None:
    """缺失评分字段时使用默认容错值。"""
    feat = StockFeatures(ts_code="600000.SH", industry="大消费")
    results, vetoes = run_scores([feat])
    assert len(results) == 1
    assert results[0]["成长性"] == 5  # 全部 None → 5
    assert 0 < results[0]["综合分"] <= 10
    assert results[0]["评级"] is not None


@pytest.mark.network
def test_real_full_scores() -> None:
    """真实全量评分：从 ``data/fin/full_collect/`` 读取最新 CSV 并评分。

    ``uv run pytest -m network integrated_tests/test_full_scores.py::test_real_full_scores``
    """
    from scripts.full_scores import _find_latest, _load_features
    from src.config import get_settings

    settings = get_settings()
    if not settings.tushare_token.strip():
        pytest.skip("未配置 TUSHARE_TOKEN")

    collect_dir = settings.data_path("fin") / "full_collect"
    csv_path = _find_latest(collect_dir)
    if csv_path is None:
        pytest.skip("无 full_collect CSV，请先采集")

    features = _load_features(csv_path)
    assert len(features) >= 5000, f"不足 5000 股：{len(features)}"

    results, vetoes = run_scores(features)
    assert len(results) > 0
    assert len(results) + len(vetoes) == len(features)

    out_dir = settings.data_root / "test" / "full_scores"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "full_scores.csv"
    _write_scoring_csv(out_path, results, ALL_OUTPUT_COLUMNS)
    print(f"测试产出：{out_path} ({len(results)} 股)")

    if vetoes:
        veto_path = out_dir / "full_scores-否决.csv"
        _write_veto_csv(veto_path, vetoes)
        print(f"否决清单：{veto_path} ({len(vetoes)} 股)")
