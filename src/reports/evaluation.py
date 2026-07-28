"""公司类型分类与操作建议规则引擎：classify_company_type 按 §8.7/§8.8 判断
千里马/现金牛/护城河，get_advice 按 §8.9 映射评级→操作建议与仓位。纯函数，不调 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.contract import StockFeatures

CAT_CYCLICAL = "周期资源"
CAT_CONSUMER = "大消费"
CAT_FINANCIAL = "证券金融"
CAT_TECH = "科技/制造"
CAT_UTILITY = "公用事业/基建"

TYPE_QIANLIMA = "\U0001f40e 千里马"
TYPE_XIANJINNIU = "\U0001f42e 现金牛"
TYPE_HUCHENGHE = "\U0001f6e1 护城河"

_DEFAULT_TYPES: dict[str, str] = {
    CAT_CYCLICAL: TYPE_XIANJINNIU,
    CAT_CONSUMER: TYPE_HUCHENGHE,
    CAT_FINANCIAL: TYPE_HUCHENGHE,
    CAT_TECH: TYPE_QIANLIMA,
    CAT_UTILITY: TYPE_XIANJINNIU,
}


@dataclass(frozen=True)
class CompanyTypeResult:
    type_label: str
    detail: str

    @property
    def growth_weight(self) -> float:
        if self.type_label == TYPE_QIANLIMA:
            return 0.50
        if self.type_label == TYPE_HUCHENGHE:
            return 0.30
        return 0.20

    @property
    def stability_weight(self) -> float:
        if self.type_label == TYPE_QIANLIMA:
            return 0.20
        if self.type_label == TYPE_HUCHENGHE:
            return 0.30
        return 0.40

    @property
    def return_weight(self) -> float:
        return 0.40


def classify_company_type(
    f: StockFeatures, industry: str | None = None
) -> CompanyTypeResult:
    """按 §8.7/§8.8 判断公司类型。行业优先，辅以财务指标微调。

    Args:
        f: 单股特征数据。
        industry: SW 五大类标签；None 时取 f.industry。

    Returns:
        CompanyTypeResult(type_label, detail)，含对应的成长/稳健/回报权重。
    """
    ind = (industry or f.industry or "").strip()
    default = _DEFAULT_TYPES.get(ind, TYPE_XIANJINNIU)

    or_yoy = f.or_yoy
    gross_margin = f.grossprofit_margin
    roe = f.roe

    # 科技/制造行业的 千里马 若无高增长可降为 现金牛
    if default == TYPE_QIANLIMA and or_yoy is not None and or_yoy < 15.0:
        return CompanyTypeResult(
            TYPE_XIANJINNIU, f"营收增速 {or_yoy:.1f}% 低于 15%，从千里马转为现金牛"
        )
    # 周期资源景气爆发 → 千里马
    if ind == CAT_CYCLICAL and or_yoy is not None and or_yoy > 30.0:
        return CompanyTypeResult(
            TYPE_QIANLIMA, f"营收增速 {or_yoy:.1f}% >30%，景气爆发期视为千里马"
        )
    # 消费/金融行业 若有 千里马 特质 → 千里马
    if default == TYPE_HUCHENGHE and or_yoy is not None and or_yoy > 15.0:
        return CompanyTypeResult(
            TYPE_QIANLIMA, f"营收增速 {or_yoy:.1f}% >15%，视为千里马"
        )
    # 公用事业扩张期 → 千里马
    if ind == CAT_UTILITY and or_yoy is not None and or_yoy > 20.0:
        return CompanyTypeResult(
            TYPE_QIANLIMA, f"营收增速 {or_yoy:.1f}% >20%，扩张期视为千里马"
        )
    # 护城河需验证品牌溢价（高毛利）；缺指标时保留默认分类
    if default == TYPE_HUCHENGHE:
        if gross_margin is not None and gross_margin > 50.0:
            return CompanyTypeResult(
                TYPE_HUCHENGHE, f"毛利率 {gross_margin:.1f}% >50%，品牌溢价显著"
            )
        if roe is not None and roe > 25.0:
            return CompanyTypeResult(
                TYPE_HUCHENGHE, f"ROE {roe:.1f}% >25%，抗通胀能力强"
            )
        if gross_margin is not None and roe is not None:
            return CompanyTypeResult(
                TYPE_XIANJINNIU, "毛利与ROE未达护城河标准，转为现金牛"
            )
        return CompanyTypeResult(
            TYPE_HUCHENGHE, f"行业 {ind} 默认分类（指标缺失暂保留）"
        )

    return CompanyTypeResult(default, f"行业 {ind} 默认分类")


@dataclass(frozen=True)
class AdviceResult:
    advice: str
    position: str
    action: str


_RATINGS_ADVICE: dict[str, AdviceResult] = {
    "\U0001f451 皇冠明珠": AdviceResult("重仓买入", "10-20%", "buy"),
    "\u2b50 优秀白马": AdviceResult("分批建仓", "5-10%", "accumulate"),
    "\U0001f504 鸡肋\u00b7观察": AdviceResult("观望/波段", "<3%", "hold"),
    "\u26a0\ufe0f 垃圾": AdviceResult("坚决回避", "0%", "avoid"),
}


def get_advice(rating: str) -> AdviceResult:
    """评级 → 操作建议与仓位建议（§8.9）。纯函数，直接查表映射。"""
    if rating in _RATINGS_ADVICE:
        return _RATINGS_ADVICE[rating]
    return AdviceResult("谨慎观望", "<5%", "hold")
