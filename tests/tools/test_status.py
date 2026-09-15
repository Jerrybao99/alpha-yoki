"""status --check 新鲜/过期退出码与 JSON 键集。"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from src.config import Settings
from src.data.collect import expected_latest_period
from src.data.store import raw_path, write_raw_csv
from src.tools import EXIT_DATA, EXIT_OK
from src.tools.status import StatusParams, run_status


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path))


def test_status_check_missing_is_data_error(tmp_path: Path) -> None:
    code, payload = run_status(StatusParams(check=True), _settings(tmp_path))
    assert code == EXIT_DATA
    assert payload["ok"] is False
    assert payload["command"] == "status"
    assert payload["error"] == "stale_or_missing"
    assert {key for item in payload["data"]["items"] for key in item} >= {
        "kind",
        "path",
        "stamp",
        "period",
        "expected_period",
        "is_stale",
        "reason",
    }


def test_status_check_fresh_collect_still_fails_if_scores_missing(tmp_path: Path) -> None:
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
    code, payload = run_status(StatusParams(check=True), settings, today=today)
    assert code == EXIT_DATA
    kinds = {item["kind"]: item for item in payload["data"]["items"]}
    assert kinds["collect"]["is_stale"] is False
    assert kinds["scores"]["is_stale"] is True


def test_status_without_check_ok_when_missing(tmp_path: Path) -> None:
    code, payload = run_status(StatusParams(check=False), _settings(tmp_path))
    assert code == EXIT_OK
    assert payload["ok"] is True
