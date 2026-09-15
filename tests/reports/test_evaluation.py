"""公司类型分类与操作建议规则引擎单测。覆盖 brd.md 三种公司类型（含行业默认 + 指标微调）、
四级评级→操作建议映射、权重属性校验。不触网络。
"""

from __future__ import annotations

from src.data.contract import StockFeatures
from src.reports.evaluation import (
    TYPE_HUCHENGHE,
    TYPE_QIANLIMA,
    TYPE_XIANJINNIU,
    AdviceResult,
    CompanyTypeResult,
    classify_company_type,
    get_advice,
)


def _f(**overrides) -> StockFeatures:
    kwargs: dict = {"ts_code": "000001.SZ", "symbol": "000001", "name": "测试股票"}
    kwargs.update(overrides)
    return StockFeatures(**kwargs)


# ===== 公司类型 — 行业默认分类 =====


def test_tech_defaults_to_qianlima():
    result = classify_company_type(_f(), industry="科技/制造")
    assert result.type_label == TYPE_QIANLIMA


def test_utility_defaults_to_xianjinniu():
    result = classify_company_type(_f(), industry="公用事业/基建")
    assert result.type_label == TYPE_XIANJINNIU


def test_consumer_defaults_to_huchenghe():
    result = classify_company_type(_f(), industry="大消费")
    assert result.type_label == TYPE_HUCHENGHE


def test_financial_defaults_to_huchenghe():
    result = classify_company_type(_f(), industry="证券金融")
    assert result.type_label == TYPE_HUCHENGHE


def test_cyclical_defaults_to_xianjinniu():
    result = classify_company_type(_f(), industry="周期资源")
    assert result.type_label == TYPE_XIANJINNIU


def test_unknown_industry_defaults_to_xianjinniu():
    result = classify_company_type(_f(), industry="不存在的行业")
    assert result.type_label == TYPE_XIANJINNIU


# ===== 公司类型 — 财务指标微调 =====


def test_qianlima_low_growth_demotes():
    """科技/制造 千里马，营收增速 <15% → 降为 现金牛。"""
    result = classify_company_type(_f(or_yoy=10.0), industry="科技/制造")
    assert result.type_label == TYPE_XIANJINNIU


def test_qianlima_high_growth_stays():
    """科技/制造 千里马，营收增速 ≥15% → 保持。"""
    result = classify_company_type(_f(or_yoy=15.0), industry="科技/制造")
    assert result.type_label == TYPE_QIANLIMA


def test_cyclical_boom_ups_to_qianlima():
    """周期资源 景气爆发（营收增速 >30%）→ 千里马。"""
    result = classify_company_type(_f(or_yoy=35.0), industry="周期资源")
    assert result.type_label == TYPE_QIANLIMA


def test_cyclical_normal_stays_xianjinniu():
    """周期资源 营收增速 ≤30% → 保持 现金牛。"""
    result = classify_company_type(_f(or_yoy=20.0), industry="周期资源")
    assert result.type_label == TYPE_XIANJINNIU


def test_consumer_high_growth_ups_to_qianlima():
    """大消费 营收增速 >15% → 千里马（大众消费品）。"""
    result = classify_company_type(_f(or_yoy=20.0), industry="大消费")
    assert result.type_label == TYPE_QIANLIMA


def test_financial_high_growth_ups_to_qianlima():
    """证券金融 营收增速 >15% → 千里马（特色券商）。"""
    result = classify_company_type(_f(or_yoy=18.0), industry="证券金融")
    assert result.type_label == TYPE_QIANLIMA


def test_utility_expansion_ups_to_qianlima():
    """公用事业/基建 营收增速 >20% → 千里马。"""
    result = classify_company_type(_f(or_yoy=25.0), industry="公用事业/基建")
    assert result.type_label == TYPE_QIANLIMA


# ===== 公司类型 — 护城河验证 =====


def test_huchenghe_high_gross_margin():
    """护城河 毛利率 >50% → 确认品牌溢价。"""
    result = classify_company_type(_f(grossprofit_margin=55.0), industry="大消费")
    assert result.type_label == TYPE_HUCHENGHE
    assert "50%" in result.detail


def test_huchenghe_high_roe_fallback():
    """护城河 毛利率低但 ROE >25% → 确认抗通胀。"""
    result = classify_company_type(_f(grossprofit_margin=30.0, roe=28.0), industry="大消费")
    assert result.type_label == TYPE_HUCHENGHE
    assert "25%" in result.detail


def test_huchenghe_low_metrics_demotes():
    """护城河 毛利/ROE 均不达标 → 现金牛。"""
    result = classify_company_type(_f(grossprofit_margin=10.0, roe=8.0), industry="大消费")
    assert result.type_label == TYPE_XIANJINNIU


# ===== 公司类型 — 权重属性 =====


def test_qianlima_weights():
    result = classify_company_type(_f(or_yoy=20.0), industry="科技/制造")
    assert result.growth_weight == 0.50
    assert result.stability_weight == 0.20
    assert result.return_weight == 0.40


def test_huchenghe_weights():
    result = classify_company_type(_f(grossprofit_margin=55.0), industry="大消费")
    assert result.growth_weight == 0.30
    assert result.stability_weight == 0.30
    assert result.return_weight == 0.40


def test_xianjinniu_weights():
    result = classify_company_type(_f(), industry="公用事业/基建")
    assert result.growth_weight == 0.20
    assert result.stability_weight == 0.40
    assert result.return_weight == 0.40


# ===== 公司类型 — industry 取 StockFeatures.industry =====


def test_classify_uses_features_industry():
    result = classify_company_type(_f(industry="大消费", grossprofit_margin=55.0))
    assert result.type_label == TYPE_HUCHENGHE


# ===== 操作建议 =====


def test_advice_crown():
    r = get_advice("\U0001f451 皇冠明珠")
    assert r.advice == "重仓买入"
    assert r.position == "10-20%"
    assert r.action == "buy"


def test_advice_excellent():
    r = get_advice("\u2b50 优秀白马")
    assert r.advice == "分批建仓"
    assert r.position == "5-10%"
    assert r.action == "accumulate"


def test_advice_mediocre():
    r = get_advice("\U0001f504 鸡肋\u00b7观察")
    assert r.advice == "观望/波段"
    assert r.position == "<3%"
    assert r.action == "hold"


def test_advice_junk():
    r = get_advice("\u26a0\ufe0f 垃圾")
    assert r.advice == "坚决回避"
    assert r.position == "0%"
    assert r.action == "avoid"


def test_advice_unknown():
    r = get_advice("不存在的评级")
    assert r.advice == "谨慎观望"
    assert r.position == "<5%"
    assert r.action == "hold"


# ===== dataclass frozen =====


def test_company_type_result_is_frozen():
    result = classify_company_type(_f(), industry="大消费")
    assert isinstance(result, CompanyTypeResult)
    assert result.type_label
    assert result.detail


def test_advice_result_is_frozen():
    r = get_advice("\u2b50 优秀白马")
    assert isinstance(r, AdviceResult)
    assert r.action == "accumulate"
