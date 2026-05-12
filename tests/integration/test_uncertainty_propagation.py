"""
tests/integration/test_uncertainty_propagation.py — E-004 완료 기준 검증

완료 기준: 각 uncertainty 조건에서 하위 노드가 실제로 다른 결과를 반환하는 테스트 통과.

링크 1 — Emily regime_confidence < 0.55 → bc_backtester:
  - uncertainty_mode=True 저장
  - lookback=30 사용 (기본 20과 다른 파라미터)
  - candidate_strategies 상위 3개 포함

링크 2 — avg_sharpe < 0.5 (= low strategy_confidence) → bc_dave:
  - risk_score에 stress_multiplier 적용
  - stress_multiplier_applied 필드 존재

링크 3 — dave risk_score > 0.7 + emily regime_confidence < 0.55 → bc_otto:
  - total_equity_pct 감소 (× 0.85)
  - exposure_shrinkage_applied = True
"""
import pytest
from unittest.mock import patch, MagicMock

from graph.bc_state import make_initial_bc_state
from graph.nodes.bc_backtester import bc_backtester_node
from graph.nodes.bc_dave import bc_dave_node
from graph.nodes.bc_otto import bc_otto_node


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _base_state(**overrides) -> dict:
    s = make_initial_bc_state(
        current_date="2024-01-15",
        tickers=["AAPL"],
        llm_analyst=None,
        llm_decision=None,
    )
    s.update(overrides)
    return s


# ── 링크 1: Emily uncertainty → bc_backtester lookback/diversity ──────────────

class TestBacktesterUncertaintyMode:
    """regime_confidence < 0.55 → uncertainty_mode=True, lookback=30."""

    def _run_backtester(self, regime_confidence: float, results: list = None) -> dict:
        emily_output = {"regime_confidence": regime_confidence, "market_regime": "mixed"}
        stock_results = [{"ticker": "AAPL", "bars": [{"close": 100 + i} for i in range(50)]}]
        state = _base_state(emily_output=emily_output, stock_results=stock_results)

        captured = {}

        def mock_backtest_all(bars, ticker, as_of, lookback=20, **kwargs):
            captured["lookback"] = lookback
            mock_results = results or [
                {"strategy": "momentum", "sharpe": 1.0, "mdd": 0.1, "return": 0.05,
                 "sortino": 1.2, "win_rate": 0.6, "turnover": 0.3},
                {"strategy": "defensive", "sharpe": 0.8, "mdd": 0.05, "return": 0.03,
                 "sortino": 0.9, "win_rate": 0.55, "turnover": 0.2},
                {"strategy": "hedged", "sharpe": 0.6, "mdd": 0.08, "return": 0.02,
                 "sortino": 0.7, "win_rate": 0.5, "turnover": 0.25},
            ]
            return {
                "ticker": ticker, "as_of": as_of,
                "results": mock_results,
                "best": mock_results[0],
                "selected_strategy": mock_results[0]["strategy"],
                "data_source": "real",
            }

        with patch("simulation.backtester.backtest_all", side_effect=mock_backtest_all), \
             patch("simulation.backtester.save_sim_result"):
            result = bc_backtester_node(state)

        return result, captured

    def test_low_regime_confidence_sets_uncertainty_mode_true(self):
        result, _ = self._run_backtester(regime_confidence=0.45)
        assert result["uncertainty_mode"] is True

    def test_high_regime_confidence_sets_uncertainty_mode_false(self):
        result, _ = self._run_backtester(regime_confidence=0.75)
        assert result["uncertainty_mode"] is False

    def test_boundary_exactly_055_is_not_uncertainty(self):
        """0.55 == 0.55 → < 0.55 조건 미충족 → uncertainty_mode=False."""
        result, _ = self._run_backtester(regime_confidence=0.55)
        assert result["uncertainty_mode"] is False

    def test_low_regime_confidence_uses_extended_lookback(self):
        _, captured = self._run_backtester(regime_confidence=0.40)
        assert captured["lookback"] == 30

    def test_high_regime_confidence_uses_default_lookback(self):
        _, captured = self._run_backtester(regime_confidence=0.80)
        assert captured["lookback"] == 20

    def test_uncertainty_mode_includes_candidate_strategies(self):
        result, _ = self._run_backtester(regime_confidence=0.40)
        aapl_sim = result["sim_results"].get("AAPL", {})
        assert "candidate_strategies" in aapl_sim
        assert len(aapl_sim["candidate_strategies"]) <= 3

    def test_normal_mode_does_not_include_candidate_strategies(self):
        result, _ = self._run_backtester(regime_confidence=0.80)
        aapl_sim = result["sim_results"].get("AAPL", {})
        assert "candidate_strategies" not in aapl_sim

    def test_different_lookback_produces_different_mode(self):
        """uncertainty_mode에 따라 lookback이 달라짐을 명시적으로 검증."""
        _, low_conf = self._run_backtester(regime_confidence=0.40)
        _, high_conf = self._run_backtester(regime_confidence=0.80)
        assert low_conf["lookback"] != high_conf["lookback"]


