"""三维评分纯函数单测：覆盖 §8.3 全部维度阈值边界与缺失字段容错。"""

from __future__ import annotations

from src.data.contract import StockFeatures
from src.scoring.scores import (
    VetoTrigger,
    check_veto,
    score_composite,
    score_growth,
    score_return,
    score_stability,
)


def _f(**overrides) -> StockFeatures:
    """构建测试用 StockFeatures，未指定字段默认 None。"""
    kwargs: dict = {"ts_code": "000001.SZ", "symbol": "000001", "name": "测试股票"}
    kwargs.update(overrides)
    return StockFeatures(**kwargs)


# ============================================================================
#  成长性 §8.3.1
# ============================================================================


class TestGrowthRevenue:
    """营收增速(or_yoy) 阈值边界。"""

    def test_above_40(self):
        assert score_growth(_f(or_yoy=40.1)) == 10

    def test_at_25(self):
        assert score_growth(_f(or_yoy=25.0)) == 8

    def test_between_25_and_40(self):
        assert score_growth(_f(or_yoy=32.0)) == 8

    def test_at_15(self):
        assert score_growth(_f(or_yoy=15.0)) == 6

    def test_at_5(self):
        assert score_growth(_f(or_yoy=5.0)) == 4

    def test_below_5(self):
        assert score_growth(_f(or_yoy=4.9)) == 2

    def test_negative(self):
        assert score_growth(_f(or_yoy=-10.0)) == 2

    def test_none_skipped(self):
        assert score_growth(_f(or_yoy=None)) == 5


class TestGrowthProfit:
    """净利增速(netprofit_yoy) 阈值边界。"""

    def test_above_50(self):
        assert score_growth(_f(netprofit_yoy=50.1)) == 10

    def test_at_30(self):
        assert score_growth(_f(netprofit_yoy=30.0)) == 8

    def test_at_15(self):
        assert score_growth(_f(netprofit_yoy=15.0)) == 6

    def test_at_0(self):
        assert score_growth(_f(netprofit_yoy=0.0)) == 4

    def test_negative(self):
        assert score_growth(_f(netprofit_yoy=-5.0)) == 2

    def test_none_skipped(self):
        assert score_growth(_f(netprofit_yoy=None)) == 5


class TestGrowthMargin:
    """盈利质量(grossprofit_margin) 阈值边界。"""

    def test_above_50(self):
        assert score_growth(_f(grossprofit_margin=50.1)) == 10

    def test_at_30(self):
        assert score_growth(_f(grossprofit_margin=30.0)) == 8

    def test_at_15(self):
        assert score_growth(_f(grossprofit_margin=15.0)) == 6

    def test_at_5(self):
        assert score_growth(_f(grossprofit_margin=5.0)) == 4

    def test_below_5(self):
        assert score_growth(_f(grossprofit_margin=4.9)) == 2

    def test_none_skipped(self):
        assert score_growth(_f(grossprofit_margin=None)) == 5


class TestGrowthCashflow:
    """现金流匹配(ocfps/eps) 阈值边界。"""

    def test_above_1_2(self):
        assert score_growth(_f(ocfps=1.21, eps=1.0)) == 10

    def test_at_1_0(self):
        assert score_growth(_f(ocfps=1.0, eps=1.0)) == 8

    def test_at_0_8(self):
        assert score_growth(_f(ocfps=0.8, eps=1.0)) == 6

    def test_at_0_5(self):
        assert score_growth(_f(ocfps=0.5, eps=1.0)) == 4

    def test_below_0_5(self):
        assert score_growth(_f(ocfps=0.49, eps=1.0)) == 2

    def test_eps_zero_skips(self):
        assert score_growth(_f(or_yoy=30.0, ocfps=2.0, eps=0.0)) == 8

    def test_eps_none_skips(self):
        assert score_growth(_f(or_yoy=30.0, ocfps=2.0, eps=None)) == 8

    def test_ocfps_none_skips(self):
        assert score_growth(_f(or_yoy=30.0, ocfps=None, eps=1.0)) == 8


