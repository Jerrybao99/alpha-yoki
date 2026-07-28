"""荐股报告纯逻辑单测。覆盖 CSV 解析、字段反序列化、LLM 上下文构建、
输出清洗（噪声剥离/回声清除/截断/回退）、CSV 写盘、常量校验。不触网络。
"""

from __future__ import annotations

from pathlib import Path

from src.data.contract import StockFeatures
from src.reports.reporting import (
    OUTPUT_HEADERS_CN,
    SCORING_KEYS,
    Top20Result,
    build_llm_context,
    clean_llm_output,
    clean_ts_code,
    load_scoring_rows,
    make_features,
    parse_back,
    write_recommend_csv,
)


def _parsed(**kw) -> dict:
    defaults = {
        "ts_code": "600000.SH",
        "symbol": "600000",
        "name": "浦发银行",
        "industry": "大消费",
        "or_yoy": 30.0,
        "netprofit_yoy": 40.0,
        "grossprofit_margin": 35.0,
        "debt_to_assets": 50.0,
        "current_ratio": 1.8,
        "roe": 18.0,
        "free_cashflow": 5.0e8,
        "eps": 1.0,
    }
    defaults.update(kw)
    return defaults


# ===== Top20Result =====
def test_top20_result_empty():
    r = Top20Result()
    assert r.rows == []


def test_top20_result_with_rows():
    r = Top20Result(rows=[{"a": "1"}])
    assert len(r.rows) == 1


# ===== clean_ts_code =====
def test_clean_ts_code_with_exchange():
    assert clean_ts_code("600000.SH") == "600000"
    assert clean_ts_code("000001.SZ") == "000001"
    assert clean_ts_code("300750.BJ") == "300750"


def test_clean_ts_code_no_suffix():
    assert clean_ts_code("600000") == "600000"


def test_clean_ts_code_zfill_padding():
    assert clean_ts_code("1309") == "001309"
    assert clean_ts_code("150.SH") == "000150"
    assert clean_ts_code("1.BJ") == "000001"


# ===== load_scoring_rows =====
def test_load_scoring_rows(tmp_path: Path):
    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "股票名称,ts_code,营业收入\n浦发银行,600000.SH,150.00亿元\n招商银行,600036.SH,200.00亿元\n",
        encoding="utf-8-sig",
    )
    rows = load_scoring_rows(csv_path)
    assert len(rows) == 2
    assert rows[0]["股票名称"] == "浦发银行"
    assert rows[1]["ts_code"] == "600036.SH"


# ===== parse_back =====
def test_parse_back_basic():
    row = {"股票名称": "浦发银行", "ts_code": "600000.SH", "营业收入": "150.00亿元"}
    result = parse_back(row)
    assert result["name"] == "浦发银行"
    assert result["ts_code"] == "600000.SH"


def test_parse_back_percent():
    row = {"归属母公司股东的净利润同比增长率": "20.00%"}
    result = parse_back(row)
    assert result["netprofit_yoy"] == 20.0


def test_parse_back_scoring_keys():
    row = {
        "\u6210\u957f\u6027": "8",
        "\u7a33\u5065\u6027": "6",
        "\u8d44\u91d1\u56de\u62a5": "10",
        "\u7efc\u5408\u5206": "8.2",
        "\u8bc4\u7ea7": "\U0001f451 \u7687\u51a0\u660e\u73e0",
    }
    result = parse_back(row)
    assert result["\u6210\u957f\u6027"] == 8.0
    assert result["\u7a33\u5065\u6027"] == 6.0
    assert result["\u8d44\u91d1\u56de\u62a5"] == 10.0
    assert result["\u7efc\u5408\u5206"] == 8.2
    assert result["\u8bc4\u7ea7"] == "\U0001f451 \u7687\u51a0\u660e\u73e0"


def test_parse_back_unknown_cn_falls_through():
    row = {"不存在的列": "hello"}
    result = parse_back(row)
    assert result["不存在的列"] == "hello"


# ===== make_features =====
def test_make_features_basic():
    p = _parsed(ts_code="600000.SH", or_yoy=30.0, roe=18.0)
    feat = make_features(p)
    assert isinstance(feat, StockFeatures)
    assert feat.ts_code == "600000.SH"
    assert feat.or_yoy == 30.0
    assert feat.roe == 18.0


def test_make_features_missing_ts_code():
    p = _parsed()
    del p["ts_code"]
    p["symbol"] = "600000"
    feat = make_features(p)
    assert feat.ts_code == "600000"


def test_make_features_extra_fields_ignored():
    p = _parsed(ts_code="999999.SH", non_existent=123)
    feat = make_features(p)
    assert feat.ts_code == "999999.SH"


# ===== build_llm_context =====
def test_build_llm_context_structure():
    ctx = build_llm_context(_parsed(), 8.0, 6.0, 10.0, 8.2, "优秀白马", "🐎 千里马")
    assert "股票代码: 600000.SH" in ctx
    assert "股票名称: 浦发银行" in ctx
    assert "行业分类: 大消费" in ctx
    assert "公司类型: 🐎 千里马" in ctx
    assert "成长性评分: 8.0 / 10" in ctx
    assert "稳健性评分: 6.0 / 10" in ctx
    assert "资金回报评分: 10.0 / 10" in ctx
    assert "综合分: 8.2 / 10" in ctx
    assert "评级: 优秀白马" in ctx


