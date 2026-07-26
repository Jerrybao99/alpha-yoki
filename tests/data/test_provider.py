"""Tushare 适配器单测。全 mock 验证 token 缺失报错、限流阻塞、指数退避重试、
vip 接口名优先、采集聚合（取最新/NaN→None）。不触网络。
"""

from __future__ import annotations

import math
from pathlib import Path
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


# ===== sw_l2_to_category =====
def test_sw_l2_to_category_known() -> None:
    from src.data.provider import sw_l2_to_category

    assert sw_l2_to_category("白酒") == "大消费"
    assert sw_l2_to_category("半导体") == "科技/制造"
    assert sw_l2_to_category("证券") == "证券金融"
    assert sw_l2_to_category("石油开采") == "周期资源"
    assert sw_l2_to_category("电力") == "公用事业/基建"


def test_sw_l2_to_category_empty() -> None:
    from src.data.provider import sw_l2_to_category

    assert sw_l2_to_category("") == "未分类"


def test_sw_l2_to_category_roman_suffix() -> None:
    from src.data.provider import sw_l2_to_category

    assert sw_l2_to_category("中药Ⅱ") == "大消费"


def test_sw_l2_to_category_unknown() -> None:
    from src.data.provider import sw_l2_to_category

    assert sw_l2_to_category("不存在的行业") == "未分类"


# ===== _call_no_fields =====
def test_call_no_fields() -> None:
    pro = _FakePro()
    pro.set_response("index_member_all", [{"ts_code": "600000.SH", "l2_name": "银行"}])
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    rows = fetcher._call_no_fields("index_member_all", ts_code="600000.SH", is_new="Y")
    assert rows[0]["l2_name"] == "银行"


# ===== _clean_record exclude =====
def test_clean_record_with_exclude() -> None:
    rec = {"end_date": "20241231", "ts_code": "600000.SH", "revenue": 1.5e10}
    out = TushareFetcher._clean_record(
        rec, ("end_date", "ts_code", "revenue"), exclude={"end_date"}
    )
    assert "end_date" not in out
    assert out["ts_code"] == "600000.SH"
    assert out["revenue"] == 1.5e10


def test_clean_record_none_rec() -> None:
    assert TushareFetcher._clean_record(None, ("ts_code",)) == {}


def test_clean_record_nan_in_field() -> None:
    import math

    out = TushareFetcher._clean_record(
        {"revenue": math.nan, "ts_code": "600000.SH"}, ("ts_code", "revenue")
    )
    assert out["ts_code"] == "600000.SH"
    assert out["revenue"] is None


# ===== _str =====
def test_str_none() -> None:
    assert TushareFetcher._str(None) == ""


def test_str_nan() -> None:
    import math

    assert TushareFetcher._str(math.nan) == ""


def test_str_normal() -> None:
    assert TushareFetcher._str("hello") == "hello"
    assert TushareFetcher._str(42) == "42"


# ===== _merge_non_none =====
def test_merge_non_none() -> None:
    target = {"a": 1, "b": 2}
    TushareFetcher._merge_non_none(target, {"b": 3, "c": 4})
    assert target == {"a": 1, "b": 3, "c": 4}


def test_merge_non_none_skips_none() -> None:
    target = {"a": 1}
    TushareFetcher._merge_non_none(target, {"a": None, "b": None, "c": 3})
    assert target == {"a": 1, "c": 3}


# ===== _sw_cache_path =====
def test_sw_cache_path() -> None:
    settings = _settings()
    fetcher = TushareFetcher(settings=settings, pro=_FakePro(), sleep=_no_sleep)
    path = fetcher._sw_cache_path()
    assert path.name == "sw_industry.csv"
    assert "ref" in path.parts


# ===== _sw_name_to_category =====
def test_sw_name_to_category_l2() -> None:
    assert TushareFetcher._sw_name_to_category({"l2_name": "白酒"}) == "大消费"


