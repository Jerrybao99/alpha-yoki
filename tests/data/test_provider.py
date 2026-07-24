"""Tushare 适配器单测。全 mock 验证 token 缺失报错、限流阻塞、指数退避重试、
vip 接口名优先、采集聚合（取最新/NaN→None）。不触网络。
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.config import Settings
from src.data.provider import (
    BACKOFF_BASE_SECONDS,
    RateLimiter,
    TushareApiError,
    TushareFetcher,
    TushareTokenError,
)


# ===== 测试桩 =====
class _FakeDf:
    """模拟 tushare 返回的 DataFrame（只需 to_dict("records")）。"""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def to_dict(self, orient: str) -> list[dict]:
        assert orient == "records"
        return list(self._rows)


class _FakePro:
    """记录所有调用并按 (api_name) 返回脚本化响应；可在指定次数内抛异常。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: dict[str, list[dict]] = {}
        self.fail_times: dict[str, int] = {}  # api_name -> 剩余抛异常次数
        self.error: Exception | None = None  # 全局抛此异常

    def set_response(self, api_name: str, rows: list[dict]) -> None:
        self.responses[api_name] = rows

    def fail_then_ok(self, api_name: str, times: int) -> None:
        self.fail_times[api_name] = times

    def query(self, api_name: str, **params: Any) -> _FakeDf:
        self.calls.append({"api_name": api_name, **params})
        if self.error is not None:
            raise self.error
        if api_name in self.fail_times and self.fail_times[api_name] > 0:
            self.fail_times[api_name] -= 1
            raise RuntimeError(f"transient {api_name}")
        return _FakeDf(self.responses.get(api_name, []))


def _settings(token: str = "test-token", rate: int = 500) -> Settings:
    return Settings(tushare_token=token, tushare_rate_limit=rate)


def _no_sleep(_seconds: float) -> None:
    """测试用空 sleep，避免真实等待。"""


_ALL_APIS = (
    "income_vip",
    "balancesheet_vip",
    "cashflow_vip",
    "fina_indicator_vip",
)


def _set_all_empty(pro: _FakePro, except_: set[str] | None = None) -> None:
    """把除 except_ 外的 4 个接口全部设为空响应（fetch_financials 默认场景）。"""
    for api in _ALL_APIS:
        if api not in (except_ or set()):
            pro.set_response(api, [])


# ===== token 缺失 =====
def test_token_missing_raises() -> None:
    """pro 未注入且 token 为空时，必须明确报错提示配置 .env。"""
    with pytest.raises(TushareTokenError, match="TUSHARE_TOKEN"):
        TushareFetcher(settings=_settings(token=""), pro=None)


def test_token_whitespace_only_raises() -> None:
    with pytest.raises(TushareTokenError):
        TushareFetcher(settings=_settings(token="   "), pro=None)


# ===== RateLimiter =====
def test_rate_limiter_allows_under_limit() -> None:
    slept: list[float] = []
    rl = RateLimiter(
        limit=3, window=60.0, sleep=slept.append, clock=_clock_seq([0, 1, 2])
    )
    for _ in range(3):
        rl.acquire()
    assert slept == []


def test_rate_limiter_blocks_when_exceed() -> None:
    """窗口内第 limit+1 次必须 sleep 到最早一次滑出窗口。"""
    slept: list[float] = []
    # acquire1 取 now=10；acquire2 取 now=20；acquire3 取 now=30 后阻塞，sleep 后再取 now=30
    rl = RateLimiter(
        limit=2, window=60.0, sleep=slept.append, clock=_clock_seq([10, 20, 30, 30])
    )
    rl.acquire()  # t=10
    rl.acquire()  # t=20
    rl.acquire()  # t=30，超额 → sleep(60-(30-10))=40
    assert slept == [40.0]


def _clock_seq(values: list[float]):
    it = iter(values)
    return lambda: next(it)


