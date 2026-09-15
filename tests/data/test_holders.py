"""股东户数采集：分页合并、单股取最新期末、缺失置空、接口异常不拖垮整批。"""

from __future__ import annotations

import pytest

from src.data.contract import StockFeatures
from src.data.holders import (
    HOLDER_PAGE_LIMIT,
    fetch_holder_number,
    fetch_holder_numbers,
    holder_page_size,
    merge_holder_numbers,
)


class _FakeHolderApi:
    def __init__(self) -> None:
        self.pages: list[list[dict]] = []
        self.calls: list[tuple[str, dict]] = []
        self.single: list[dict] = []
        self.raise_paginated = False
        self.raise_single = False

    def _call_paginated(self, interface_key: str, page_size: int, **params: object) -> list[dict]:
        self.calls.append((interface_key, {"page_size": page_size, **params}))
        if self.raise_paginated:
            raise RuntimeError("holder page boom")
        out: list[dict] = []
        for page in self.pages:
            out.extend(page)
        return out

    def _call(self, interface_key: str, fields: tuple[str, ...] | None = None, **params: object) -> list[dict]:
        self.calls.append((interface_key, dict(params)))
        if self.raise_single:
            raise RuntimeError("holder one boom")
        return list(self.single)


def test_holder_page_size_caps_at_3000() -> None:
    assert holder_page_size(5000) == HOLDER_PAGE_LIMIT
    assert holder_page_size(600) == 600
    assert HOLDER_PAGE_LIMIT == 3000


def test_fetch_holder_numbers_paginated_keeps_latest_end_date() -> None:
    api = _FakeHolderApi()
    api.pages = [
        [
            {"ts_code": "600000.SH", "end_date": "20240930", "holder_num": 100},
            {"ts_code": "000001.SZ", "end_date": "20241231", "holder_num": 200},
        ],
        [
            {"ts_code": "600000.SH", "end_date": "20241231", "holder_num": 25135},
        ],
    ]
    got = fetch_holder_numbers(api, "20241231", page_size=5000)
    assert api.calls[0][0] == "stk_holdernumber"
    assert api.calls[0][1]["enddate"] == "20241231"
    assert api.calls[0][1]["page_size"] == 3000
    assert got == {"600000.SH": 25135, "000001.SZ": 200}


def test_fetch_holder_numbers_skips_missing_and_invalid() -> None:
    api = _FakeHolderApi()
    api.pages = [
        [
            {"ts_code": "", "end_date": "20241231", "holder_num": 1},
            {"ts_code": "600000.SH", "end_date": "20241231", "holder_num": None},
            {"ts_code": "000001.SZ", "end_date": "20241231", "holder_num": "bad"},
            {"ts_code": "000002.SZ", "end_date": "20241231", "holder_num": "888"},
        ]
    ]
    assert fetch_holder_numbers(api, "20241231", page_size=600) == {"000002.SZ": 888}


def test_fetch_holder_number_explicit_period() -> None:
    api = _FakeHolderApi()
    api.single = [
        {"ts_code": "600000.SH", "end_date": "20240630", "holder_num": 10},
        {"ts_code": "600000.SH", "end_date": "20241231", "holder_num": 20},
    ]
    assert fetch_holder_number(api, "600000.SH", "20241231") == 20
    assert api.calls[0][1]["ts_code"] == "600000.SH"
    assert api.calls[0][1]["enddate"] == "20241231"


def test_fetch_holder_number_latest_when_period_none() -> None:
    api = _FakeHolderApi()
    api.single = [
        {"ts_code": "600000.SH", "end_date": "20240630", "holder_num": 10},
        {"ts_code": "600000.SH", "end_date": "20240930", "holder_num": 30},
    ]
    assert fetch_holder_number(api, "600000.SH", None) == 30
    assert "enddate" not in api.calls[0][1]


def test_fetch_holder_number_missing_returns_none() -> None:
    api = _FakeHolderApi()
    api.single = []
    assert fetch_holder_number(api, "600000.SH", "20241231") is None


def test_merge_holder_numbers_sets_known_leaves_unknown() -> None:
    features = {
        "600000.SH": StockFeatures(ts_code="600000.SH"),
        "000001.SZ": StockFeatures(ts_code="000001.SZ"),
    }
    merge_holder_numbers(features, {"600000.SH": 25135})
    assert features["600000.SH"].holder_num == 25135
    assert features["000001.SZ"].holder_num is None


def test_fetch_holder_numbers_propagates_api_error() -> None:
    api = _FakeHolderApi()
    api.raise_paginated = True
    with pytest.raises(RuntimeError, match="holder page boom"):
        fetch_holder_numbers(api, "20241231", page_size=600)