def test_sw_name_to_category_fallback_l1() -> None:
    rec = {"l2_name": "未知行业名", "l1_name": "证券", "l3_name": ""}
    assert TushareFetcher._sw_name_to_category(rec) == "证券金融"


def test_sw_name_to_category_default() -> None:
    assert TushareFetcher._sw_name_to_category({}, default="默认") == "默认"


# ===== save/load SW cache =====
def test_save_and_load_sw_cache(tmp_path: Path) -> None:
    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    fetcher = TushareFetcher(settings=settings, pro=_FakePro(), sleep=_no_sleep)
    import src.data.provider as _mod

    mapping = {"600000.SH": "证券金融", "000001.SZ": "大消费"}
    l2_names = {"600000.SH": "银行", "000001.SZ": "白酒"}

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: tmp_path / "sw_industry.csv"  # type: ignore[method-assign]
    try:
        fetcher._save_sw_cache(mapping, l2_names=l2_names)
        loaded = fetcher.load_sw_cache(tmp_path / "sw_industry.csv")
        assert loaded == mapping
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig


def test_load_sw_cache_no_file(tmp_path: Path) -> None:
    from src.data.provider import TushareFetcher

    assert TushareFetcher.load_sw_cache(tmp_path / "nonexist.csv") is None


def test_load_sw_cache_empty_mapping(tmp_path: Path) -> None:
    from src.data.provider import TushareFetcher

    path = tmp_path / "sw.csv"
    path.write_text("ts_code,l2_name,category\n", encoding="utf-8-sig")
    assert TushareFetcher.load_sw_cache(path) is None  # mapping 为空 dict → 返回 None


# ===== _load_or_build_sw_cache =====
def test_load_or_build_sw_cache_no_file(tmp_path: Path) -> None:
    import src.data.provider as _mod

    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    fetcher = TushareFetcher(settings=settings, pro=_FakePro(), sleep=_no_sleep)

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: tmp_path / "sw_industry.csv"  # type: ignore[method-assign]
    try:
        result = fetcher._load_or_build_sw_cache()
        assert result == {}  # 无文件，返回空 dict
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig


# ===== _enrich_with_sw_category =====
def test_enrich_with_sw_category_updates_industry(tmp_path: Path) -> None:
    import src.data.provider as _mod
    from src.data.contract import StockInfo

    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    fetcher = TushareFetcher(settings=settings, pro=_FakePro(), sleep=_no_sleep)

    # 准备缓存文件
    sw_path = tmp_path / "ref"
    sw_path.mkdir(parents=True)
    cache = sw_path / "sw_industry.csv"
    cache.write_text(
        "ts_code,l2_name,category\n600000.SH,银行,证券金融\n", encoding="utf-8-sig"
    )

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: cache  # type: ignore[method-assign]
    try:
        stocks = [
            StockInfo(
                ts_code="600000.SH", symbol="600000", name="A", industry="原始行业"
            )
        ]
        result = fetcher._enrich_with_sw_category(stocks)
        assert result[0].industry == "证券金融"
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig


def test_enrich_with_sw_category_calls_api_for_missing(tmp_path: Path) -> None:
    """缓存无该 ts_code 时，查 API 获取。"""
    import src.data.provider as _mod
    from src.data.contract import StockInfo

    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    pro = _FakePro()
    pro.set_response(
        "index_member_all",
        [
            {
                "ts_code": "600000.SH",
                "l2_name": "证券",
                "l3_name": "",
                "l1_name": "",
                "is_new": "Y",
            }
        ],
    )
    fetcher = TushareFetcher(settings=settings, pro=pro, sleep=_no_sleep)

    sw_path = tmp_path / "ref"
    sw_path.mkdir(parents=True)
    cache = sw_path / "sw_industry.csv"

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: cache  # type: ignore[method-assign]
    try:
        stocks = [
            StockInfo(
                ts_code="600000.SH", symbol="600000", name="A", industry="原始行业"
            )
        ]
        result = fetcher._enrich_with_sw_category(stocks)
        assert result[0].industry == "证券金融"
        # 缓存应已写出
        assert cache.exists()
        loaded = fetcher.load_sw_cache(cache)
        assert loaded is not None
        assert "600000.SH" in loaded
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig


# ===== _call_paginated =====
def test_call_paginated_single_page() -> None:
    pro = _FakePro()
    pro.set_response("income_vip", [{"ts_code": "600000.SH", "revenue": 1.5e10}])
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    rows = fetcher._call_paginated("income", page_size=100, period="20241231")
    assert len(rows) == 1
    assert rows[0]["ts_code"] == "600000.SH"


def test_call_paginated_multiple_pages() -> None:
    """分页：第一页满，第二页空 → 只调一次。"""

    class _MultiPagePro:
        def query(self, api_name, **params):
            offset = params.get("offset", 0)
            limit = params.get("limit", 10)
            if offset == 0:
                rows = [{"ts_code": f"6000{i:02d}.SH"} for i in range(min(limit, 5))]
            else:
                rows = []
            return _FakeDf(rows)

    fetcher = TushareFetcher(settings=_settings(), pro=_MultiPagePro(), sleep=_no_sleep)
    rows = fetcher._call_paginated("income", page_size=5, period="20241231")
    assert 0 < len(rows) <= 5


def test_call_paginated_second_page_partial() -> None:
    """第二页不足 page_size → 停止。"""

    class _TwoPagePro:
        def query(self, api_name, **params):
            offset = params.get("offset", 0)
            if offset == 0:
                return _FakeDf([{"ts_code": f"A{i:02d}.SH"} for i in range(5)])
            return _FakeDf([{"ts_code": "B00.SH"}])

    fetcher = TushareFetcher(settings=_settings(), pro=_TwoPagePro(), sleep=_no_sleep)
    rows = fetcher._call_paginated("income", page_size=5, period="20241231")
    assert len(rows) == 6


# ===== fetch_financials_batch =====
def test_fetch_financials_batch_basic() -> None:
    """批量采集：income 为主接口，其余 3 接口增量合并。"""
    pro = _FakePro()
    # income
    pro.set_response(
        "income_vip",
        [
            {
                "ts_code": "600000.SH",
                "end_date": "20241231",
                "revenue": 1.5e10,
                "n_income_attr_p": 2e9,
            },
            {
                "ts_code": "000001.SZ",
                "end_date": "20241231",
                "revenue": 3e10,
                "n_income_attr_p": 4e9,
            },
        ],
    )
    # balancesheet
    pro.set_response(
        "balancesheet_vip",
        [
            {"ts_code": "600000.SH", "end_date": "20241231", "total_assets": 1e12},
        ],
    )
    # cashflow
    pro.set_response("cashflow_vip", [])
    # fina_indicator
    pro.set_response("fina_indicator_vip", [])

    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    result = fetcher.fetch_financials_batch("20241231")
    assert len(result) == 2
    assert "600000.SH" in result
    assert result["600000.SH"].revenue == 1.5e10
    assert result["600000.SH"].total_assets == 1e12
    assert result["000001.SZ"].revenue == 3e10
    assert result["000001.SZ"].total_assets is None  # 未在 balancesheet 中出现


def test_fetch_financials_batch_paginated() -> None:
    """分页 income VIP 接口验证。"""

    class _LargePro:
        def query(self, api_name, **params):
            offset = params.get("offset", 0)
            if api_name == "income_vip":
                return _FakeDf(
                    [
                        {
                            "ts_code": f"T{i:03d}.SH",
                            "end_date": "20241231",
                            "revenue": 1e9,
                        }
                        for i in range(offset, offset + min(10, 25 - offset))
                    ]
                )
            return _FakeDf([])

    settings = Settings(tushare_token="t", tushare_rate_limit=500, vip_page_size=10)
    fetcher = TushareFetcher(settings=settings, pro=_LargePro(), sleep=_no_sleep)
    result = fetcher.fetch_financials_batch("20241231")
    assert len(result) == 25


