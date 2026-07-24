"""字段模型与契约：55 需求→Tushare 字段对齐表（RequirementAlign × 53）、各接口字段集、
OUTPUT_COLUMNS（44 列输出）、StockInfo / StockFeatures 数据模型、百分比字段集合、覆盖统计。
所有列名使用 Tushare 真实字段名，数据为真实值，不做别名转换。
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

# ===== 接口别名（与 src.data.provider.TUSHARE_INTERFACES key 一致）=====
STOCK_BASIC = "stock_basic"
INCOME = "income"  # vip: income_vip
BALANCESHEET = "balancesheet"  # vip: balancesheet_vip
CASHFLOW = "cashflow"  # vip: cashflow_vip
FINA_INDICATOR = "fina_indicator"  # vip: fina_indicator_vip
DAILY_BASIC = "daily_basic"
FINA_AUDIT = "fina_audit"
PLEDGE_STAT = "pledge_stat"
COMPUTED = "computed_in_scoring"  # 评分时由真实字段计算，不落盘
UNAVAILABLE = "unavailable"  # Tushare 无此字段且无近似，首版不采集


@dataclass(frozen=True)
class RequirementAlign:
    """§8.1 需求字段 → Tushare 真实字段的对齐记录。

    Attributes:
        requirement: brd.md §7.8 需求字段中文名。
        endpoint: 来源接口别名（与 TUSHARE_INTERFACES key 一致），或 COMPUTED / UNAVAILABLE。
        tushare_field: 对应 Tushare 真实字段名（元组表示拆为多列）。
        chinese_name: 真实字段的中文翻译（供 CSV 字段对应表使用）。
        match: exact / approximate / computed_in_scoring / unavailable。
        note: 备注。
    """

    requirement: str
    endpoint: str
    tushare_field: str | tuple[str, ...] | None
    chinese_name: str
    match: str
    note: str = ""


# ===== brd.md §7.8 需求字段（55）→ Tushare 真实字段对齐表 =====
REQUIREMENT_ALIGNMENT: list[RequirementAlign] = [
    RequirementAlign("股票代码", STOCK_BASIC, "symbol", "股票代码", "exact"),
    RequirementAlign("股票名称", STOCK_BASIC, "name", "股票名称", "exact"),
    RequirementAlign("行业属性", STOCK_BASIC, "industry", "所属行业", "exact"),
    RequirementAlign(
        "财报所属期间", INCOME, "end_date", "报告期", "exact", "如 20171231"
    ),
    RequirementAlign(
        "主营收入", INCOME, "revenue", "营业收入", "approximate", "营业收入近似主营收入"
    ),
    RequirementAlign(
        "主营利润",
        INCOME,
        "operate_profit",
        "营业利润",
        "approximate",
        "以营业利润近似",
    ),
    RequirementAlign("营业利润", INCOME, "operate_profit", "营业利润", "exact"),
    RequirementAlign("投资收益", INCOME, "invest_income", "投资净收益", "exact"),
    RequirementAlign(
        "营业外收支",
        INCOME,
        ("non_oper_income", "non_oper_exp"),
        "营业外收入/支出",
        "approximate",
        "拆为两列",
    ),
    RequirementAlign("利润总额", INCOME, "total_profit", "利润总额", "exact"),
    RequirementAlign(
        "净利润", INCOME, "n_income_attr_p", "归属母公司股东净利润", "exact"
    ),
    RequirementAlign(
        "未分配利润",
        BALANCESHEET,
        "undistr_porfit",
        "未分配利润",
        "exact",
        "Tushare 拼写为 porfit",
    ),
    RequirementAlign("总资产", BALANCESHEET, "total_assets", "资产总计", "exact"),
    RequirementAlign(
        "流动资产", BALANCESHEET, "total_cur_assets", "流动资产合计", "exact"
    ),
    RequirementAlign("固定资产", BALANCESHEET, "fix_assets", "固定资产", "exact"),
    RequirementAlign("无形资产", BALANCESHEET, "intan_assets", "无形资产", "exact"),
    RequirementAlign("总负债", BALANCESHEET, "total_liab", "负债合计", "exact"),
    RequirementAlign(
        "流动负债", BALANCESHEET, "total_cur_liab", "流动负债合计", "exact"
    ),
    RequirementAlign("长期负债", BALANCESHEET, "total_ncl", "非流动负债合计", "exact"),
    RequirementAlign(
        "股东权益",
        BALANCESHEET,
        "total_hldr_eqy_exc_min_int",
        "股东权益合计(不含少数股东权益)",
        "exact",
    ),
    RequirementAlign("资本公积金", BALANCESHEET, "cap_rese", "资本公积金", "exact"),
    RequirementAlign(
        "经营现金流量", CASHFLOW, "n_cashflow_act", "经营活动现金流量净额", "exact"
    ),
    RequirementAlign(
        "投资现金流量", CASHFLOW, "n_cashflow_inv_act", "投资活动现金流量净额", "exact"
    ),
    RequirementAlign(
        "筹资现金流量",
        CASHFLOW,
        "n_cash_flows_fnc_act",
        "筹资活动现金流量净额",
        "exact",
    ),
    RequirementAlign(
        "现金增加额",
        CASHFLOW,
        "n_incr_cash_cash_equ",
        "现金及现金等价物净增加额",
        "exact",
    ),
    RequirementAlign("每股收益", FINA_INDICATOR, "eps", "基本每股收益", "exact"),
    RequirementAlign("每股净资产", FINA_INDICATOR, "bps", "每股净资产", "exact"),
    RequirementAlign("净资产收益率", FINA_INDICATOR, "roe", "净资产收益率", "exact"),
    RequirementAlign(
        "每股经营现金", FINA_INDICATOR, "ocfps", "每股经营活动现金流量净额", "exact"
    ),
    RequirementAlign(
        "每股公积金", FINA_INDICATOR, "capital_rese_ps", "每股资本公积", "exact"
    ),
    RequirementAlign(
        "每股未分配利润", FINA_INDICATOR, "undist_profit_ps", "每股未分配利润", "exact"
    ),
    RequirementAlign(
        "股东权益比",
        COMPUTED,
        None,
        "股东权益比",
        "computed_in_scoring",
        "= total_hldr_eqy_exc_min_int / total_assets",
    ),
    RequirementAlign(
        "净利润同比增长率",
        FINA_INDICATOR,
        "netprofit_yoy",
        "归母净利润同比增长率(%)",
        "exact",
    ),
    RequirementAlign(
        "主营收入同比增长率", FINA_INDICATOR, "or_yoy", "营业收入同比增长率(%)", "exact"
    ),
    RequirementAlign(
        "销售毛利率", FINA_INDICATOR, "grossprofit_margin", "销售毛利率(%)", "exact"
    ),
    RequirementAlign(
        "调整后每股净资产",
        UNAVAILABLE,
        None,
        "调整后每股净资产",
        "unavailable",
        "Tushare 无此字段",
    ),
    RequirementAlign("总股本", BALANCESHEET, "total_share", "期末总股本", "exact"),
    RequirementAlign(
        "无限售股合计", UNAVAILABLE, None, "流通股本", "unavailable", "首版已删除不采集"
    ),
    RequirementAlign(
        "A股数量", UNAVAILABLE, None, "A股数量", "unavailable", "Tushare 无此字段"
    ),
    RequirementAlign(
        "B股数量", UNAVAILABLE, None, "B股数量", "unavailable", "Tushare 无此字段"
    ),
    RequirementAlign(
        "限售股合计",
        COMPUTED,
        None,
        "限售股合计",
        "computed_in_scoring",
        "= total_share - float_share",
    ),
    RequirementAlign(
        "国家持股数量",
        UNAVAILABLE,
        None,
        "国家持股数量",
        "unavailable",
        "需 top10_holders 聚合",
    ),
    RequirementAlign(
        "国有法人持股",
        UNAVAILABLE,
        None,
        "国有法人持股",
        "unavailable",
        "需 top10_holders 聚合",
    ),
    RequirementAlign(
        "资产负债率", FINA_INDICATOR, "debt_to_assets", "资产负债率(%)", "exact"
    ),
    RequirementAlign("流动比率", FINA_INDICATOR, "current_ratio", "流动比率", "exact"),
    RequirementAlign("速动比率", FINA_INDICATOR, "quick_ratio", "速动比率", "exact"),
    RequirementAlign("权益乘数", FINA_INDICATOR, "assets_to_eqt", "权益乘数", "exact"),
    RequirementAlign(
        "每股经营现金流/每股收益",
        COMPUTED,
        None,
        "每股经营现金流/每股收益",
        "computed_in_scoring",
        "= ocfps / eps",
    ),
    RequirementAlign(
        "净利润占营业利润比",
        COMPUTED,
        None,
        "净利润占营业利润比",
        "computed_in_scoring",
        "= n_income_attr_p / operate_profit",
    ),
    RequirementAlign(
        "主营利润率",
        COMPUTED,
        None,
        "主营利润率",
        "computed_in_scoring",
        "= operate_profit / revenue",
    ),
    RequirementAlign(
        "净利率", FINA_INDICATOR, "netprofit_margin", "销售净利率(%)", "exact"
    ),
    RequirementAlign(
        "投资收益占比",
        COMPUTED,
        None,
        "投资收益占比",
        "computed_in_scoring",
        "= invest_income / total_profit",
    ),
    RequirementAlign(
        "现金流量比率",
        FINA_INDICATOR,
        "ocf_to_shortdebt",
        "经营现金流/流动负债",
        "exact",
    ),
]


# ===== 补充字段（一票否决 §8.2 / 三维评分 §8.3 辅助，非 55 需求字段）=====
@dataclass(frozen=True)
class SupplementaryField:
    """补充字段描述（服务一票否决与三维评分）。"""

    tushare_field: str
    chinese_name: str
    endpoint: str
    purpose: str  # veto / scoring


SUPPLEMENTARY_FIELDS: list[SupplementaryField] = [
    SupplementaryField("money_cap", "货币资金", BALANCESHEET, "veto"),
    SupplementaryField("free_cashflow", "企业自由现金流量", CASHFLOW, "scoring"),
    SupplementaryField("inv_turn", "存货周转率", FINA_INDICATOR, "scoring"),
]


# ===== 各接口需请求的真实字段（供 TushareFetcher 拼 fields= 参数）=====
STOCK_BASIC_FIELDS: tuple[str, ...] = ("ts_code", "symbol", "name", "industry")
INCOME_FIELDS: tuple[str, ...] = (
    "ts_code",
    "end_date",
    "revenue",
    "operate_profit",
    "invest_income",
    "non_oper_income",
    "non_oper_exp",
    "total_profit",
    "n_income_attr_p",
)
BALANCESHEET_FIELDS: tuple[str, ...] = (
    "ts_code",
    "undistr_porfit",
    "total_assets",
    "total_cur_assets",
    "fix_assets",
    "intan_assets",
    "total_liab",
    "total_cur_liab",
    "total_ncl",
    "total_hldr_eqy_exc_min_int",
    "cap_rese",
    "total_share",
    "money_cap",
)
CASHFLOW_FIELDS: tuple[str, ...] = (
    "ts_code",
    "n_cashflow_act",
    "n_cashflow_inv_act",
    "n_cash_flows_fnc_act",
    "n_incr_cash_cash_equ",
    "free_cashflow",
)
FINA_INDICATOR_FIELDS: tuple[str, ...] = (
    "ts_code",
    "eps",
    "bps",
    "roe",
    "ocfps",
    "capital_rese_ps",
    "undist_profit_ps",
    "netprofit_yoy",
    "or_yoy",
    "grossprofit_margin",
    "debt_to_assets",
    "current_ratio",
    "quick_ratio",
    "assets_to_eqt",
    "netprofit_margin",
    "ocf_to_shortdebt",
    "inv_turn",
)
DAILY_BASIC_FIELDS: tuple[str, ...] = ("ts_code",)
FINA_AUDIT_FIELDS: tuple[str, ...] = ("ts_code", "end_date")
PLEDGE_STAT_FIELDS: tuple[str, ...] = ("ts_code", "end_date")

# 输出列顺序（Tushare 真实字段名）；name 首列，ts_code 次列，不含 symbol。
OUTPUT_COLUMNS: tuple[str, ...] = (
    # —— 基本信息 ——
    "name",
    "ts_code",
    "industry",
    "end_date",
    # —— 利润表（盈利能力）——
    "revenue",
    "operate_profit",
    "non_oper_income",
    "non_oper_exp",
    "invest_income",
    "total_profit",
    "n_income_attr_p",
    # —— 利润率与增速 ——
    "grossprofit_margin",
    "netprofit_margin",
    "or_yoy",
    "netprofit_yoy",
    # —— 资产负债表（资产端）——
    "total_assets",
    "total_cur_assets",
    "fix_assets",
    "intan_assets",
    # —— 资产负债表（负债端）——
    "total_liab",
    "total_cur_liab",
    "total_ncl",
    # —— 资产负债表（权益端）——
    "total_hldr_eqy_exc_min_int",
    "cap_rese",
    "undistr_porfit",
    "money_cap",
    # —— 偿债与杠杆指标 ——
    "debt_to_assets",
    "current_ratio",
    "quick_ratio",
    "assets_to_eqt",
    # —— 每股指标与回报 ——
    "total_share",
    "eps",
    "bps",
    "ocfps",
    "capital_rese_ps",
    "undist_profit_ps",
    "roe",
    # —— 现金流量 ——
    "n_cashflow_act",
    "n_cashflow_inv_act",
    "n_cash_flows_fnc_act",
    "n_incr_cash_cash_equ",
    "free_cashflow",
    "ocf_to_shortdebt",
    # —— 营运效率 ——
    "inv_turn",
)

# 补充输出列（一票否决/评分辅助，追加在 OUTPUT_COLUMNS 之后；去重已出现在核心列的字段）
_core_set = set(OUTPUT_COLUMNS)
SUPPLEMENTARY_COLUMNS: tuple[str, ...] = ()

# 全部输出列 = 核心列 + 补充列（无重复）
ALL_OUTPUT_COLUMNS: tuple[str, ...] = (*OUTPUT_COLUMNS, *SUPPLEMENTARY_COLUMNS)

# Tushare 以百分数数值返回的字段（如 30.5 表示 30.5%）；写盘时按 dev-log 加 % 后缀。
PERCENT_FIELDS: frozenset[str] = frozenset(
    {
        "netprofit_yoy",
        "or_yoy",
        "grossprofit_margin",
        "debt_to_assets",
        "netprofit_margin",
    }
)


class StockInfo(BaseModel):
    """上市公司清单条目（来源 stock_basic，字段名即 Tushare 真实字段名）。"""

    model_config = ConfigDict(populate_by_name=True)

    ts_code: str
    symbol: str = ""
    name: str = ""
    industry: str = ""


class StockFeatures(BaseModel):
    """单股特征工程数据——字段名即 Tushare 真实返回字段名，数据为真实值。

    采集层只存真实字段；§8.1 中的计算型需求（股东权益比/主营利润率等）
    不在此模型，由 M2 评分纯函数基于这些真实字段计算。
    补充字段（货币资金/审计结果/质押比例等）服务一票否决与三维评分。
    """

    model_config = ConfigDict(populate_by_name=True)

    # —— stock_basic ——
    ts_code: str
    symbol: str = ""
    name: str = ""
    industry: str = ""
    # —— income ——
    end_date: str | None = None
    revenue: float | None = None
    operate_profit: float | None = None
    invest_income: float | None = None
    non_oper_income: float | None = None
    non_oper_exp: float | None = None
    total_profit: float | None = None
    n_income_attr_p: float | None = None
    # —— balancesheet ——
    undistr_porfit: float | None = None
    total_assets: float | None = None
    total_cur_assets: float | None = None
    fix_assets: float | None = None
    intan_assets: float | None = None
    total_liab: float | None = None
    total_cur_liab: float | None = None
    total_ncl: float | None = None
    total_hldr_eqy_exc_min_int: float | None = None
    cap_rese: float | None = None
    total_share: float | None = None
    money_cap: float | None = None
    # —— cashflow ——
    n_cashflow_act: float | None = None
    n_cashflow_inv_act: float | None = None
    n_cash_flows_fnc_act: float | None = None
    n_incr_cash_cash_equ: float | None = None
    free_cashflow: float | None = None
    # —— fina_indicator ——
    eps: float | None = None
    bps: float | None = None
    roe: float | None = None
    ocfps: float | None = None
    capital_rese_ps: float | None = None
    undist_profit_ps: float | None = None
    netprofit_yoy: float | None = None
    or_yoy: float | None = None
    grossprofit_margin: float | None = None
    debt_to_assets: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    assets_to_eqt: float | None = None
    netprofit_margin: float | None = None
    ocf_to_shortdebt: float | None = None
    inv_turn: float | None = None

    @classmethod
    def output_columns(cls) -> list[str]:
        """输出 CSV/表的列名（Tushare 真实字段名，按 OUTPUT_COLUMNS 顺序）。"""
        return list(OUTPUT_COLUMNS)

    @classmethod
    def all_output_columns(cls) -> list[str]:
        """全部输出列名（核心 + 补充），按 ALL_OUTPUT_COLUMNS 顺序。"""
        return list(ALL_OUTPUT_COLUMNS)


def requirement_coverage() -> dict[str, int]:
    """统计 §8.1 需求字段的对齐覆盖情况，供文档/报告使用。"""
    counts: dict[str, int] = {}
    for a in REQUIREMENT_ALIGNMENT:
        counts[a.match] = counts.get(a.match, 0) + 1
    return counts