# ===== 指数退避重试 =====
def test_call_retry_then_success() -> None:
    """前 2 次抛异常，第 3 次成功：sleep 序列为 1s、2s。"""
    pro = _FakePro()
    pro.set_response(
        "stock_basic",
        [{"ts_code": "600000.SH", "symbol": "600000", "name": "浦发银行"}],
    )
    pro.fail_then_ok("stock_basic", 2)
    delays: list[float] = []
    fetcher = TushareFetcher(
        settings=_settings(), pro=pro, sleep=delays.append, max_retries=3
    )
    rows = fetcher._call("stock_basic", ("ts_code", "symbol", "name"), list_status="L")
    assert rows[0]["ts_code"] == "600000.SH"
    assert delays == [BACKOFF_BASE_SECONDS * 1, BACKOFF_BASE_SECONDS * 2]


def test_call_retry_exhausted_raises() -> None:
    """持续失败，重试耗尽抛 TushareApiError，sleep 序列 1/2/4。"""
    pro = _FakePro()
    pro.fail_then_ok("stock_basic", 99)  # 永远失败
    delays: list[float] = []
    fetcher = TushareFetcher(
        settings=_settings(), pro=pro, sleep=delays.append, max_retries=3
    )
    with pytest.raises(TushareApiError, match="stock_basic"):
        fetcher._call("stock_basic", ("ts_code",), list_status="L")
    assert delays == [1.0, 2.0, 4.0]


def test_call_uses_vip_api_name_and_fields() -> None:
    """财务三表/指标走 _vip 接口，常规接口走原名；fields 拼成 CSV、params 透传。"""
    pro = _FakePro()
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    fetcher._call("income", ("ts_code", "revenue"), ts_code="600000.SH")
    fetcher._call("balancesheet", ("ts_code", "total_assets"), ts_code="600000.SH")
    fetcher._call("daily_basic", ("ts_code", "pe_ttm"), ts_code="600000.SH")
    fetcher._call("stock_basic", ("ts_code", "symbol", "name"), list_status="L")
    names = [c["api_name"] for c in pro.calls[:3]]
    assert names == ["income_vip", "balancesheet_vip", "daily_basic"]
    last = pro.calls[-1]
    assert last["fields"] == "ts_code,symbol,name"
    assert last["list_status"] == "L"


def test_call_none_df_returns_empty() -> None:
    class ProNone:
        def query(self, api_name, **params):
            return None

    fetcher = TushareFetcher(settings=_settings(), pro=ProNone(), sleep=_no_sleep)
    assert fetcher._call("stock_basic", ("ts_code",)) == []


# ===== fetch_stock_list =====
def test_fetch_stock_list_maps_rows() -> None:
    pro = _FakePro()
    pro.set_response(
        "stock_basic",
        [
            {
                "ts_code": "600000.SH",
                "symbol": "600000",
                "name": "浦发银行",
                "industry": "银行",
            },
            {
                "ts_code": "000001.SZ",
                "symbol": "000001",
                "name": "平安银行",
                "industry": "银行",
            },
        ],
    )
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    lst = fetcher.fetch_stock_list()
    assert [s.ts_code for s in lst] == ["600000.SH", "000001.SZ"]
    assert lst[0].name == "浦发银行"
    assert lst[1].industry == "银行"


