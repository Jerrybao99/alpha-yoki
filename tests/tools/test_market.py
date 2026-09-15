"""collect / scores / screen 工具契约。"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from src.config import Settings
from src.data.collect import CollectionResult, expected_latest_period
from src.data.contract import StockFeatures
from src.data.store import Kind, latest, raw_path, write_raw_csv
from src.tools import EXIT_OK
from src.tools.market import CollectParams, ScoresParams, ScreenParams, run_collect, run_market_scores, run_screen


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path), tushare_token="t")


class _FakePipe:
    def __init__(self, *_args, **_kwargs) -> None:
        self.calls: list[str] = []

    def run_batch(self, period=None):
        self.calls.append(f"batch:{period}")
        result = CollectionResult(total=1)
        result.successes.append(StockFeatures(ts_code="600000.SH", name="浦发", end_date=period, revenue=1.0))
        return result

    def run(self, period=None, codes=None):
        self.calls.append(f"run:{period}:{list(codes or [])}")
        result = CollectionResult(total=len(codes or []))
        for code in codes or []:
            result.successes.append(StockFeatures(ts_code=code, name="续", end_date=period, revenue=2.0))
        return result

    def close(self) -> None:
        return None


def test_collect_update_skips_when_fresh(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    today = _dt.date(2026, 9, 15)
    expected = expected_latest_period(today)
    collect = settings.data_path("fin") / "full_collect"
    collect.mkdir(parents=True)
    (collect / "260915.csv").write_text("ts_code\n", encoding="utf-8")
    write_raw_csv(
        [{"ts_code": "600000.SH", "end_date": expected}],
        raw_path(collect, "260915"),
        ("ts_code", "end_date"),
    )
    pipe = _FakePipe()
    code, payload = run_collect(
        CollectParams(update=True),
        settings,
        pipeline_factory=lambda *_a, **_k: pipe,
        today=today,
    )
    assert code == EXIT_OK
    assert payload["data"]["skipped"] is True
    assert pipe.calls == []


def test_collect_force_runs_batch(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("src.tools.market.TushareFetcher", lambda _settings: object())
    pipe = _FakePipe()
    code, payload = run_collect(
        CollectParams(force=True),
        settings,
        pipeline_factory=lambda *_a, **_k: pipe,
        today=_dt.date(2026, 9, 15),
    )
    assert code == EXIT_OK
    assert payload["data"]["skipped"] is False
    assert pipe.calls[0].startswith("batch:")
    assert Path(payload["data"]["path"]).name == "260915.csv"


def test_collect_codes_writes_single_stock_csv(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("src.tools.market.TushareFetcher", lambda _settings: object())
    pipe = _FakePipe()
    code, payload = run_collect(
        CollectParams(codes=["600519.SH"]),
        settings,
        pipeline_factory=lambda *_a, **_k: pipe,
        today=_dt.date(2026, 9, 15),
    )
    assert code == EXIT_OK
    assert Path(payload["data"]["path"]).name == "260915-单股.csv"
    assert "run:" in pipe.calls[0]


def test_collect_resume_skips_existing_and_merges(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.data.contract import StockInfo

    settings = _settings(tmp_path)
    today = _dt.date(2026, 9, 15)
    collect = settings.data_path("fin") / "full_collect"
    collect.mkdir(parents=True)
    (collect / "260915.csv").write_text("股票代码,股票名称\n600000.SH,浦发\n", encoding="utf-8-sig")
    write_raw_csv(
        [{"ts_code": "600000.SH", "name": "浦发", "end_date": "20260630", "revenue": 1.0}],
        raw_path(collect, "260915"),
        ("ts_code", "name", "end_date", "revenue"),
    )

    class _Fetcher:
        def fetch_stock_list(self):
            return [
                StockInfo(ts_code="600000.SH", name="浦发"),
                StockInfo(ts_code="600519.SH", name="茅台"),
            ]

    monkeypatch.setattr("src.tools.market.TushareFetcher", lambda _settings: _Fetcher())
    pipe = _FakePipe()
    code, payload = run_collect(
        CollectParams(resume=True),
        settings,
        pipeline_factory=lambda *_a, **_k: pipe,
        today=today,
    )
    assert code == EXIT_OK
    assert payload["data"]["skipped"] is False
    assert pipe.calls == [f"run:{expected_latest_period(today)}:['600519.SH']"]
    merged = (collect / "260915-raw.csv").read_text(encoding="utf-8")
    assert "600000.SH" in merged
    assert "600519.SH" in merged


def test_collect_resume_without_file_is_data_error(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("src.tools.market.TushareFetcher", lambda _settings: object())
    pipe = _FakePipe()
    from src.tools import EXIT_DATA, ToolError

    try:
        run_collect(
            CollectParams(resume=True),
            settings,
            pipeline_factory=lambda *_a, **_k: pipe,
            today=_dt.date(2026, 9, 15),
        )
    except ToolError as exc:
        assert exc.code == EXIT_DATA
        assert "可续" in str(exc)
    else:
        raise AssertionError("expected ToolError")
    assert pipe.calls == []


def test_scores_reads_raw_and_writes_scores(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    collect = settings.data_path("fin") / "full_collect"
    collect.mkdir(parents=True)
    (collect / "260915.csv").write_text("ts_code\n", encoding="utf-8")
    write_raw_csv(
        [
            {
                "ts_code": "600519.SH",
                "name": "贵州茅台",
                "industry": "大消费",
                "end_date": "20260630",
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
        ],
        raw_path(collect, "260915"),
        (
            "ts_code",
            "name",
            "industry",
            "end_date",
            "or_yoy",
            "netprofit_yoy",
            "grossprofit_margin",
            "ocfps",
            "eps",
            "debt_to_assets",
            "current_ratio",
            "inv_turn",
            "roe",
            "free_cashflow",
            "total_assets",
            "revenue",
            "n_income_attr_p",
            "money_cap",
        ),
    )
    code, payload = run_market_scores(ScoresParams(), settings)
    assert code == EXIT_OK
    assert payload["data"]["passed"] == 1
    assert latest(Kind.SCORES, settings).name == "260915.csv"
    assert raw_path(settings.data_path("fin") / "full_scores", "260915").exists()


def test_screen_filters_industry_and_rating(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    scores = settings.data_path("fin") / "full_scores"
    scores.mkdir(parents=True)
    (scores / "260915.csv").write_text("ts_code\n", encoding="utf-8")
    write_raw_csv(
        [
            {"ts_code": "600519.SH", "industry": "大消费", "评级": "👑 皇冠明珠", "综合分": 9.0},
            {"ts_code": "600000.SH", "industry": "证券金融", "评级": "⭐ 优秀白马", "综合分": 7.4},
        ],
        raw_path(scores, "260915"),
        ("ts_code", "industry", "评级", "综合分"),
    )
    code, payload = run_screen(ScreenParams(industry="大消费", rating="皇冠"), settings)
    assert code == EXIT_OK
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["ts_code"] == "600519.SH"