class TestGrowthComposite:
    """成长性综合分：多维度平均与边界。"""

    def test_all_dims_avg(self):
        f = _f(
            or_yoy=30.0, netprofit_yoy=40.0, grossprofit_margin=35.0, ocfps=2.0, eps=1.0
        )
        assert score_growth(f) == 8  # (7.5+7.5+7.5+9.5)/4=8.0

    def test_all_dims_none_returns_5(self):
        assert score_growth(_f()) == 5

    def test_round_up(self):
        assert (
            score_growth(_f(or_yoy=30.0, netprofit_yoy=40.0, grossprofit_margin=35.0))
            == 8
        )  # (7.5+7.5+7.5)/3=7.5→8

    def test_round_down(self):
        assert (
            score_growth(_f(or_yoy=15.0, netprofit_yoy=15.0, grossprofit_margin=15.0))
            == 6
        )  # (5.5*3)/3=5.5→6

    def test_single_dim(self):
        assert score_growth(_f(or_yoy=10.0)) == 4

    def test_min_score_is_2(self):
        assert (
            score_growth(
                _f(
                    or_yoy=-100.0,
                    netprofit_yoy=-100.0,
                    grossprofit_margin=0.0,
                    ocfps=0.1,
                    eps=1.0,
                )
            )
            == 2
        )

    def test_max_score_is_10(self):
        assert (
            score_growth(
                _f(
                    or_yoy=1000.0,
                    netprofit_yoy=1000.0,
                    grossprofit_margin=100.0,
                    ocfps=100.0,
                    eps=1.0,
                )
            )
            == 10
        )

    def test_two_dims_mixed(self):
        assert (
            score_growth(
                _f(
                    or_yoy=30.0,
                    netprofit_yoy=20.0,
                    grossprofit_margin=None,
                    ocfps=None,
                    eps=None,
                )
            )
            == 6
        )


# ============================================================================
#  稳健性 §8.3.2
# ============================================================================


class TestStabilityDebt:
    """资产负债率(debt_to_assets) 阈值边界（越低越好）。"""

    def test_above_85(self):
        assert score_stability(_f(debt_to_assets=85.1)) == 2

    def test_at_75(self):
        assert score_stability(_f(debt_to_assets=75.0)) == 4

    def test_at_60(self):
        assert score_stability(_f(debt_to_assets=60.0)) == 6

    def test_at_40(self):
        assert score_stability(_f(debt_to_assets=40.0)) == 8

    def test_below_40(self):
        assert score_stability(_f(debt_to_assets=30.0)) == 10

    def test_none_skipped(self):
        assert score_stability(_f(debt_to_assets=None)) == 5


class TestStabilityCurrentRatio:
    """流动比率(current_ratio) 阈值边界。"""

    def test_above_2_5(self):
        assert score_stability(_f(current_ratio=2.51)) == 10

    def test_at_1_5(self):
        assert score_stability(_f(current_ratio=1.5)) == 8

    def test_at_1_0(self):
        assert score_stability(_f(current_ratio=1.0)) == 6

    def test_at_0_5(self):
        assert score_stability(_f(current_ratio=0.5)) == 4

    def test_below_0_5(self):
        assert score_stability(_f(current_ratio=0.49)) == 2

    def test_none_skipped(self):
        assert score_stability(_f(current_ratio=None)) == 5


class TestStabilityInvTurn:
    """存货周转率(inv_turn) 阈值边界。"""

    def test_above_10(self):
        assert score_stability(_f(inv_turn=10.1)) == 10

    def test_at_5(self):
        assert score_stability(_f(inv_turn=5.0)) == 8

    def test_at_2(self):
        assert score_stability(_f(inv_turn=2.0)) == 6

    def test_at_1(self):
        assert score_stability(_f(inv_turn=1.0)) == 4

    def test_below_1(self):
        assert score_stability(_f(inv_turn=0.99)) == 2

    def test_none_skipped(self):
        assert score_stability(_f(inv_turn=None)) == 5


