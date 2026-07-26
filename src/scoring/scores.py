"""三维评分纯函数 + 综合分 + 一票否决：成长性/稳健性/资金回报，基于 StockFeatures 真实字段按 dev-guide §8.3 阈值评分。
每维度按五档（1-2/3-4/5-6/7-8/9-10）取档位中点，多维度平均后四舍五入得 1-10 整数分。
综合分按 §8.4/§8.5 行业权重加权求和，保留 1 位小数。
一票否决按 §8.2 规则，返回触发的否决项列表（空列表表示通过）。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.contract import StockFeatures


def _round_score(scores: list[float]) -> int:
    """多维度档位中点平均后四舍五入，钳位 1-10；无有效维度返回 5。"""
    if not scores:
        return 5
    return max(1, min(10, round(sum(scores) / len(scores))))


def score_growth(f: StockFeatures) -> int:
    """成长性评分（1-10）。

    四维度：营收增速(or_yoy) / 净利增速(netprofit_yoy) / 盈利质量(grossprofit_margin) / 现金流匹配(ocfps/eps)。
    缺失维度自动跳过；eps 为 0 时跳过现金流匹配维度避免除零。
    """
    dims: list[float] = []

    v = f.or_yoy
    if v is not None:
        if v > 40.0:
            dims.append(9.5)
        elif v >= 25.0:
            dims.append(7.5)
        elif v >= 15.0:
            dims.append(5.5)
        elif v >= 5.0:
            dims.append(3.5)
        else:
            dims.append(1.5)

    v = f.netprofit_yoy
    if v is not None:
        if v > 50.0:
            dims.append(9.5)
        elif v >= 30.0:
            dims.append(7.5)
        elif v >= 15.0:
            dims.append(5.5)
        elif v >= 0.0:
            dims.append(3.5)
        else:
            dims.append(1.5)

    v = f.grossprofit_margin
    if v is not None:
        if v > 50.0:
            dims.append(9.5)
        elif v >= 30.0:
            dims.append(7.5)
        elif v >= 15.0:
            dims.append(5.5)
        elif v >= 5.0:
            dims.append(3.5)
        else:
            dims.append(1.5)

    if f.ocfps is not None and f.eps is not None and f.eps != 0:
        r = f.ocfps / f.eps
        if r > 1.2:
            dims.append(9.5)
        elif r >= 1.0:
            dims.append(7.5)
        elif r >= 0.8:
            dims.append(5.5)
        elif r >= 0.5:
            dims.append(3.5)
        else:
            dims.append(1.5)

    return _round_score(dims)


def score_stability(f: StockFeatures) -> int:
    """稳健性评分（1-10）。

    三维度：资产负债率(debt_to_assets) / 流动比率(current_ratio) / 存货周转率(inv_turn)。
    审计意见暂不可用；缺失维度自动跳过。
    """
    dims: list[float] = []

    v = f.debt_to_assets
    if v is not None:
        if v > 85.0:
            dims.append(1.5)
        elif v >= 75.0:
            dims.append(3.5)
        elif v >= 60.0:
            dims.append(5.5)
        elif v >= 40.0:
            dims.append(7.5)
        else:
            dims.append(9.5)

    v = f.current_ratio
    if v is not None:
        if v > 2.5:
            dims.append(9.5)
        elif v >= 1.5:
            dims.append(7.5)
        elif v >= 1.0:
            dims.append(5.5)
        elif v >= 0.5:
            dims.append(3.5)
        else:
            dims.append(1.5)

    v = f.inv_turn
    if v is not None:
        if v > 10.0:
            dims.append(9.5)
        elif v >= 5.0:
            dims.append(7.5)
        elif v >= 2.0:
            dims.append(5.5)
        elif v >= 1.0:
            dims.append(3.5)
        else:
            dims.append(1.5)

    return _round_score(dims)


def score_return(f: StockFeatures) -> int:
    """资金回报评分（1-10）。

    二维度：ROE(roe) / 自由现金流(free_cashflow 按总资产归一化)。
    分红率/PEG 暂不可用；缺失维度自动跳过。
    """
    dims: list[float] = []

    v = f.roe
    if v is not None:
        if v > 20.0:
            dims.append(9.5)
        elif v >= 15.0:
            dims.append(7.5)
        elif v >= 10.0:
            dims.append(5.5)
        elif v >= 6.0:
            dims.append(3.5)
        else:
            dims.append(1.5)

    v = f.free_cashflow
    if v is not None:
        if f.total_assets is not None and f.total_assets > 0:
            r = v / f.total_assets
            if r > 0.10:
                dims.append(9.5)
            elif r >= 0.03:
                dims.append(7.5)
            elif r >= 0.0:
                dims.append(5.5)
            elif r >= -0.03:
                dims.append(3.5)
            else:
                dims.append(1.5)
        else:
            if v > 1_000_000_000:
                dims.append(7.5)
            elif v > 0:
                dims.append(5.5)
            else:
                dims.append(3.5)

    return _round_score(dims)


@dataclass(frozen=True)
class VetoTrigger:
    """一票否决触发记录（审计可追溯，dev-guide §8.2）。"""

    rule: str
    reason: str


def check_veto(f: StockFeatures) -> list[VetoTrigger]:
    """一票否决检查（§8.2）。返回触发的否决项列表，空列表表示通过。

    已实现：
    - 造假嫌疑（货币资金异常）：货币资金 > 1 亿 且 占总资产 > 30%

    待实现（需额外数据源或定性判断）：
    - 造假嫌疑（经营现金流连续多年低于净利润）
    - 行业毁灭
    - 诚信问题（审计机构变更 / 质押率 / 信披违规）
    """
    triggers: list[VetoTrigger] = []

    mc = f.money_cap
    ta = f.total_assets
    if mc is not None and ta is not None and ta > 0 and mc > 1e8 and mc / ta > 0.30:
        triggers.append(
            VetoTrigger(
                rule="造假嫌疑",
                reason=f"货币资金占比异常（{mc / ta:.1%}），需核查利息收入是否匹配",
            )
        )

    return triggers


_INDUSTRY_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "周期资源": (0.25, 0.35, 0.40),
    "大消费": (0.30, 0.30, 0.40),
    "证券金融": (0.30, 0.30, 0.40),
    "科技/制造": (0.50, 0.20, 0.30),
    "公用事业/基建": (0.20, 0.40, 0.40),
}

_DEFAULT_WEIGHTS: tuple[float, float, float] = (0.333, 0.333, 0.334)


def score_composite(
    growth: int,
    stability: int,
    return_: int,
    industry: str,
) -> float:
    """综合分 = 成长分×行业成长权重 + 稳健分×行业稳健权重 + 回报分×行业回报权重。

    dev-guide §8.4 行业权重区间取中点；未知行业默认三等分。
    返回保留 1 位小数。
    """
    gw, sw, rw = _INDUSTRY_WEIGHTS.get(industry, _DEFAULT_WEIGHTS)
    return round(growth * gw + stability * sw + return_ * rw, 1)