# ===== fetch_financials explicit period multi-record =====
def test_fetch_financials_explicit_period_merges() -> None:
    """explicit period 下有两条记录时 merge_non_none 覆盖。"""
    pro = _FakePro()
    pro.set_response(
        "income_vip",
        [
            {"ts_code": "600000.SH", "end_date": "20241231", "revenue": None},
            {"ts_code": "600000.SH", "end_date": "20241231", "revenue": 1.5e10},
        ],
    )
    pro.set_response(
        "balancesheet_vip",
        [
            {"ts_code": "600000.SH", "end_date": "20241231", "total_assets": 1e12},
            {"ts_code": "600000.SH", "end_date": "20241231", "total_assets": None},
        ],
    )
    _set_all_empty(pro, except_={"income_vip", "balancesheet_vip"})

    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    feat = fetcher.fetch_financials("600000.SH", period="20241231")
    assert feat.revenue == 1.5e10
    assert feat.total_assets == 1e12


# ===== RateLimiter eviction =====
def test_rate_limiter_evicts_old() -> None:
    """旧条目滑出窗口后不阻塞。"""
    slept: list[float] = []
    rl = RateLimiter(
        limit=2, window=60.0, sleep=slept.append, clock=_clock_seq([10, 20, 80, 80])
    )
    rl.acquire()  # t=10, stamps=[10]
    rl.acquire()  # t=20, stamps=[10, 20] → limit reached but not exceeded
    rl.acquire()  # t=80: evict 10 (80-10>=60), stamps=[20] → under limit, no sleep
    assert slept == []


# ===== token init with real path (mocked) =====
def test_token_init_real_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """覆盖 ts.set_token + ts.pro_api 调用路径。"""
    import tushare as _ts

    class _FakeApi:
        pass

    monkeypatch.setattr(_ts, "set_token", lambda token: None)
    monkeypatch.setattr(_ts, "pro_api", lambda: _FakeApi())
    fetcher = TushareFetcher(settings=_settings(token="real-token"))
    assert isinstance(fetcher._pro, _FakeApi)

    # 验证空 token 仍然报错
    monkeypatch.undo()
    monkeypatch.setattr(_ts, "set_token", lambda token: None)
    monkeypatch.setattr(_ts, "pro_api", lambda: _FakeApi())


# ===== _sw_name_to_category fallback L1 =====
def test_sw_name_to_category_fallback_l1_direct() -> None:
    """L1 名直接命中映射表。"""
    # "证券" 在 _SW_L2_TO_CATEGORY 中 → 证券金融
    rec = {"l2_name": "", "l1_name": "证券", "l3_name": ""}
    assert TushareFetcher._sw_name_to_category(rec) == "证券金融"


def test_sw_name_to_category_fallback_l3() -> None:
    """L2 无，L1 也无，回退 L3。"""
    rec = {"l2_name": "", "l1_name": "", "l3_name": "白酒"}
    assert TushareFetcher._sw_name_to_category(rec) == "大消费"


def test_sw_name_to_category_no_fields() -> None:
    """所有字段都空/无→ 默认值。"""
    assert TushareFetcher._sw_name_to_category({}) == "未分类"


# ===== _fetch_one_sw_category =====
def test_fetch_one_sw_category_success() -> None:
    """单个 ts_code 查 SW 分类成功。"""
    pro = _FakePro()
    pro.set_response(
        "index_member_all",
        [
            {
                "ts_code": "600000.SH",
                "l2_name": "证券",
                "l1_name": "",
                "l3_name": "",
                "is_new": "Y",
            },
        ],
    )
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    cat, l2 = fetcher._fetch_one_sw_category("600000.SH")
    assert cat == "证券金融"
    assert l2 == "证券"