class TestStabilityComposite:
    """稳健性综合分：多维度平均与边界。"""

    def test_all_dims_none_returns_5(self):
        assert score_stability(_f()) == 5

    def test_all_dims_avg(self):
        f = _f(debt_to_assets=50.0, current_ratio=1.8, inv_turn=6.0)
        assert score_stability(f) == 8  # (7.5+7.5+7.5)/3=7.5→8

    def test_mixed(self):
        f = _f(debt_to_assets=70.0, current_ratio=1.2, inv_turn=2.5)
        assert score_stability(f) == 6  # (5.5+5.5+5.5)/3=5.5→6

    def test_min_score_is_2(self):
        assert (
            score_stability(_f(debt_to_assets=99.0, current_ratio=0.1, inv_turn=0.1))
            == 2
        )

    def test_max_score_is_10(self):
        assert (
            score_stability(
                _f(debt_to_assets=10.0, current_ratio=100.0, inv_turn=999.0)
            )
            == 10
        )

    def test_round_up_boundary(self):
        f = _f(debt_to_assets=50.0, current_ratio=2.0)
        assert score_stability(f) == 8  # (7.5+7.5)/2=7.5→8

    def test_round_down_boundary(self):
        f = _f(debt_to_assets=70.0, current_ratio=1.0)
        assert score_stability(f) == 6  # (5.5+5.5)/2=5.5→6


# ============================================================================
#  资金回报 §8.3.3
# ============================================================================


class TestReturnROE:
    """ROE(roe) 阈值边界。"""

    def test_above_20(self):
        assert score_return(_f(roe=20.1)) == 10

    def test_at_15(self):
        assert score_return(_f(roe=15.0)) == 8

    def test_at_10(self):
        assert score_return(_f(roe=10.0)) == 6

    def test_at_6(self):
        assert score_return(_f(roe=6.0)) == 4

    def test_below_6(self):
        assert score_return(_f(roe=5.9)) == 2

    def test_negative(self):
        assert score_return(_f(roe=-5.0)) == 2

    def test_none_skipped(self):
        assert score_return(_f(roe=None)) == 5


class TestReturnFreeCashflow:
    """自由现金流(free_cashflow) 归一化阈值边界。"""

    def test_normalized_above_0_10(self):
        assert (
            score_return(_f(free_cashflow=2.0e9, total_assets=1.0e10)) == 10
        )  # 0.20>0.10

    def test_normalized_at_0_03(self):
        assert score_return(_f(free_cashflow=3.0e8, total_assets=1.0e10)) == 8

    def test_normalized_between_0_03_and_0_10(self):
        assert score_return(_f(free_cashflow=5.0e8, total_assets=1.0e10)) == 8

    def test_normalized_between_0_and_0_03(self):
        assert (
            score_return(_f(free_cashflow=1.0e8, total_assets=1.0e10)) == 6
        )  # 0.01→5.5→6

    def test_normalized_zero(self):
        assert score_return(_f(free_cashflow=0.0, total_assets=1.0e10)) == 6

    def test_normalized_negative(self):
        assert (
            score_return(_f(free_cashflow=-1.0e8, total_assets=1.0e10)) == 4
        )  # -0.01→3.5→4

    def test_normalized_very_negative(self):
        assert (
            score_return(_f(free_cashflow=-1.0e9, total_assets=1.0e10)) == 2
        )  # -0.1→1.5→2

    def test_no_total_assets_positive_large(self):
        assert (
            score_return(_f(free_cashflow=2.0e9, total_assets=None)) == 8
        )  # >10亿→7.5→8

    def test_no_total_assets_positive_small(self):
        assert score_return(_f(free_cashflow=1.0e8, total_assets=None)) == 6  # >0→5.5→6

    def test_no_total_assets_negative(self):
        assert (
            score_return(_f(free_cashflow=-1.0e8, total_assets=None)) == 4
        )  # ≤0→3.5→4

    def test_total_assets_zero_falls_back(self):
        assert score_return(_f(free_cashflow=2.0e9, total_assets=0.0)) == 8

    def test_fcf_none_skipped(self):
        assert score_return(_f(free_cashflow=None)) == 5


