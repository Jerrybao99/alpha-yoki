"""CSV 输出与格式化：FIELD_CN 中英文列头映射、format_value 数值格式化
（亿/万/%/倍/次/元/股/比率/天）、to_output_row 行标准化、write_features_csv 写数据 CSV、
write_data_source_csv 写数据来源表、FIELD_TO_INTERFACE 字段→接口溯源。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from src.data.contract import (
    ALL_OUTPUT_COLUMNS,
    FIELD_CN,
    FIELD_UNIT,
    PERCENT_FIELDS,
    StockFeatures,
)
from src.data.provider import TUSHARE_INTERFACES, get_vip_api_name

# 字段 → 来源接口别名（按首次出现的接口归属）
FIELD_TO_INTERFACE: dict[str, str] = {}
_INCOME_SET = set()  # type: ignore[var-annotated]
_BALANCESHEET_SET = set()  # type: ignore[var-annotated]
_CASHFLOW_SET = set()  # type: ignore[var-annotated]
_FINA_SET = set()  # type: ignore[var-annotated]

# 接口→字段集（从 Tushare 文档输出参数表提取，用于数据来源表溯源）
_INCOME_KEYS = {
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "end_type",
    "basic_eps",
    "diluted_eps",
    "total_revenue",
    "revenue",
    "int_income",
    "prem_earned",
    "comm_income",
    "n_commis_income",
    "n_oth_income",
    "n_oth_b_income",
    "prem_income",
    "out_prem",
    "une_prem_reser",
    "reins_income",
    "n_sec_tb_income",
    "n_sec_uw_income",
    "n_asset_mg_income",
    "oth_b_income",
    "fv_value_chg_gain",
    "invest_income",
    "ass_invest_income",
    "forex_gain",
    "total_cogs",
    "oper_cost",
    "int_exp",
    "comm_exp",
    "biz_tax_surchg",
    "sell_exp",
    "admin_exp",
    "fin_exp",
    "assets_impair_loss",
    "prem_refund",
    "compens_payout",
    "reser_insur_liab",
    "div_payt",
    "reins_exp",
    "oper_exp",
    "compens_payout_refu",
    "insur_reser_refu",
    "reins_cost_refund",
    "other_bus_cost",
    "operate_profit",
    "non_oper_income",
    "non_oper_exp",
    "nca_disploss",
    "total_profit",
    "income_tax",
    "n_income",
    "n_income_attr_p",
    "minority_gain",
    "oth_compr_income",
    "t_compr_income",
    "compr_inc_attr_p",
    "compr_inc_attr_m_s",
    "ebit",
    "ebitda",
    "insurance_exp",
    "undist_profit",
    "distable_profit",
    "rd_exp",
    "fin_exp_int_exp",
    "fin_exp_int_inc",
    "transfer_surplus_rese",
    "transfer_housing_imprest",
    "transfer_oth",
    "adj_lossgain",
    "withdra_legal_surplus",
    "withdra_legal_pubfund",
    "withdra_biz_devfund",
    "withdra_rese_fund",
    "withdra_oth_ersu",
    "workers_welfare",
    "distr_profit_shrhder",
    "prfshare_payable_dvd",
    "comshare_payable_dvd",
    "capit_comstock_div",
    "net_after_nr_lp_correct",
    "credit_impa_loss",
    "net_expo_hedging_benefits",
    "oth_impair_loss_assets",
    "total_opcost",
    "amodcost_fin_assets",
    "oth_income",
    "asset_disp_income",
    "continued_net_profit",
    "end_net_profit",
    "update_flag",
}
_BALANCESHEET_KEYS = {
    "total_share",
    "cap_rese",
    "undistr_porfit",
    "surplus_rese",
    "special_rese",
    "money_cap",
    "trad_asset",
    "notes_receiv",
    "accounts_receiv",
    "oth_receiv",
    "prepayment",
    "div_receiv",
    "int_receiv",
    "inventories",
    "amor_exp",
    "nca_within_1y",
    "sett_rsrv",
    "loanto_oth_bank_fi",
    "premium_receiv",
    "reinsur_receiv",
    "reinsur_res_receiv",
    "pur_resale_fa",
    "oth_cur_assets",
    "total_cur_assets",
    "fa_avail_for_sale",
    "htm_invest",
    "lt_eqt_invest",
    "invest_real_estate",
    "time_deposits",
    "oth_assets",
    "lt_rec",
    "fix_assets",
    "cip",
    "const_materials",
    "fixed_assets_disp",
    "produc_bio_assets",
    "oil_and_gas_assets",
    "intan_assets",
    "r_and_d",
    "goodwill",
    "lt_amor_exp",
    "defer_tax_assets",
    "decr_in_disbur",
    "oth_nca",
    "total_nca",
    "cash_reser_cb",
    "depos_in_oth_bfi",
    "prec_metals",
    "deriv_assets",
    "rr_reins_une_prem",
    "rr_reins_outstd_cla",
    "rr_reins_lins_liab",
    "rr_reins_lthins_liab",
    "refund_depos",
    "ph_pledge_loans",
    "refund_cap_depos",
    "indep_acct_assets",
    "client_depos",
    "client_prov",
    "transac_seat_fee",
    "invest_as_receiv",
    "total_assets",
    "lt_borr",
    "st_borr",
    "cb_borr",
    "depos_ib_deposits",
    "loan_oth_bank",
    "trading_fl",
    "notes_payable",
    "acct_payable",
    "adv_receipts",
    "sold_for_repur_fa",
    "comm_payable",
    "payroll_payable",
    "taxes_payable",
    "int_payable",
    "div_payable",
    "oth_payable",
    "acc_exp",
    "deferred_inc",
    "st_bonds_payable",
    "payable_to_reinsurer",
    "rsrv_insur_cont",
    "acting_trading_sec",
    "acting_uw_sec",
    "non_cur_liab_due_1y",
    "oth_cur_liab",
    "total_cur_liab",
    "bond_payable",
    "lt_payable",
    "specific_payables",
    "estimated_liab",
    "defer_tax_liab",
    "defer_inc_non_cur_liab",
    "oth_ncl",
    "total_ncl",
    "depos_oth_bfi",
    "deriv_liab",
    "depos",
    "agency_bus_liab",
    "oth_liab",
    "prem_receiv_adva",
    "depos_received",
    "ph_invest",
    "reser_une_prem",
    "reser_outstd_claims",
    "reser_lins_liab",
    "reser_lthins_liab",
    "indept_acc_liab",
    "pledge_borr",
    "indem_payable",
    "policy_div_payable",
    "total_liab",
    "treasury_share",
    "ordin_risk_reser",
    "forex_differ",
    "invest_loss_unconf",
    "minority_int",
    "total_hldr_eqy_exc_min_int",
    "total_hldr_eqy_inc_min_int",
    "total_liab_hldr_eqy",
    "lt_payroll_payable",
    "oth_comp_income",
    "oth_eqt_tools",
    "oth_eqt_tools_p_shr",
    "lending_funds",
    "acc_receivable",
    "st_fin_payable",
    "payables",
    "hfs_assets",
    "hfs_sales",
    "cost_fin_assets",
    "fair_value_fin_assets",
    "cip_total",
    "oth_pay_total",
    "long_pay_total",
    "debt_invest",
    "oth_debt_invest",
    "oth_eq_invest",
    "oth_illiq_fin_assets",
    "oth_eq_ppbond",
    "receiv_financing",
    "use_right_assets",
    "lease_liab",
    "contract_assets",
    "contract_liab",
    "accounts_receiv_bill",
    "accounts_pay",
    "oth_rcv_total",
    "fix_assets_total",
}
_CASHFLOW_KEYS = {
    "net_profit",
    "finan_exp",
    "c_fr_sale_sg",
    "recp_tax_rends",
    "n_depos_incr_fi",
    "n_incr_loans_cb",
    "n_inc_borr_oth_fi",
    "prem_fr_orig_contr",
    "n_incr_insured_dep",
    "n_reinsur_prem",
    "n_incr_disp_tfa",
    "ifc_cash_incr",
    "n_incr_disp_faas",
    "n_incr_loans_oth_bank",
    "n_cap_incr_repur",
    "c_fr_oth_operate_a",
    "c_inf_fr_operate_a",
    "c_paid_goods_s",
    "c_paid_to_for_empl",
    "c_paid_for_taxes",
    "n_incr_clt_loan_adv",
    "n_incr_dep_cbob",
    "c_pay_claims_orig_inco",
    "pay_handling_chrg",
    "pay_comm_insur_plcy",
    "oth_cash_pay_oper_act",
    "st_cash_out_act",
    "n_cashflow_act",
    "oth_recp_ral_inv_act",
    "c_disp_withdrwl_invest",
    "c_recp_return_invest",
    "n_recp_disp_fiolta",
    "n_recp_disp_sobu",
    "stot_inflows_inv_act",
    "c_pay_acq_const_fiolta",
    "c_paid_invest",
    "n_disp_subs_oth_biz",
    "oth_pay_ral_inv_act",
    "n_incr_pledge_loan",
    "stot_out_inv_act",
    "n_cashflow_inv_act",
    "c_recp_borrow",
    "proc_issue_bonds",
    "oth_cash_recp_ral_fnc_act",
    "stot_cash_in_fnc_act",
    "free_cashflow",
    "c_prepay_amt_borr",
    "c_pay_dist_dpcp_int_exp",
    "incl_dvd_profit_paid_sc_ms",
    "oth_cashpay_ral_fnc_act",
    "stot_cashout_fnc_act",
    "n_cash_flows_fnc_act",
    "eff_fx_flu_cash",
    "n_incr_cash_cash_equ",
    "c_cash_equ_beg_period",
    "c_cash_equ_end_period",
    "c_recp_cap_contrib",
    "incl_cash_rec_saims",
    "uncon_invest_loss",
    "prov_depr_assets",
    "depr_fa_coga_dpba",
    "amort_intang_assets",
    "lt_amort_deferred_exp",
    "decr_deferred_exp",
    "incr_acc_exp",
    "loss_disp_fiolta",
    "loss_scr_fa",
    "loss_fv_chg",
    "invest_loss",
    "decr_def_inc_tax_assets",
    "incr_def_inc_tax_liab",
    "decr_inventories",
    "decr_oper_payable",
    "incr_oper_payable",
    "others",
    "im_net_cashflow_oper_act",
    "conv_debt_into_cap",
    "conv_copbonds_due_within_1y",
    "fa_fnc_leases",
    "im_n_incr_cash_equ",
    "net_dism_capital_add",
    "net_cash_rece_sec",
    "end_bal_cash",
    "beg_bal_cash",
    "end_bal_cash_equ",
    "beg_bal_cash_equ",
    "use_right_asset_dep",
    "oth_loss_asset",
}
_FINA_KEYS = {
    "eps",
    "dt_eps",
    "total_revenue_ps",
    "revenue_ps",
    "capital_rese_ps",
    "surplus_rese_ps",
    "undist_profit_ps",
    "extra_item",
    "profit_dedt",
    "gross_margin",
    "current_ratio",
    "quick_ratio",
    "cash_ratio",
    "invturn_days",
    "arturn_days",
    "inv_turn",
    "ar_turn",
    "ca_turn",
    "fa_turn",
    "assets_turn",
    "op_income",
    "valuechange_income",
    "interst_income",
    "daa",
    "fcff",
    "fcfe",
    "current_exint",
    "noncurrent_exint",
    "interestdebt",
    "netdebt",
    "tangible_asset",
    "working_capital",
    "networking_capital",
    "invest_capital",
    "retained_earnings",
    "diluted2_eps",
    "bps",
    "ocfps",
    "retainedps",
    "cfps",
    "ebit_ps",
    "fcff_ps",
    "fcfe_ps",
    "netprofit_margin",
    "grossprofit_margin",
    "cogs_of_sales",
    "expense_of_sales",
    "profit_to_gr",
    "saleexp_to_gr",
    "adminexp_of_gr",
    "finaexp_of_gr",
    "impai_ttm",
    "gc_of_gr",
    "op_of_gr",
    "ebit_of_gr",
    "roe",
    "roe_waa",
    "roe_dt",
    "roa",
    "npta",
    "roic",
    "roe_yearly",
    "roa2_yearly",
    "roe_avg",
    "opincome_of_ebt",
    "investincome_of_ebt",
    "n_op_profit_of_ebt",
    "tax_to_ebt",
    "dtprofit_to_profit",
    "salescash_to_or",
    "ocf_to_or",
    "ocf_to_opincome",
    "capitalized_to_da",
    "debt_to_assets",
    "assets_to_eqt",
    "dp_assets_to_eqt",
    "ca_to_assets",
    "nca_to_assets",
    "tbassets_to_totalassets",
    "int_to_talcap",
    "eqt_to_talcapital",
    "currentdebt_to_debt",
    "longdeb_to_debt",
    "ocf_to_shortdebt",
    "debt_to_eqt",
    "eqt_to_debt",
    "eqt_to_interestdebt",
    "tangibleasset_to_debt",
    "tangasset_to_intdebt",
    "tangibleasset_to_netdebt",
    "ocf_to_debt",
    "ocf_to_interestdebt",
    "ocf_to_netdebt",
    "ebit_to_interest",
    "longdebt_to_workingcapital",
    "ebitda_to_debt",
    "turn_days",
    "roa_yearly",
    "roa_dp",
    "fixed_assets",
    "profit_prefin_exp",
    "non_op_profit",
    "op_to_ebt",
    "nop_to_ebt",
    "ocf_to_profit",
    "cash_to_liqdebt",
    "cash_to_liqdebt_withinterest",
    "op_to_liqdebt",
    "op_to_debt",
    "roic_yearly",
    "total_fa_trun",
    "profit_to_op",
    "q_opincome",
    "q_investincome",
    "q_dtprofit",
    "q_eps",
    "q_netprofit_margin",
    "q_gsprofit_margin",
    "q_exp_to_sales",
    "q_profit_to_gr",
    "q_saleexp_to_gr",
    "q_adminexp_to_gr",
    "q_finaexp_to_gr",
    "q_impair_to_gr_ttm",
    "q_gc_to_gr",
    "q_op_to_gr",
    "q_roe",
    "q_dt_roe",
    "q_npta",
    "q_opincome_to_ebt",
    "q_investincome_to_ebt",
    "q_dtprofit_to_profit",
    "q_salescash_to_or",
    "q_ocf_to_sales",
    "q_ocf_to_or",
    "basic_eps_yoy",
    "dt_eps_yoy",
    "cfps_yoy",
    "op_yoy",
    "ebt_yoy",
    "netprofit_yoy",
    "dt_netprofit_yoy",
    "ocf_yoy",
    "roe_yoy",
    "bps_yoy",
    "assets_yoy",
    "eqt_yoy",
    "tr_yoy",
    "or_yoy",
    "q_gr_yoy",
    "q_gr_qoq",
    "q_sales_yoy",
    "q_sales_qoq",
    "q_op_yoy",
    "q_op_qoq",
    "q_profit_yoy",
    "q_profit_qoq",
    "q_netprofit_yoy",
    "q_netprofit_qoq",
    "equity_yoy",
}

# stock_basic 字段
_STOCK_BASIC_KEYS = {"ts_code", "symbol", "name", "industry"}

# 构建字段→接口溯源
for _f in _STOCK_BASIC_KEYS:
    FIELD_TO_INTERFACE[_f] = "stock_basic"
for _f in _INCOME_KEYS:
    FIELD_TO_INTERFACE.setdefault(_f, "income")
for _f in _BALANCESHEET_KEYS:
    FIELD_TO_INTERFACE.setdefault(_f, "balancesheet")
for _f in _CASHFLOW_KEYS:
    FIELD_TO_INTERFACE.setdefault(_f, "cashflow")
for _f in _FINA_KEYS:
    FIELD_TO_INTERFACE.setdefault(_f, "fina_indicator")

# date/string fields shared across interfaces
for _f in (
    "ann_date",
    "f_ann_date",
    "report_type",
    "comp_type",
    "end_type",
    "update_flag",
):
    FIELD_TO_INTERFACE.setdefault(_f, "income")

FIELD_TO_INTERFACE["holder_num"] = "stk_holdernumber"


def _unit_of(field: str) -> tuple[str, str]:
    """返回 (单位, 来源)；unit 来自 FIELD_UNIT，来源固定为「推断」。"""
    unit = FIELD_UNIT.get(field, "—")
    return unit, "推断" if unit != "—" else "—"


def format_value(field: str, value: Any) -> str:
    """按 FIELD_UNIT 中记录的单位格式化单元格。

    规则：
    - None → 空串
    - ``%``、``天`` → 两位小数 + 单位
    - ``倍/次/元/股`` → 两位小数 + 单位，不做数量级缩放
    - ``比率`` → 两位小数，无后缀
    - ``元`` → 亿/万 数量级 + 元
    - ``股`` → 亿/万 数量级
    - ``户`` → 整数 + 户
    - 无单位/未知 → 亿/万 数量级
    """
    if value is None:
        return ""
    if field in PERCENT_FIELDS:
        return f"{float(value):.2f}%"
    if isinstance(value, (int, float)):
        v = float(value)
        unit, _source = _unit_of(field)

        if unit in ("%", "天"):
            return f"{v:.2f}{unit}"
        if unit in ("倍", "次", "元/股"):
            return f"{v:.2f}{unit}"
        if unit == "比率":
            return f"{v:.2f}"
        if unit == "户":
            return f"{int(v)}户"

        _w = abs(v) / 1e4
        if abs(v) >= 1e8 or _w >= 9999.995:
            scaled, mag = v / 1e8, "亿"
        elif abs(v) >= 1e4:
            scaled, mag = v / 1e4, "万"
        else:
            scaled, mag = v, ""

        if unit == "元":
            return f"{scaled:.2f}{mag}元"
        if unit == "股":
            return f"{scaled:.2f}{mag}股"
        return f"{scaled:.2f}{mag}" if mag else f"{scaled:.2f}"
    return str(value)


def write_features_csv(features: list[StockFeatures], out_path: Path) -> Path:
    """写特征数据 CSV：中文列头 + 格式化值。"""
    headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    rows: list[list[str]] = []
    for feat in features:
        dumped = feat.model_dump()
        rows.append([format_value(c, dumped.get(c)) for c in ALL_OUTPUT_COLUMNS])

    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(row))
    content = "\n".join(lines) + "\n"
    try:
        out_path.write_text(content, encoding="utf-8-sig")
    except (PermissionError, IsADirectoryError):
        import shutil

        tmp = Path(tempfile.mktemp(suffix=".csv", prefix=out_path.stem + "_"))
        tmp.write_text(content, encoding="utf-8-sig")
        shutil.copy(tmp, out_path.with_suffix(".csv.tmp"))
        print(f"\u26a0 目标文件被占用，已写到临时文件: {out_path.with_suffix('.csv.tmp')}")
    return out_path


def write_data_source_csv(out_path: Path) -> Path:
    """写数据来源 CSV：接口/字段/字段中文/单位/单位来源/文档URL。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["接口,字段,字段中文,单位,单位来源,文档URL"]
    for field in ALL_OUTPUT_COLUMNS:
        iface_key = FIELD_TO_INTERFACE.get(field)
        if iface_key is None:
            continue
        iface = TUSHARE_INTERFACES.get(iface_key)
        if iface is None:
            continue
        api_name = get_vip_api_name(iface_key)
        cn = FIELD_CN.get(field, field)
        unit, src = _unit_of(field)
        lines.append(f"{api_name},{field},{cn},{unit},{src},{iface.doc_url}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return out_path


def format_percent(value: float | None) -> str | None:
    """百分比格式化：30.5 → ``30.50%``；None → None。"""
    if value is None:
        return None
    return f"{value:.2f}%"


def to_output_row(features: StockFeatures) -> dict[str, Any]:
    """按 ALL_OUTPUT_COLUMNS 顺序提取字段；百分比字段格式化为字符串，其余原值。"""
    dumped = features.model_dump()
    row: dict[str, Any] = {}
    for col in ALL_OUTPUT_COLUMNS:
        value = dumped.get(col)
        row[col] = format_percent(value) if col in PERCENT_FIELDS else value
    return row
