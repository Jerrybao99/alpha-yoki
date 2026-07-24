"""CSV 报告生成与格式化。中文列头、亿/万数量级、百分比后缀、数据来源表。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.data.contract import (
    ALL_OUTPUT_COLUMNS,
    BALANCESHEET_FIELDS,
    CASHFLOW_FIELDS,
    FINA_INDICATOR_FIELDS,
    INCOME_FIELDS,
    PERCENT_FIELDS,
    REQUIREMENT_ALIGNMENT,
    STOCK_BASIC_FIELDS,
    SUPPLEMENTARY_FIELDS,
    StockFeatures,
)
from src.data.provider import TUSHARE_INTERFACES, get_vip_api_name

# 字段 → 中文显示名（先从需求对齐表/补充字段构造，再补缺口）
FIELD_CN: dict[str, str] = {}
for _a in REQUIREMENT_ALIGNMENT:
    if isinstance(_a.tushare_field, str):
        FIELD_CN[_a.tushare_field] = _a.chinese_name
    elif isinstance(_a.tushare_field, tuple):
        for _f in _a.tushare_field:
            FIELD_CN[_f] = _a.chinese_name
for _sf in SUPPLEMENTARY_FIELDS:
    FIELD_CN[_sf.tushare_field] = _sf.chinese_name
# REQUIREMENT_ALIGNMENT 未覆盖的列
FIELD_CN.update(
    {
        "ts_code": "股票代码",
        "industry": "所属分类",
        "non_oper_income": "营业外收入",
        "non_oper_exp": "营业外支出",
    }
)

# 字段 → 来源接口别名（取自各接口字段集，便于生成数据来源表）
# ts_code 在多接口均出现，按首个接口（stock_basic）为准，不后续覆写。
_FIELD_TO_INTERFACE: dict[str, str] = {}
for _iface, _fields in (
    ("stock_basic", STOCK_BASIC_FIELDS),
    ("income", INCOME_FIELDS),
    ("balancesheet", BALANCESHEET_FIELDS),
    ("cashflow", CASHFLOW_FIELDS),
    ("fina_indicator", FINA_INDICATOR_FIELDS),
):
    for _f in _fields:
        if _f not in _FIELD_TO_INTERFACE:
            _FIELD_TO_INTERFACE[_f] = _iface


# 字段单位与来源（「文档」=Tushare 文档标注；「推断」=按财务惯例推断，文档未标注）
# 实测文档仅标注：total_mv/circ_mv（万元）、float_share（万股）。其余字段文档只给中文名/定义。
_DOCUMENTED_UNITS: dict[str, str] = {}
_INFERRED_UNITS: dict[str, str] = {
    # 百分比
    "netprofit_yoy": "%",
    "or_yoy": "%",
    "grossprofit_margin": "%",
    "debt_to_assets": "%",
    "netprofit_margin": "%",
    "roe": "%",
    # 每股
    "eps": "元/股",
    "bps": "元/股",
    "ocfps": "元/股",
    "capital_rese_ps": "元/股",
    "undist_profit_ps": "元/股",
    # 倍数/比率/周转
    "current_ratio": "倍",
    "quick_ratio": "倍",
    "assets_to_eqt": "倍",
    "ocf_to_shortdebt": "比率",
    "inv_turn": "次",
    # 股本
    "total_share": "股",
    # 金额（元）
    "revenue": "元",
    "operate_profit": "元",
    "invest_income": "元",
    "non_oper_income": "元",
    "non_oper_exp": "元",
    "total_profit": "元",
    "n_income_attr_p": "元",
    "undistr_porfit": "元",
    "total_assets": "元",
    "total_cur_assets": "元",
    "fix_assets": "元",
    "intan_assets": "元",
    "total_liab": "元",
    "total_cur_liab": "元",
    "total_ncl": "元",
    "total_hldr_eqy_exc_min_int": "元",
    "cap_rese": "元",
    "money_cap": "元",
    "n_cashflow_act": "元",
    "n_cashflow_inv_act": "元",
    "n_cash_flows_fnc_act": "元",
    "n_incr_cash_cash_equ": "元",
    "free_cashflow": "元",
}


def _unit_of(field: str) -> tuple[str, str]:
    """返回 (单位, 来源)；文档已标注返回「文档」，否则按语义推断返回「推断」。"""
    if field in _DOCUMENTED_UNITS:
        return _DOCUMENTED_UNITS[field], "文档"
    if field in _INFERRED_UNITS:
        return _INFERRED_UNITS[field], "推断"
    return "—", "—"


# 原始单位已为「万」的字段（Tushare 文档标注）。已全部删除，空集保留占位。
_RAW_WAN_FIELDS: frozenset[str] = frozenset()


def format_value(field: str, value: Any) -> str:
    """按数据来源 CSV 中记录的单位格式化单元格。

    规则（对齐 ``data/test/YYMMDD-数据来源.csv`` 单位列）：
    - None → 空串
    - ``%`` → 两位小数 + %
    - ``倍/次/元/股`` → 两位小数 + 单位，不做数量级缩放
    - ``比率`` → 两位小数，无后缀
    - ``元`` → 亿/万 数量级 + 元
    - ``万元``（total_mv/circ_mv）→ 万→亿换算（÷1e4） + 元
    - ``万股``（float_share）→ 万→亿换算（÷1e4），数量级即单位
    - ``股``（total_share）→ 亿/万 数量级
    - 无单位/未知 → 亿/万 数量级
    """
    if value is None:
        return ""
    if field in PERCENT_FIELDS:
        return f"{float(value):.2f}%"
    if isinstance(value, (int, float)):
        v = float(value)
        unit, _source = _unit_of(field)

        # _RAW_WAN_FIELDS：原始单位已为「万」，换算到亿除以 1e4
        if field in _RAW_WAN_FIELDS:
            if abs(v) >= 1e4:
                if unit == "万元":
                    return f"{v / 1e4:.2f}亿元"
                return f"{v / 1e4:.2f}亿"
            return f"{v:.2f}{unit}"

        # 不缩放的固定单位
        if unit == "%":
            return f"{v:.2f}%"
        if unit in ("倍", "次", "元/股"):
            return f"{v:.2f}{unit}"
        if unit == "比率":
            return f"{v:.2f}"

        # 可缩放的金额/股份类字段
        if abs(v) >= 1e8:
            scaled, mag = v / 1e8, "亿"
        elif abs(v) >= 1e4:
            scaled, mag = v / 1e4, "万"
        else:
            scaled, mag = v, ""

        if unit == "元":
            return f"{scaled:.2f}{mag}元"
        if unit == "股":
            return f"{scaled:.2f}{mag}股"
        # 无单位或未知
        return f"{scaled:.2f}{mag}" if mag else f"{scaled:.2f}"
    return str(value)


def write_features_csv(features: list[StockFeatures], out_path: Path) -> Path:
    """写特征数据 CSV：中文列头 + 格式化值（不做宽度填充，Excel 双击列边界即可自适应）。"""
    headers = [FIELD_CN[c] for c in ALL_OUTPUT_COLUMNS]
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
    except PermissionError:
        import shutil
        import tempfile

        tmp = Path(tempfile.mktemp(suffix=".csv", prefix=out_path.stem + "_"))
        tmp.write_text(content, encoding="utf-8-sig")
        shutil.copy(tmp, out_path.with_suffix(".csv.tmp"))
        print(f"⚠ 目标文件被占用，已写到临时文件: {out_path.with_suffix('.csv.tmp')}")
    return out_path


def write_data_source_csv(out_path: Path) -> Path:
    """写数据来源 CSV：接口/字段/字段中文/单位/单位来源/文档URL。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["接口,字段,字段中文,单位,单位来源,文档URL"]
    for field in ALL_OUTPUT_COLUMNS:
        iface_key = _FIELD_TO_INTERFACE.get(field)
        if iface_key is None:
            continue
        iface = TUSHARE_INTERFACES[iface_key]
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
    """按 ALL_OUTPUT_COLUMNS 顺序提取字段；百分比字段格式化为字符串，其余原值。

    保证写盘列与 §8.1 字段契约一致，不缺列、不多列。
    """
    dumped = features.model_dump()
    row: dict[str, Any] = {}
    for col in ALL_OUTPUT_COLUMNS:
        value = dumped.get(col)
        row[col] = format_percent(value) if col in PERCENT_FIELDS else value
    return row