# ── 링크 2: low strategy_confidence → bc_dave stress multiplier ───────────────

class TestDaveStressMultiplier:
    """avg_sharpe < 0.5 → dave risk_score에 stress multiplier 적용."""

    def _run_dave(self, avg_sharpe: float, base_risk_score: float = 0.5) -> dict:
        sim_results = {
            "AAPL": {"best": {"sharpe": avg_sharpe, "mdd": 0.1, "turnover": 0.3}}
        }
        state = _base_state(
            portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3, "allocations": []},
            stock_results=[{"ticker": "AAPL"}],
            sim_results=sim_results,
        )

        mock_dave_output = {"risk_score": base_risk_score, "risk_level": "medium"}

        with patch("integration.dave_context.run_dave_for_portfolio",
                   return_value=(mock_dave_output, "")):
            return bc_dave_node(state)

    def test_low_sharpe_applies_stress_multiplier(self):
        result = self._run_dave(avg_sharpe=0.2)
        assert "stress_multiplier_applied" in result["dave_output"]
        assert result["dave_output"]["stress_multiplier_applied"] > 1.0

    def test_low_sharpe_increases_risk_score(self):
        base_risk = 0.5
        result = self._run_dave(avg_sharpe=0.2, base_risk_score=base_risk)
        assert result["dave_output"]["risk_score"] > base_risk

    def test_high_sharpe_no_stress_multiplier(self):
        result = self._run_dave(avg_sharpe=1.2)
        assert "stress_multiplier_applied" not in result["dave_output"]

    def test_sharpe_exactly_05_no_multiplier(self):
        """avg_sharpe == 0.5 → < 0.5 조건 미충족 → multiplier 없음."""
        result = self._run_dave(avg_sharpe=0.5)
        assert "stress_multiplier_applied" not in result["dave_output"]

    def test_stress_multiplier_max_cap_15_percent(self):
        """매우 낮은 sharpe에도 multiplier는 최대 1.15."""
        result = self._run_dave(avg_sharpe=-1.0)
        mult = result["dave_output"].get("stress_multiplier_applied", 1.0)
        assert mult <= 1.15

    def test_risk_score_capped_at_1(self):
        """stress multiplier 적용 후 risk_score는 1.0 초과 불가."""
        result = self._run_dave(avg_sharpe=0.1, base_risk_score=0.98)
        assert result["dave_output"]["risk_score"] <= 1.0

    def test_empty_sim_results_no_multiplier(self):
        """sim_results 없으면 stress multiplier 미적용."""
        state = _base_state(
            portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3},
            stock_results=[{"ticker": "AAPL"}],
            sim_results={},
        )
        mock_dave_output = {"risk_score": 0.5, "risk_level": "medium"}
        with patch("integration.dave_context.run_dave_for_portfolio",
                   return_value=(mock_dave_output, "")):
            result = bc_dave_node(state)
        assert "stress_multiplier_applied" not in result["dave_output"]


