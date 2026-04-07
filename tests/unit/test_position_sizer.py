"""
tests/unit/test_position_sizer.py

PositionSizer 단위 테스트.
"""
import pytest
import math
from execution.position_sizer import PositionSizer, OrderPlan, OrderLine


class TestPositionSizerBasic:
    def setup_method(self):
        self.prices = {"SPY": 500.0, "SH": 41.0}
        self.sizer = PositionSizer(portfolio_value=1_000_000, current_prices=self.prices)

    def _allocation(self, e=0.6, h=0.1, c=0.3):
        return {"equities": e, "hedge": h, "cash": c}

    def _exec(self, entry="staggered", stop=0.05):
        return {"entry_style": entry, "stop_loss": stop}

    def _compute(self, alloc=None, exec_plan=None):
        return self.sizer.compute(
            allocation=alloc or self._allocation(),
            execution_plan=exec_plan or self._exec(),
            strategy_name="TestStrategy",
            approval_status="approved",
            date="2024-01-15",
        )

    def test_returns_order_plan(self):
        plan = self._compute()
        assert isinstance(plan, OrderPlan)

    def test_equity_order_created(self):
        plan = self._compute()
        spy_orders = [o for o in plan.orders if o.ticker == "SPY"]
        assert len(spy_orders) == 1

    def test_equity_shares_correct(self):
        plan = self._compute()
        spy = next(o for o in plan.orders if o.ticker == "SPY")
        # 600,000 / 500.0 = 1200 shares
        assert spy.shares == 1200
        assert spy.notional == 600_000.0

    def test_stop_loss_price_correct(self):
        plan = self._compute()
        spy = next(o for o in plan.orders if o.ticker == "SPY")
        # 500 * (1 - 0.05) = 475
        assert abs(spy.stop_loss_price - 475.0) < 0.01

    def test_hedge_order_created(self):
        plan = self._compute()
        sh_orders = [o for o in plan.orders if o.ticker == "SH"]
        assert len(sh_orders) == 1

    def test_hedge_shares_correct(self):
        plan = self._compute()
        sh = next(o for o in plan.orders if o.ticker == "SH")
        # 100,000 / 41.0 = floor(2439.02) = 2439
        assert sh.shares == math.floor(100_000 / 41.0)

    def test_cash_reserved_correct(self):
        plan = self._compute()
        assert abs(plan.cash_reserved - 300_000.0) < 0.01

    def test_to_dict_structure(self):
        plan = self._compute()
        d = plan.to_dict()
        assert "orders" in d
        assert "cash_reserved" in d
        assert "estimated_slippage" in d
        assert d["portfolio_value"] == 1_000_000

    def test_slippage_estimated(self):
        plan = self._compute()
        assert plan.estimated_slippage > 0

    def test_entry_style_preserved(self):
        plan = self._compute(exec_plan=self._exec(entry="immediate"))
        for o in plan.orders:
            assert o.entry_style == "immediate"