# ===== fetch_financials =====
def test_fetch_financials_picks_latest_and_aggregates() -> None:
    """多接口聚合，财务表按 end_date 取最新，daily_basic 按 trade_date 取最新。"""
    pro = _FakePro()
    # income 返回两期，应取 end_date 更大的 20241231
    pro.set_response(
        "income_vip",
        [
            {
                "ts_code": "600000.SH",
                "end_date": "20240930",
                "revenue": 1.0e10,
                "n_income_attr_p": 1.0e9,
            },
            {
                "ts_code": "600000.SH",
                "end_date": "20241231",
                "revenue": 1.5e10,
                "n_income_attr_p": 2.0e9,
            },
        ],
    )
    pro.set_response(
        "balancesheet_vip",
        [
            {
                "ts_code": "600000.SH",
                "end_date": "20241231",
                "total_assets": 1.0e12,
                "money_cap": 5.0e11,
            }
        ],
    )
    pro.set_response(
        "cashflow_vip",
        [{"ts_code": "600000.SH", "end_date": "20241231", "n_cashflow_act": 3.0e9}],
    )
    pro.set_response(
        "fina_indicator_vip",
        [
            {
                "ts_code": "600000.SH",
                "end_date": "20241231",
                "roe": 12.5,
                "netprofit_yoy": 20.0,
            }
        ],
    )

    feat = TushareFetcher(
        settings=_settings(), pro=pro, sleep=_no_sleep
    ).fetch_financials("600000.SH")
    dumped = feat.model_dump()
    expected = {
        "ts_code": "600000.SH",
        "end_date": "20241231",
        "revenue": 1.5e10,
        "n_income_attr_p": 2.0e9,
        "money_cap": 5.0e11,
        "n_cashflow_act": 3.0e9,
        "roe": 12.5,
        "netprofit_yoy": 20.0,
        "eps": None,
    }
    for k, v in expected.items():
        assert dumped[k] == v, k


def test_fetch_financials_end_date_locked_to_income() -> None:
    """end_date 锁定为 income 报告期，不被其他接口的 end_date 覆盖。"""
    pro = _FakePro()
    pro.set_response(
        "income_vip",
        [{"ts_code": "600000.SH", "end_date": "20260331", "revenue": 1.0e10}],
    )
    pro.set_response(
        "balancesheet_vip",
        [{"ts_code": "600000.SH", "end_date": "20260331", "total_assets": 1.0e12}],
    )
    pro.set_response(
        "cashflow_vip",
        [{"ts_code": "600000.SH", "end_date": "20260331", "n_cashflow_act": 3.0e9}],
    )
    pro.set_response(
        "fina_indicator_vip",
        [{"ts_code": "600000.SH", "end_date": "20260331", "roe": 12.5}],
    )
    feat = TushareFetcher(
        settings=_settings(), pro=pro, sleep=_no_sleep
    ).fetch_financials("600000.SH")
    assert feat.end_date == "20260331"


def test_fetch_financials_nan_normalized_to_none() -> None:
    """Tushare 可能返回 NaN，应归一化为 None 以匹配 StockFeatures(float|None)。"""
    pro = _FakePro()
    pro.set_response(
        "income_vip",
        [{"ts_code": "600000.SH", "end_date": "20241231", "revenue": math.nan}],
    )
    _set_all_empty(pro, except_={"income_vip"})
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    assert fetcher.fetch_financials("600000.SH").revenue is None


def test_fetch_financials_passes_period_param() -> None:
    """period 非空时透传给财务三表/指标（vip 接口按报告期取）。"""
    pro = _FakePro()
    _set_all_empty(pro)
    TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep).fetch_financials(
        "600000.SH", period="20241231"
    )
    by_api = {c["api_name"]: c for c in pro.calls}
    assert by_api["income_vip"]["period"] == "20241231"
    assert by_api["fina_indicator_vip"]["period"] == "20241231"


def test_fetch_financials_calls_all_4_interfaces() -> None:
    """fetch_financials 必须覆盖 4 个 vip 财务接口。"""
    pro = _FakePro()
    _set_all_empty(pro)
    TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep).fetch_financials(
        "600000.SH"
    )
    names = [c["api_name"] for c in pro.calls]
    assert set(names) == set(_ALL_APIS)
    assert len(names) == 4


def test_fetch_financials_no_date_falls_back_to_first() -> None:
    """记录无 date_field 时回退取首条，不报错。"""
    pro = _FakePro()
    pro.set_response("income_vip", [{"ts_code": "600000.SH", "revenue": 1.0e10}])
    _set_all_empty(pro, except_={"income_vip"})
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    assert fetcher.fetch_financials("600000.SH").revenue == 1.0e10