class TestReturnComposite:
    """资金回报综合分：多维度平均与边界。"""

    def test_all_dims_none_returns_5(self):
        assert score_return(_f()) == 5

    def test_roe_and_fcf_avg(self):
        f = _f(roe=18.0, free_cashflow=5.0e8, total_assets=1.0e10)
        assert score_return(f) == 8

    def test_round_up(self):
        f = _f(roe=18.0, free_cashflow=1.0e8, total_assets=1.0e10)
        assert score_return(f) == 6

    def test_round_down(self):
        f = _f(roe=7.0, free_cashflow=1.0e8, total_assets=1.0e10)
        assert score_return(f) == 4

    def test_max_score_is_10(self):
        assert (
            score_return(_f(roe=100.0, free_cashflow=1.0e12, total_assets=1.0e10)) == 10
        )

    def test_min_score_is_2(self):
        assert (
            score_return(_f(roe=-100.0, free_cashflow=-1.0e12, total_assets=1.0e10))
            == 2
        )


# ============================================================================
#  综合分 §8.4 / §8.5
# ============================================================================


def test_composite_cyclical():
    assert score_composite(8, 8, 8, "周期资源") == 8.0  # 8×0.25+8×0.35+8×0.40


def test_composite_tech():
    assert score_composite(10, 6, 8, "科技/制造") == 8.6  # 10×0.50+6×0.20+8×0.30


def test_composite_utility():
    assert score_composite(5, 8, 8, "公用事业/基建") == 7.4  # 5×0.20+8×0.40+8×0.40


def test_composite_consumer():
    assert score_composite(6, 7, 9, "大消费") == 7.5  # 6×0.30+7×0.30+9×0.40


def test_composite_financial():
    assert score_composite(7, 8, 6, "证券金融") == 6.9  # 7×0.30+8×0.30+6×0.40


def test_composite_unknown_industry():
    assert score_composite(8, 8, 8, "不存在的行业") == round(
        8 * 0.333 + 8 * 0.333 + 8 * 0.334, 1
    )


def test_composite_one_decimal():
    result = score_composite(7, 8, 9, "大消费")
    assert result == round(result, 1)
    assert len(str(result).split(".")[1]) <= 1


# ============================================================================
#  一票否决 §8.2
# ============================================================================


class TestVetoFraud:
    """造假嫌疑——货币资金异常检测。"""

    def test_high_cash_ratio_triggers(self):
        triggers = check_veto(_f(money_cap=3e10, total_assets=5e10))
        assert len(triggers) == 1
        assert triggers[0].rule == "造假嫌疑"
        assert "60.0%" in triggers[0].reason

    def test_exactly_30_percent_no_trigger(self):
        triggers = check_veto(_f(money_cap=3e9, total_assets=1e10))
        assert len(triggers) == 0

    def test_below_30_percent_no_trigger(self):
        triggers = check_veto(_f(money_cap=2e9, total_assets=1e10))
        assert len(triggers) == 0

    def test_small_cash_no_trigger(self):
        triggers = check_veto(_f(money_cap=5e7, total_assets=1e8))
        assert len(triggers) == 0

    def test_missing_money_cap_no_trigger(self):
        triggers = check_veto(_f(money_cap=None, total_assets=1e10))
        assert len(triggers) == 0

    def test_missing_total_assets_no_trigger(self):
        triggers = check_veto(_f(money_cap=1e10, total_assets=None))
        assert len(triggers) == 0

    def test_zero_assets_no_trigger(self):
        triggers = check_veto(_f(money_cap=1e10, total_assets=0.0))
        assert len(triggers) == 0

    def test_high_cash_but_small_absolute_no_trigger(self):
        triggers = check_veto(_f(money_cap=5e7, total_assets=1e8))
        assert len(triggers) == 0  # mc=5000万 < 1亿

    def test_veto_trigger_is_frozen(self):
        triggers = check_veto(_f(money_cap=3e10, total_assets=5e10))
        vt = triggers[0]
        assert isinstance(vt, VetoTrigger)
        assert vt.rule == "造假嫌疑"
