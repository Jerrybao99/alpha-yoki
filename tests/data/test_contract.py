"""特征工程字段模型与数据源抽象的纯逻辑单测。验证需求对齐表、输出列、
接口注册表（vip 优先）、补充字段、BaseFetcher 不可实例化。不触网络。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.data.contract import (
    ALL_OUTPUT_COLUMNS,
    BALANCESHEET_FIELDS,
    CASHFLOW_FIELDS,
    FINA_INDICATOR_FIELDS,
    INCOME_FIELDS,
    OUTPUT_COLUMNS,
    PERCENT_FIELDS,
    REQUIREMENT_ALIGNMENT,
    STOCK_BASIC_FIELDS,
    SUPPLEMENTARY_COLUMNS,
    SUPPLEMENTARY_FIELDS,
    StockFeatures,
    StockInfo,
    requirement_coverage,
)
from src.data.provider import (
    TUSHARE_INTERFACES,
    BaseFetcher,
    get_doc_url,
    get_vip_api_name,
)


def test_requirement_alignment_covers_all() -> None:
    """需求字段（采集层落地）对齐表全覆盖且中文名唯一。

    owner 决策移除上市日期/公告日期列，采集对齐表由 55 收敛为 53（见 CHANGELOG）。
    """
    reqs = [a.requirement for a in REQUIREMENT_ALIGNMENT]
    assert len(reqs) == 53
    assert len(set(reqs)) == 53


def test_requirement_has_chinese_name() -> None:
    """每条对齐记录必须有非空 chinese_name（真实字段中文翻译）。"""
    for a in REQUIREMENT_ALIGNMENT:
        assert a.chinese_name, f"缺少中文翻译: {a.requirement}"


def test_requirement_match_types_valid() -> None:
    """match 取值合法；exact/approximate 必须有 tushare_field，其余必须无。"""
    valid = {"exact", "approximate", "computed_in_scoring", "unavailable"}
    for a in REQUIREMENT_ALIGNMENT:
        assert a.match in valid, a
        if a.match in {"exact", "approximate"}:
            assert a.tushare_field, f"{a.match} 缺少字段: {a.requirement}"
        else:
            assert a.tushare_field is None, f"{a.match} 不应有字段: {a.requirement}"


def test_requirement_coverage_summary() -> None:
    """覆盖统计：exact 占多数，unavailable 受控。"""
    cov = requirement_coverage()
    assert sum(cov.values()) == 53
    assert cov["exact"] >= 35
    assert cov["unavailable"] == 6  # 调整后每股净资产/A股/B股/国家持股/国有法人持股 + float_share已删除
    assert cov["computed_in_scoring"] == 6


def test_endpoint_field_lists_no_duplicate() -> None:
    """stock_basic 含 ts_code 主键；VIP 接口字段集为空（取全量字段）。"""
    assert len(STOCK_BASIC_FIELDS) == len(set(STOCK_BASIC_FIELDS))
    assert "ts_code" in STOCK_BASIC_FIELDS
    for fields in (
        INCOME_FIELDS,
        BALANCESHEET_FIELDS,
        CASHFLOW_FIELDS,
        FINA_INDICATOR_FIELDS,
    ):
        assert fields == ()


def test_output_columns_are_tushare_real_names() -> None:
    """输出列全部为 Tushare 真实字段名，name 首列，ts_code 次列，symbol 不在输出列中。"""
    cols = list(OUTPUT_COLUMNS)
    assert cols[0] == "name"
    assert cols[1] == "ts_code"
    assert len(cols) == len(set(cols))  # 无重复
    for f in (
        "n_income_attr_p",
        "undistr_porfit",
        "total_hldr_eqy_exc_min_int",
        "n_cash_flows_fnc_act",
        "grossprofit_margin",
        "debt_to_assets",
        "ocf_to_shortdebt",
        "money_cap",
        "free_cashflow",
        "inv_turn",
    ):
        assert f in cols, f
    assert StockFeatures.output_columns() == cols


def test_output_columns_match_model_fields() -> None:
    """StockFeatures 显式声明的输出字段必须全部出现在输出列中；
    symbol 仅用于内部标识不在输出列中；extra=allow 允许额外列。"""
    declared = set(StockFeatures.model_fields) - {"symbol"}
    assert declared <= set(OUTPUT_COLUMNS), (
        f"StockFeatures 声明了但未在 OUTPUT_COLUMNS 中: {declared - set(OUTPUT_COLUMNS)}"
    )
    assert declared <= set(ALL_OUTPUT_COLUMNS), (
        f"StockFeatures 声明了但未在 ALL_OUTPUT_COLUMNS 中: {declared - set(ALL_OUTPUT_COLUMNS)}"
    )


def test_supplementary_columns_no_overlap() -> None:
    """补充列与核心列无重复，ALL_OUTPUT_COLUMNS 无重复。"""
    assert set(SUPPLEMENTARY_COLUMNS).isdisjoint(set(OUTPUT_COLUMNS))
    all_cols = list(ALL_OUTPUT_COLUMNS)
    assert len(all_cols) == len(set(all_cols))


def test_all_output_columns_match() -> None:
    """all_output_columns() 返回 ALL_OUTPUT_COLUMNS。"""
    assert StockFeatures.all_output_columns() == list(ALL_OUTPUT_COLUMNS)


def test_percent_fields_subset_of_output() -> None:
    """百分比字段必须是输出列。"""
    assert PERCENT_FIELDS <= set(OUTPUT_COLUMNS)


def test_supplementary_fields_valid() -> None:
    """补充字段 endpoint 必须在接口注册表中，purpose 为 veto 或 scoring。"""
    for sf in SUPPLEMENTARY_FIELDS:
        assert sf.endpoint in TUSHARE_INTERFACES, sf
        assert sf.purpose in {"veto", "scoring"}, sf
        assert sf.chinese_name, sf


# ===== 接口注册表测试 =====
VIP_ENDPOINTS = {
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "forecast",
    "express",
    "fina_mainbz",
}


def test_tushare_interfaces_registry() -> None:
    """接口注册表非空，每个接口有 api_name/vip_api_name/doc_url/min_points。"""
    assert len(TUSHARE_INTERFACES) >= 15
    for key, iface in TUSHARE_INTERFACES.items():
        assert iface.api_name, key
        assert iface.vip_api_name, key
        assert iface.doc_url.startswith("https://tushare.pro/document/2?doc_id="), key
        assert iface.min_points > 0, key
        assert iface.description, key


def test_vip_interfaces() -> None:
    """财务三表/指标/预告/快报/主营构成有 vip 后缀高级接口。"""
    for key in VIP_ENDPOINTS:
        iface = TUSHARE_INTERFACES[key]
        assert iface.vip_api_name.endswith("_vip"), f"{key} 缺少 vip 接口"
        assert iface.vip_api_name != iface.api_name, f"{key} vip 接口名与常规接口名相同"


def test_non_vip_interfaces() -> None:
    """非财务三表接口无 vip 后缀，vip_api_name 同 api_name。"""
    non_vip = set(TUSHARE_INTERFACES) - VIP_ENDPOINTS
    for key in non_vip:
        iface = TUSHARE_INTERFACES[key]
        assert iface.vip_api_name == iface.api_name, f"{key} 不应有 vip 接口"


def test_get_vip_api_name_and_doc_url() -> None:
    """get_vip_api_name / get_doc_url 正确返回。"""
    assert get_vip_api_name("income") == "income_vip"
    assert get_vip_api_name("stock_basic") == "stock_basic"
    assert get_doc_url("income") == "https://tushare.pro/document/2?doc_id=33"


def test_stock_features_required_ts_code() -> None:
    """ts_code 必填，缺失报错。"""
    with pytest.raises(ValidationError):
        StockFeatures()  # type: ignore[call-arg]


def test_stock_features_real_field_roundtrip() -> None:
    """用 Tushare 真实字段名构造与 dump，显式字段保持不变；
    extra=allow + mode="python" 确保额外字段也被序列化。"""
    feat = StockFeatures(
        ts_code="600000.SH",
        symbol="600000",
        name="浦发银行",
        revenue=1.2e10,
        n_income_attr_p=3.4e9,
        roe=12.5,
        money_cap=5.0e11,
    )
    dumped = feat.model_dump()
    assert dumped["ts_code"] == "600000.SH"
    assert dumped["n_income_attr_p"] == 3.4e9
    assert dumped["money_cap"] == 5.0e11
    # 显式声明字段应全部在 dump 中
    for f in StockFeatures.model_fields:
        assert f in dumped, f


def test_stock_features_tolerates_missing() -> None:
    """缺失字段默认 None（采集时单股可能缺字段）。"""
    feat = StockFeatures(ts_code="000001.SZ")
    dumped = feat.model_dump()
    assert dumped["n_income_attr_p"] is None
    assert dumped["eps"] is None
    assert dumped["money_cap"] is None


def test_stock_info_real_fields() -> None:
    info = StockInfo(ts_code="600000.SH", symbol="600000", name="浦发银行", industry="银行")
    assert info.ts_code == "600000.SH"
    assert info.symbol == "600000"


def test_base_fetcher_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseFetcher()  # type: ignore[abstract]


def test_base_fetcher_concrete_subclass_works() -> None:
    """完整实现的子类可正常实例化；fetch_financials 用 ts_code 返回 StockFeatures。"""

    class FakeFetcher(BaseFetcher):
        def fetch_stock_list(self):
            return [StockInfo(ts_code="600000.SH", symbol="600000", name="浦发银行")]  # noqa: ARG002

        def fetch_financials(self, ts_code, period=None):
            return StockFeatures(ts_code=ts_code)

    f = FakeFetcher()
    assert f.fetch_stock_list()[0].ts_code == "600000.SH"
    assert f.fetch_financials("600000.SH").ts_code == "600000.SH"
