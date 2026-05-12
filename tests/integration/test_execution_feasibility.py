"""
tests/integration/test_execution_feasibility.py — E-003 완료 기준 검증

완료 기준: feasibility score 낮은 경우 Otto가 staggered execution 또는 hold 반환.

검증 시나리오:
  bc_portfolio_node:
  1. sim_results/dave_output 없으면 feasibility 기본값으로 계산됨
  2. high sharpe + high cash → high feasibility
  3. low sharpe + low cash + high risk → low feasibility (< 0.4)
  4. execution_feasibility가 state에 저장됨

  bc_otto_node:
  5. feasibility_score >= 0.4 → staggered 없음
  6. feasibility_score < 0.4 → execution_plan.execution_style = "staggered"
  7. feasibility_score < 0.4 → portfolio.execution_style = "staggered"
  8. feasibility_score < 0.4 + rejected 상태 → staggered 미적용 (approved/conditional만 대상)
  9. execution_feasibility 비어있으면 staggered 미적용 (기본값 1.0)

  bc_portfolio _compute_execution_feasibility 유닛:
  10. score가 [0, 1] 범위 내
  11. high risk_score → low feasibility
  12. zero sim_results → 기본값 반환
"""
import pytest
from unittest.mock import patch

from graph.bc_state import make_initial_bc_state
from graph.nodes.bc_portfolio import bc_portfolio_node, _compute_execution_feasibility
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


def _run_portfolio(sim_results: dict, dave_output: dict, portfolio_stub: dict = None) -> dict:
    portfolio_stub = portfolio_stub or {"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1}
    state = _base_state(
        stock_results=[{"ticker": "AAPL"}],
        sim_results=sim_results,
        dave_output=dave_output,
    )
    with patch("scripts.portfolio_pipeline.run_portfolio_manager", return_value=portfolio_stub):
        return bc_portfolio_node(state)


# 고/저 feasibility 시나리오 공용 입력값
_HIGH_FEAS_INPUTS = dict(
    sim_results={"AAPL": {"best": {"sharpe": 1.2, "turnover": 0.3}}},
    dave_output={"risk_score": 0.4},
    portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1, "allocations": []},
)
_LOW_FEAS_INPUTS = dict(
    sim_results={},
    dave_output={"risk_score": 0.9},
    portfolio={"total_equity_pct": 0.9, "cash_pct": 0.05, "hedge_pct": 0.05, "allocations": []},
)


def _run_otto(
    *,
    sim_results: dict | None = None,
    dave_output: dict | None = None,
    portfolio: dict | None = None,
    otto_status: str = "approved",
) -> dict:
    """bc_otto_node 실행. Fix 3: bc_otto가 dave_output으로 feasibility를 직접 재산출."""
    def _otto_stub(*args, **kwargs):
        return {"approval_status": otto_status, "selected_policy": "p", "execution_plan": {}}

    sim_results = sim_results if sim_results is not None else {}
    dave_output = dave_output or {"risk_score": 0.4}
    portfolio   = portfolio   or {"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1, "allocations": []}
    state = _base_state(
        emily_output={"market_regime": "bull", "regime_confidence": 0.7},
        portfolio=portfolio,
        dave_output=dave_output,
        sim_results=sim_results,
    )
    with patch("integration.otto_gate.run_otto_approval", side_effect=_otto_stub), \
         patch("integration.otto_gate.apply_otto_decision", side_effect=lambda o, p: dict(p)):
        return bc_otto_node(state)


# ── bc_state 초기값 ───────────────────────────────────────────────────────────

class TestBcStateExecutionFeasibility:
    def test_initial_state_has_execution_feasibility(self):
        s = make_initial_bc_state("2024-01-15", ["AAPL"], None, None)
        assert "execution_feasibility" in s
        assert s["execution_feasibility"] == {}


# ── _compute_execution_feasibility 유닛 테스트 ────────────────────────────────

class TestComputeExecutionFeasibility:
    def test_score_in_range(self):
        result = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.3},
            sim_results={"AAPL": {"best": {"sharpe": 1.0, "turnover": 0.3}}},
            dave_output={"risk_score": 0.4},
        )
        assert 0.0 <= result["feasibility_score"] <= 1.0

    def test_high_sharpe_high_cash_low_risk_gives_high_score(self):
        result = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.5},
            sim_results={"AAPL": {"best": {"sharpe": 2.0, "turnover": 0.2}}},
            dave_output={"risk_score": 0.1},
        )
        assert result["feasibility_score"] >= 0.6

    def test_low_sharpe_low_cash_high_risk_gives_low_score(self):
        result = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.05},
            sim_results={"AAPL": {"best": {"sharpe": -0.5, "turnover": 0.8}}},
            dave_output={"risk_score": 0.9},
        )
        assert result["feasibility_score"] < 0.4

    def test_empty_sim_results_returns_default(self):
        result = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.3},
            sim_results={},
            dave_output={"risk_score": 0.5},
        )
        assert "feasibility_score" in result
        assert 0.0 <= result["feasibility_score"] <= 1.0

    def test_high_risk_score_lowers_feasibility(self):
        low = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.3},
            sim_results={"AAPL": {"best": {"sharpe": 1.0, "turnover": 0.3}}},
            dave_output={"risk_score": 0.9},
        )
        high = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.3},
            sim_results={"AAPL": {"best": {"sharpe": 1.0, "turnover": 0.3}}},
            dave_output={"risk_score": 0.2},
        )
        assert low["feasibility_score"] < high["feasibility_score"]

    def test_contains_required_keys(self):
        result = _compute_execution_feasibility(
            portfolio={"cash_pct": 0.3},
            sim_results={},
            dave_output={},
        )
        for key in ("feasibility_score", "rebalance_urgency", "avg_sharpe", "cash_pct", "dave_risk_score"):
            assert key in result