# ── 링크 3: Dave risk + Emily uncertainty → bc_otto exposure shrinkage ─────────

class TestOttoExposureShrinkage:
    """dave risk > 0.7 + emily regime_confidence < 0.55 → equity shrinkage."""

    def _run_otto(
        self,
        dave_risk: float,
        emily_conf: float,
        otto_status: str = "approved",
        base_equity: float = 0.6,
    ) -> dict:
        def _otto_stub(*args, **kwargs):
            return {"approval_status": otto_status, "selected_policy": "p", "execution_plan": {}}

        # sim_results에 충분한 sharpe 주입 → feasibility >= 0.4 보장 (staggered 미발동)
        # score = 0.4×0.6 + 0.3×0.6 + 0.3×(1-dave_risk) >= 0.48 for dave_risk <= 0.8
        sim_results = {"AAPL": {"best": {"sharpe": 1.2, "turnover": 0.3}}}
        state = _base_state(
            emily_output={"market_regime": "mixed", "regime_confidence": emily_conf},
            portfolio={
                "total_equity_pct": base_equity,
                "cash_pct": 0.3,
                "hedge_pct": 0.1,
                "allocations": [],
            },
            dave_output={"risk_score": dave_risk},
            sim_results=sim_results,
            reliability_summary={},
        )
        with patch("integration.otto_gate.run_otto_approval", side_effect=_otto_stub), \
             patch("integration.otto_gate.apply_otto_decision", side_effect=lambda o, p: dict(p)):
            return bc_otto_node(state)

    def test_high_risk_low_confidence_applies_shrinkage(self):
        result = self._run_otto(dave_risk=0.75, emily_conf=0.45)
        assert result["portfolio"].get("exposure_shrinkage_applied") is True

    def test_equity_is_reduced_by_shrink_factor(self):
        base = 0.6
        result = self._run_otto(dave_risk=0.75, emily_conf=0.45, base_equity=base)
        new_equity = result["portfolio"]["total_equity_pct"]
        assert abs(new_equity - base * 0.85) < 1e-3

    def test_cash_pct_increases_after_shrinkage(self):
        result = self._run_otto(dave_risk=0.75, emily_conf=0.45, base_equity=0.6)
        assert result["portfolio"]["cash_pct"] > 0.3

    def test_low_risk_no_shrinkage(self):
        result = self._run_otto(dave_risk=0.4, emily_conf=0.45)
        assert result["portfolio"].get("exposure_shrinkage_applied") is not True

    def test_high_confidence_no_shrinkage(self):
        result = self._run_otto(dave_risk=0.75, emily_conf=0.70)
        assert result["portfolio"].get("exposure_shrinkage_applied") is not True

    def test_boundary_dave_risk_exactly_07_no_shrinkage(self):
        """dave_risk == 0.7 → > 0.7 조건 미충족 → shrinkage 없음."""
        result = self._run_otto(dave_risk=0.7, emily_conf=0.45)
        assert result["portfolio"].get("exposure_shrinkage_applied") is not True

    def test_rejected_status_no_shrinkage(self):
        """rejected 상태는 shrinkage 미적용 (approved/conditional만 대상)."""
        result = self._run_otto(dave_risk=0.8, emily_conf=0.40, otto_status="rejected")
        # rejected → portfolio 반환 없음
        assert "otto_feedback" in result

    def test_conditional_approval_also_gets_shrinkage(self):
        result = self._run_otto(dave_risk=0.8, emily_conf=0.40, otto_status="conditional_approval")
        assert result["portfolio"].get("exposure_shrinkage_applied") is True


# ── 체인 통합: 세 링크가 독립적으로 동작함을 확인 ────────────────────────────

class TestUncertaintyChainInitialState:
    def test_uncertainty_mode_initial_false(self):
        s = make_initial_bc_state("2024-01-15", ["AAPL"], None, None)
        assert s["uncertainty_mode"] is False