class TestPositionSizerEdgeCases:
    def test_all_cash_no_orders(self):
        sizer = PositionSizer(1_000_000, {"SPY": 500.0})
        plan = sizer.compute(
            allocation={"equities": 0.0, "hedge": 0.0, "cash": 1.0},
            execution_plan={"entry_style": "hold", "stop_loss": 0.05},
            strategy_name="CashOnly",
            approval_status="approved",
            date="2024-01-15",
        )
        assert plan.orders == []
        assert abs(plan.cash_reserved - 1_000_000) < 0.01

    def test_no_prices_warns(self):
        sizer = PositionSizer(1_000_000, {})
        plan = sizer.compute(
            allocation={"equities": 0.6, "hedge": 0.1, "cash": 0.3},
            execution_plan={"entry_style": "staggered", "stop_loss": 0.05},
            strategy_name="NoPriceStrat",
            approval_status="approved",
            date="2024-01-15",
        )
        # 주문 없음 + 경고 있음
        spy_orders = [o for o in plan.orders if o.ticker == "SPY"]
        assert len(spy_orders) == 0
        assert len(plan.warnings) > 0

    def test_allocation_over_100_normalized(self):
        sizer = PositionSizer(1_000_000, {"SPY": 500.0})
        plan = sizer.compute(
            allocation={"equities": 0.8, "hedge": 0.5, "cash": 0.5},  # sum=1.8
            execution_plan={"entry_style": "staggered", "stop_loss": 0.05},
            strategy_name="Overweight",
            approval_status="approved",
            date="2024-01-15",
        )
        assert "normalized" in " ".join(plan.warnings).lower()
        # 총 주문 notional이 portfolio_value 이하여야 함
        total_notional = sum(o.notional for o in plan.orders)
        assert total_notional <= 1_000_000 + 1  # float tolerance

    def test_invalid_portfolio_value_raises(self):
        with pytest.raises(ValueError):
            PositionSizer(0, {"SPY": 500.0})
        with pytest.raises(ValueError):
            PositionSizer(-1000, {"SPY": 500.0})

    def test_small_portfolio_no_fractional_shares(self):
        """소액 포트폴리오: 1주도 못 살 경우 shares=0 + 경고."""
        sizer = PositionSizer(100, {"SPY": 500.0})
        plan = sizer.compute(
            allocation={"equities": 0.6, "hedge": 0.0, "cash": 0.4},
            execution_plan={"entry_style": "staggered", "stop_loss": 0.05},
            strategy_name="TooSmall",
            approval_status="approved",
            date="2024-01-15",
        )
        spy_orders = [o for o in plan.orders if o.ticker == "SPY"]
        assert len(spy_orders) == 0  # 60 < 500, 1주 불가
        assert len(plan.warnings) > 0


class TestOrderNodeIntegration:
    """order.py 노드와 PositionSizer 통합 테스트."""

    def test_order_node_with_prices(self):
        from graph.nodes.order import daily_order_plan_generation
        from graph.state import make_initial_state

        state = make_initial_state("2024-01-15")
        state["_portfolio_value"] = 500_000.0
        state["_current_prices"] = {"SPY": 450.0, "SH": 40.0}
        state["execution_feasibility_score"] = 0.8
        state["otto_output"] = {
            "approval_status": "approved",
            "selected_policy": "SPY Momentum",
            "allocation": {"equities": 0.70, "hedge": 0.10, "cash": 0.20},
            "execution_plan": {"entry_style": "staggered", "stop_loss": 0.05},
        }
        state["otto_policy_packet"] = {"action": "execute", "approval_status": "approved"}

        result = daily_order_plan_generation(state)
        plan = result["execution_plan"]

        assert plan["status"] == "planned"
        assert len(plan["orders"]) >= 1
        spy = next(o for o in plan["orders"] if o["ticker"] == "SPY")
        # 350,000 / 450 = floor(777.7) = 777 shares
        assert spy["shares"] == math.floor(350_000 / 450.0)
        assert spy["stop_loss_price"] == pytest.approx(450.0 * 0.95, rel=1e-3)

    def test_order_node_hold_no_orders(self):
        from graph.nodes.order import daily_order_plan_generation
        from graph.state import make_initial_state

        state = make_initial_state("2024-01-15")
        state["otto_policy_packet"] = {"action": "hold", "approval_status": "approved"}
        state["otto_output"] = {"approval_status": "approved"}

        result = daily_order_plan_generation(state)
        plan = result["execution_plan"]
        assert plan["orders"] == []
        assert plan["status"] == "no_order"

    def test_order_node_rejected_no_orders(self):
        from graph.nodes.order import daily_order_plan_generation
        from graph.state import make_initial_state

        state = make_initial_state("2024-01-15")
        state["otto_policy_packet"] = {"action": "execute", "approval_status": "rejected"}
        state["otto_output"] = {"approval_status": "rejected"}

        result = daily_order_plan_generation(state)
        plan = result["execution_plan"]
        assert plan["orders"] == []