# ── bc_portfolio_node 저장 검증 ───────────────────────────────────────────────

class TestPortfolioNodeFeasibility:
    def test_execution_feasibility_stored_in_state(self):
        result = _run_portfolio(
            sim_results={"AAPL": {"best": {"sharpe": 1.2, "turnover": 0.3}}},
            dave_output={"risk_score": 0.4},
        )
        assert "execution_feasibility" in result
        assert "feasibility_score" in result["execution_feasibility"]

    def test_high_feasibility_scenario(self):
        result = _run_portfolio(
            sim_results={"AAPL": {"best": {"sharpe": 2.0, "turnover": 0.2}}},
            dave_output={"risk_score": 0.1},
            portfolio_stub={"total_equity_pct": 0.5, "cash_pct": 0.45, "hedge_pct": 0.05},
        )
        assert result["execution_feasibility"]["feasibility_score"] >= 0.5

    def test_low_feasibility_scenario(self):
        result = _run_portfolio(
            sim_results={"AAPL": {"best": {"sharpe": -0.3, "turnover": 0.9}}},
            dave_output={"risk_score": 0.85},
            portfolio_stub={"total_equity_pct": 0.9, "cash_pct": 0.05, "hedge_pct": 0.05},
        )
        assert result["execution_feasibility"]["feasibility_score"] < 0.4


# ── bc_otto_node feasibility gating ──────────────────────────────────────────

class TestOttoFeasibilityGating:
    def test_high_feasibility_no_staggered(self):
        """높은 feasibility 입력 → staggered 없음 (score ≈ 0.60)."""
        result = _run_otto(**_HIGH_FEAS_INPUTS, otto_status="approved")
        plan = result["otto_output"].get("execution_plan", {})
        assert plan.get("execution_style") != "staggered"
        assert result["portfolio"].get("execution_style") != "staggered"

    def test_low_feasibility_approved_gets_staggered(self):
        """낮은 feasibility 입력 → staggered 적용 (score ≈ 0.045)."""
        result = _run_otto(**_LOW_FEAS_INPUTS, otto_status="approved")
        assert result["otto_output"]["execution_plan"]["execution_style"] == "staggered"
        assert result["portfolio"]["execution_style"] == "staggered"

    def test_low_feasibility_conditional_approval_gets_staggered(self):
        result = _run_otto(**_LOW_FEAS_INPUTS, otto_status="conditional_approval")
        assert result["otto_output"]["execution_plan"]["execution_style"] == "staggered"
        assert result["portfolio"]["execution_style"] == "staggered"

    def test_low_feasibility_rejected_no_staggered(self):
        """rejected 상태는 staggered 미적용 — rejected 로직 그대로(portfolio 키 없음)."""
        result = _run_otto(**_LOW_FEAS_INPUTS, otto_status="rejected")
        # rejected는 otto_feedback 반환 경로 — portfolio 키 자체가 없음
        assert "otto_feedback" in result
        assert "portfolio" not in result

    def test_boundary_exactly_04_no_staggered(self):
        """경계값: score == 0.4 → < 0.4 조건 미충족 → staggered 없음.
        sharpe=0.2 → score = 0.4×0.1 + 0.3×0.6 + 0.3×0.6 = 0.40
        """
        result = _run_otto(
            sim_results={"AAPL": {"best": {"sharpe": 0.2, "turnover": 0.3}}},
            dave_output={"risk_score": 0.4},
            portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1, "allocations": []},
            otto_status="approved",
        )
        plan = result["otto_output"].get("execution_plan", {})
        assert plan.get("execution_style") != "staggered"

    def test_normal_conditions_no_staggered(self):
        """정상 조건(적절한 sharpe/cash/risk) → staggered 미발동."""
        result = _run_otto(**_HIGH_FEAS_INPUTS, otto_status="approved")
        plan = result["otto_output"].get("execution_plan", {})
        assert plan.get("execution_style") != "staggered"
