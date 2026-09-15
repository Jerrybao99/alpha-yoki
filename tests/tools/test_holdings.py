"""holdings add/list/remove：幂等与删除不存在退出 4。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.tools import EXIT_DATA, EXIT_OK, ToolError
from src.tools.holdings import HoldingsParams, holdings_path, run_holdings


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path))


def test_holdings_add_list_remove_roundtrip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    code, payload = run_holdings(HoldingsParams(action="add", ts_code="600519.SH", name="贵州茅台"), settings)
    assert code == EXIT_OK
    assert payload["data"]["items"] == [{"ts_code": "600519.SH", "name": "贵州茅台"}]
    again, payload2 = run_holdings(HoldingsParams(action="add", ts_code="600519.SH", name="贵州茅台"), settings)
    assert again == EXIT_OK
    assert payload2["data"]["items"] == payload["data"]["items"]
    listed = run_holdings(HoldingsParams(action="list"), settings)[1]
    assert listed["data"]["items"] == payload["data"]["items"]
    removed, payload3 = run_holdings(HoldingsParams(action="remove", ts_code="600519.SH"), settings)
    assert removed == EXIT_OK
    assert payload3["data"]["items"] == []
    assert holdings_path(settings).exists()


def test_holdings_remove_missing_is_data_error(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as exc:
        run_holdings(HoldingsParams(action="remove", ts_code="600000.SH"), _settings(tmp_path))
    assert exc.value.code == EXIT_DATA