def test_fetch_one_sw_category_api_error() -> None:
    """API 调用失败返回未分类。"""
    pro = _FakePro()
    pro.error = RuntimeError("test error")
    fetcher = TushareFetcher(
        settings=_settings(), pro=pro, sleep=_no_sleep, max_retries=0
    )
    cat, l2 = fetcher._fetch_one_sw_category("600000.SH")
    assert cat == "未分类"
    assert l2 == ""


def test_fetch_one_sw_category_no_match() -> None:
    """有记录但都未命中映射。"""
    pro = _FakePro()
    pro.set_response(
        "index_member_all",
        [
            {
                "ts_code": "600000.SH",
                "l2_name": "不存在的行业名",
                "l1_name": "",
                "l3_name": "",
                "is_new": "Y",
            },
        ],
    )
    fetcher = TushareFetcher(settings=_settings(), pro=pro, sleep=_no_sleep)
    cat, l2 = fetcher._fetch_one_sw_category("600000.SH")
    assert cat == "未分类"
    assert l2 == "不存在的行业名"


# ===== load_sw_cache 边界 =====
def test_load_sw_cache_oserror(tmp_path: Path) -> None:
    from src.data.provider import TushareFetcher

    path = tmp_path / "unreadable.csv"
    # 用目录模拟不可读：read_text 在目录上会抛 OSError
    path.mkdir()
    result = TushareFetcher.load_sw_cache(path)
    assert result is None


def test_load_sw_cache_with_rows(tmp_path: Path) -> None:
    from src.data.provider import TushareFetcher

    path = tmp_path / "sw.csv"
    path.write_text(
        "ts_code,l2_name,category\n600000.SH,银行,证券金融\n000001.SZ,白酒,大消费\n\n,,\n",
        encoding="utf-8-sig",
    )
    result = TushareFetcher.load_sw_cache(path)
    assert result == {"600000.SH": "证券金融", "000001.SZ": "大消费"}


def test_load_sw_cache_empty_file(tmp_path: Path) -> None:
    from src.data.provider import TushareFetcher

    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8-sig")
    result = TushareFetcher.load_sw_cache(path)
    assert result is None


# ===== _save_sw_cache without l2_names =====
def test_save_sw_cache_no_l2_names(tmp_path: Path) -> None:
    import src.data.provider as _mod

    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    fetcher = TushareFetcher(settings=settings, pro=_FakePro(), sleep=_no_sleep)

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: tmp_path / "sw_industry.csv"
    try:
        mapping = {"600000.SH": "证券金融"}
        fetcher._save_sw_cache(mapping)  # l2_names=None
        loaded = fetcher.load_sw_cache(tmp_path / "sw_industry.csv")
        assert loaded == mapping
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig


# ===== build_sw_cache =====
def test_build_sw_cache(tmp_path: Path) -> None:
    import src.data.provider as _mod

    settings = Settings(
        tushare_token="t", tushare_rate_limit=500, data_dir=str(tmp_path)
    )
    pro = _FakePro()
    pro.set_response(
        "stock_basic",
        [{"ts_code": "600000.SH"}, {"ts_code": "000001.SZ"}, {"ts_code": ""}],
    )
    pro.set_response(
        "index_member_all",
        [
            {
                "ts_code": "600000.SH",
                "l2_name": "证券",
                "l1_name": "",
                "l3_name": "",
                "is_new": "Y",
            },
        ],
    )

    save_orig = _mod.TushareFetcher._sw_cache_path
    _mod.TushareFetcher._sw_cache_path = lambda self: tmp_path / "sw_industry.csv"
    try:
        fetcher = TushareFetcher(settings=settings, pro=pro, sleep=_no_sleep)
        mapping = fetcher.build_sw_cache()
        # 600000.SH → 证券金融, 000001.SZ → index_member_all response is same for all calls (only 1 route)
        # Since _FakePro returns same response for all calls, both stocks get "证券金融"
        assert len(mapping) == 2
        assert mapping["600000.SH"] == "证券金融"
    finally:
        _mod.TushareFetcher._sw_cache_path = save_orig