def test_build_llm_context_none_values():
    ctx = build_llm_context(_parsed(), None, None, None, None, None, None)
    assert "成长性评分: - / 10" in ctx
    assert "稳健性评分: - / 10" in ctx
    assert "资金回报评分: - / 10" in ctx
    assert "综合分: - / 10" in ctx
    assert "评级: -" in ctx
    assert "公司类型: 未知" in ctx


def test_build_llm_context_contains_financial_fields():
    ctx = build_llm_context(
        _parsed(or_yoy=30.0, netprofit_yoy=40.0, grossprofit_margin=35.0, eps=1.0),
        8,
        6,
        10,
        8.2,
        "优秀白马",
        "千里马",
    )
    assert "营业收入同比增长率（%）: 30.00" in ctx
    assert "归母净利润同比增长率（%）: 40.00" in ctx
    assert "基本每股收益（元/股）: 1.00" in ctx


def test_build_llm_context_excludes_scoring_keys():
    ctx = build_llm_context(_parsed(), 8, 6, 10, 8.2, "优秀白马", "千里马")
    assert "成长性评分" not in ctx.split("=== 关键财务指标 ===")[1]


# ===== clean_llm_output — 噪声剥离 =====
def test_clean_noise_we_bei_yaoqiu():
    text = "我们被要求用一句话总结核心亮点，30字以内。需要输出答案，不要解释。"
    result = clean_llm_output(text, 60)
    assert "我们" not in result
    assert result == "" or len(result) < len(text)


def test_clean_noise_shou_xian():
    text = "首先，要求是\u201c用一句话（30字内）指出主要风险\u201d。"
    result = clean_llm_output(text, 60)
    assert "首先" not in result or len(result) < 10


def test_clean_noise_ji_yu_shu_ju():
    text = "基于数据：成长性8，稳健性8，资金回报10，综合8。"
    result = clean_llm_output(text, 60)
    assert (
        "基于数据" not in result.split("；")[0]
        if "；" in result
        else "基于数据" not in result
    )


def test_clean_keeps_real_content():
    text = "净利润暴增2691%，净资产收益率24.4%，资金回报满分。"
    result = clean_llm_output(text, 60)
    assert "净利润" in result
    assert "净资��收益" in result or "收益率" in result


def test_clean_strips_echo_prefix():
    text = "用一句话（30字内）总结这只股票的核心亮点：营收净利双增超200%。"
    result = clean_llm_output(text, 60)
    assert "用一句话" not in result
    assert "营收" in result


def test_clean_mixed_noise_and_content():
    text = "我们需要理解任务。营收暴增9倍，利润飙升。"
    result = clean_llm_output(text, 60)
    assert "需要" not in result
    assert "营收" in result


# ===== clean_llm_output — 截断 =====
def test_clean_truncates_to_max_chars():
    text = "营收暴增9倍，净利润同比增长率高达615.38%，毛利率94.01%，ROE 23%"
    result = clean_llm_output(text, 30)
    assert len(result) <= 30


def test_clean_empty_returns_empty():
    assert clean_llm_output("", 60) == ""


def test_clean_noise_only_returns_empty_or_short():
    text = "我们被要求。基于数据。首先。"
    result = clean_llm_output(text, 60)
    assert len(result) < 20


# ===== clean_llm_output — 回退 =====
def test_clean_fallback_to_last_segment():
    text = "我们被要求概括亮点。营收暴增500%，毛利高。"
    result = clean_llm_output(text, 60)
    assert "营收" in result


def test_clean_short_clean_text_passes_through():
    text = "营收暴增9倍"
    result = clean_llm_output(text, 30)
    assert result == "营收暴增9倍"


# ===== write_recommend_csv =====
def test_write_recommend_csv(tmp_path: Path):
    result = Top20Result(
        rows=[
            {
                "股票代码": "001309",
                "股票名称": "德明利",
                "公司类型": "千里马",
                "行业分类": "大消费",
                "核心亮点": "利润高增",
                "成长性": "8",
                "稳健性": "6",
                "回报性": "10",
                "综合分": "8.2",
                "评级": "优秀白马",
                "操作建议": "分批建仓（5-10%）",
                "风险提示": "负债偏高",
                "点评": "建议买入",
            }
        ]
    )
    out = write_recommend_csv(result, tmp_path / "260728.csv")
    assert out.exists()
    content = out.read_text(encoding="utf-8-sig")
    header = content.strip().split("\n")[0].split(",")
    assert header[0] == '"股票代码"'  # QUOTE_ALL
    assert '"001309"' in content
    assert '"德明利"' in content
    assert '"利润高增"' in content


# ===== 常量校验 =====
def test_output_headers_count():
    assert len(OUTPUT_HEADERS_CN) == 13


def test_output_headers_order():
    assert OUTPUT_HEADERS_CN[0] == "股票代码"
    assert OUTPUT_HEADERS_CN[1] == "股票名称"
    assert OUTPUT_HEADERS_CN[4] == "核心亮点"
    assert OUTPUT_HEADERS_CN[9] == "评级"
    assert OUTPUT_HEADERS_CN[10] == "操作建议"
    assert OUTPUT_HEADERS_CN[11] == "风险提示"
    assert OUTPUT_HEADERS_CN[12] == "点评"


def test_scoring_keys():
    assert SCORING_KEYS == ("成长性", "稳健性", "资金回报", "综合分", "评级")
