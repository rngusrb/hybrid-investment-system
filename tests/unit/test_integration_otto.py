"""tests/unit/test_integration_otto.py — integration/otto_gate.py 단위 테스트 (LLM 없음)."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from integration.otto_gate import (
    build_otto_input,
    apply_otto_decision,
    run_otto_approval,
    _load_reward_history,
)


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_emily_output(**overrides) -> dict:
    base = {
        "market_regime": "risk_on",
        "regime_confidence": 0.82,
        "recommended_market_bias": "selective_long",
        "technical_signal_state": {
            "trend_direction": "up",
            "continuation_strength": 0.7,
            "reversal_risk": 0.21,
            "technical_confidence": 0.77,
        },
        "bull_catalysts": ["Fed pivot"],
        "bear_catalysts": ["recession risk"],
        "uncertainty_reasons": [],
        "risk_flags": [],
        "sector_preference": [],
    }
    base.update(overrides)
    return base


def make_portfolio(**overrides) -> dict:
    base = {
        "allocations": [
            {"ticker": "AAPL", "weight": 0.4, "action": "BUY"},
            {"ticker": "NVDA", "weight": 0.3, "action": "BUY"},
        ],
        "total_equity_pct": 0.7,
        "cash_pct": 0.2,
        "hedge_pct": 0.1,
        "portfolio_risk_level": "medium",
        "rebalance_urgency": 0.5,
        "entry_style": "staggered",
    }
    base.update(overrides)
    return base


def make_dave_output(**overrides) -> dict:
    base = {
        "risk_score": 0.42,
        "risk_level": "medium",
        "risk_components": {"beta": 0.3, "illiquidity": 0.1, "sector_concentration": 0.3, "volatility": 0.3},
        "stress_test": {"severity_score": 0.4, "worst_case_drawdown": 0.1},
        "recommended_controls": [],
        "risk_constraints": {
            "max_single_sector_weight": 0.4,
            "max_beta": 1.5,
            "max_gross_exposure": 1.0,
        },
        "trigger_risk_alert_meeting": False,
    }
    base.update(overrides)
    return base


def make_otto_output(**overrides) -> dict:
    base = {
        "agent": "Otto",
        "date": "2024-01-15",
        "approval_status": "approved",
        "selected_policy": "moderate_growth",
        "candidate_policies": ["moderate_growth", "defensive"],
        "allocation": {"equities": 0.6, "hedge": 0.1, "cash": 0.3},
        "execution_plan": {"entry_style": "staggered", "rebalance_frequency": "weekly", "stop_loss": 0.05},
        "adaptive_weights": {"w_sim": 0.5, "w_real": 0.5, "lookback_steps": 10},
        "policy_reasoning_summary": ["Risk-adjusted approval"],
        "confidence": 0.8,
    }
    base.update(overrides)
    return base


# ─── build_otto_input 테스트 ──────────────────────────────────────────────────

class TestBuildOttoInput:
    def test_returns_dict(self):
        result = build_otto_input(
            make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-01-15"
        )
        assert isinstance(result, dict)

    def test_no_forbidden_raw_fields(self):
        """Otto _block_raw_data_access를 통과해야 함."""
        from agents.otto import _FORBIDDEN_RAW_FIELDS
        result = build_otto_input(
            make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-01-15"
        )
        found = _FORBIDDEN_RAW_FIELDS.intersection(result.keys())
        assert not found, f"Forbidden raw fields found: {found}"

    def test_contains_market_regime(self):
        emily = make_emily_output(market_regime="risk_off")
        result = build_otto_input(emily, {}, make_dave_output(), make_portfolio(), "2024-01-15")
        assert result["market_regime"] == "risk_off"

    def test_contains_regime_confidence(self):
        emily = make_emily_output(regime_confidence=0.75)
        result = build_otto_input(emily, {}, make_dave_output(), make_portfolio(), "2024-01-15")
        assert result["regime_confidence"] == 0.75

    def test_contains_risk_score_from_dave(self):
        dave = make_dave_output(risk_score=0.65)
        result = build_otto_input(make_emily_output(), {}, dave, make_portfolio(), "2024-01-15")
        assert result["risk_score"] == 0.65

    def test_risk_alert_from_dave(self):
        dave = make_dave_output(trigger_risk_alert_meeting=True)
        result = build_otto_input(make_emily_output(), {}, dave, make_portfolio(), "2024-01-15")
        assert result["trigger_risk_alert"] is True

    def test_sim_results_strategy_selection(self):
        sim = {
            "AAPL": {"selected_strategy": "momentum", "best": {"sharpe": 1.5}},
            "NVDA": {"selected_strategy": "momentum", "best": {"sharpe": 2.0}},
            "MSFT": {"selected_strategy": "defensive", "best": {"sharpe": 0.8}},
        }
        result = build_otto_input(make_emily_output(), sim, make_dave_output(), make_portfolio(), "2024-01-15")
        # 가장 많이 선택된 전략 = momentum
        assert result["selected_strategy_name"] == "momentum"

    def test_empty_sim_results_defaults_to_defensive(self):
        result = build_otto_input(make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-01-15")
        assert result["selected_strategy_name"] == "defensive"

    def test_empty_dave_uses_defaults(self):
        result = build_otto_input(make_emily_output(), {}, {}, make_portfolio(), "2024-01-15")
        assert result["risk_score"] == 0.3
        assert result["risk_level"] == "medium"
        assert result["trigger_risk_alert"] is False

    def test_strategy_confidence_bounded_0_1(self):
        sim = {"AAPL": {"selected_strategy": "momentum", "best": {"sharpe": 99.0}}}
        result = build_otto_input(make_emily_output(), sim, make_dave_output(), make_portfolio(), "2024-01-15")
        assert 0.0 <= result["strategy_confidence"] <= 1.0

    def test_portfolio_summary_included(self):
        result = build_otto_input(make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-01-15")
        assert "portfolio_summary" in result
        ps = result["portfolio_summary"]
        assert "total_equity_pct" in ps
        assert "cash_pct" in ps

    def test_adaptive_weights_included(self):
        aw = {"w_sim": 0.3, "w_real": 0.7}
        result = build_otto_input(
            make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-01-15",
            adaptive_weights=aw
        )
        assert result["recent_reward_summary"]["w_sim"] == 0.3
        assert result["recent_reward_summary"]["w_real"] == 0.7

    def test_date_included(self):
        result = build_otto_input(make_emily_output(), {}, make_dave_output(), make_portfolio(), "2024-03-15")
        assert result["date"] == "2024-03-15"


# ─── apply_otto_decision 테스트 ───────────────────────────────────────────────

class TestApplyOttoDecision:
    def test_approved_returns_original(self):
        otto = make_otto_output(approval_status="approved")
        portfolio = make_portfolio()
        result = apply_otto_decision(otto, portfolio)
        assert result["total_equity_pct"] == portfolio["total_equity_pct"]
        assert result["allocations"] == portfolio["allocations"]

    def test_rejected_sets_all_hold(self):
        otto = make_otto_output(approval_status="rejected")
        portfolio = make_portfolio()
        result = apply_otto_decision(otto, portfolio)
        assert result["total_equity_pct"] == 0.05
        assert result["cash_pct"] == 0.90
        for a in result["allocations"]:
            assert a["action"] == "HOLD"
            assert a["weight"] == 0.0

    def test_rejected_sets_hedge_to_5pct(self):
        otto = make_otto_output(approval_status="rejected")
        result = apply_otto_decision(otto, make_portfolio())
        assert result["hedge_pct"] == 0.05

    def test_approved_with_modification_scales_equity_down(self):
        otto = make_otto_output(
            approval_status="approved_with_modification",
            allocation={"equities": 0.4, "hedge": 0.2, "cash": 0.4},
        )
        portfolio = make_portfolio(total_equity_pct=0.8)
        result = apply_otto_decision(otto, portfolio)
        # scale = 0.4 / 0.8 = 0.5 → equity should be 0.4
        assert abs(result["total_equity_pct"] - 0.4) < 1e-4

    def test_approved_with_modification_scales_weights(self):
        otto = make_otto_output(
            approval_status="approved_with_modification",
            allocation={"equities": 0.35, "hedge": 0.15, "cash": 0.5},
        )
        portfolio = make_portfolio(
            total_equity_pct=0.7,
            allocations=[
                {"ticker": "AAPL", "weight": 0.4, "action": "BUY"},
                {"ticker": "NVDA", "weight": 0.3, "action": "BUY"},
            ]
        )
        result = apply_otto_decision(otto, portfolio)
        # scale = 0.35 / 0.7 = 0.5
        for a in result["allocations"]:
            original_weight = 0.4 if a["ticker"] == "AAPL" else 0.3
            assert abs(a["weight"] - original_weight * 0.5) < 1e-4

    def test_conditional_approval_increases_hedge(self):
        otto = make_otto_output(approval_status="conditional_approval")
        portfolio = make_portfolio(hedge_pct=0.05)
        result = apply_otto_decision(otto, portfolio)
        assert result["hedge_pct"] > 0.05

    def test_conditional_approval_hedge_capped_at_30pct(self):
        otto = make_otto_output(approval_status="conditional_approval")
        portfolio = make_portfolio(hedge_pct=0.28)
        result = apply_otto_decision(otto, portfolio)
        assert result["hedge_pct"] <= 0.30

    def test_conditional_approval_high_risk_positions_become_hold(self):
        otto = make_otto_output(approval_status="conditional_approval")
        portfolio = make_portfolio(
            allocations=[
                {"ticker": "AAPL", "weight": 0.4, "action": "BUY", "risk_level": "high"},
                {"ticker": "NVDA", "weight": 0.3, "action": "BUY", "risk_level": "low"},
            ]
        )
        result = apply_otto_decision(otto, portfolio)
        aapl = next(a for a in result["allocations"] if a["ticker"] == "AAPL")
        nvda = next(a for a in result["allocations"] if a["ticker"] == "NVDA")
        assert aapl["action"] == "HOLD"
        assert nvda["action"] == "BUY"  # low risk → 유지

    def test_empty_otto_returns_original_portfolio(self):
        portfolio = make_portfolio()
        result = apply_otto_decision({}, portfolio)
        assert result == portfolio

    def test_none_otto_returns_original_portfolio(self):
        portfolio = make_portfolio()
        result = apply_otto_decision(None, portfolio)
        assert result == portfolio

    def test_preserves_portfolio_schema_keys(self):
        """PortfolioManagerOutput 구조 보존 확인."""
        otto = make_otto_output(approval_status="rejected")
        portfolio = make_portfolio()
        result = apply_otto_decision(otto, portfolio)
        for key in ("allocations", "total_equity_pct", "cash_pct", "hedge_pct"):
            assert key in result

    def test_approved_with_modification_scale_minimum_10pct(self):
        """scale이 0.1 미만으로 내려가지 않음."""
        otto = make_otto_output(
            approval_status="approved_with_modification",
            allocation={"equities": 0.01, "hedge": 0.01, "cash": 0.98},
        )
        portfolio = make_portfolio(total_equity_pct=0.8)
        result = apply_otto_decision(otto, portfolio)
        # scale = max(0.01/0.8, 0.1) = 0.1 → equity = 0.08
        assert result["total_equity_pct"] >= 0.07


# ─── _load_reward_history 테스트 ──────────────────────────────────────────────

class TestLoadRewardHistory:
    def test_returns_list(self):
        result = _load_reward_history()
        assert isinstance(result, list)

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import integration.otto_gate as module
        monkeypatch.setattr(module, "_STRATEGY_MEM_PATH", tmp_path / "nonexistent.json")
        result = _load_reward_history()
        assert result == []

    def test_loads_r_sim_and_r_real(self, tmp_path, monkeypatch):
        import integration.otto_gate as module
        mem_path = tmp_path / "strategy_memory.json"
        data = {
            "rec1": {"value": {"r_sim": 0.05, "r_real": 0.03, "selected_strategy": "momentum"}},
            "rec2": {"value": {"r_sim": 0.02, "r_real": -0.01, "selected_strategy": "defensive"}},
        }
        mem_path.write_text(json.dumps(data))
        monkeypatch.setattr(module, "_STRATEGY_MEM_PATH", mem_path)
        result = _load_reward_history()
        assert len(result) == 2
        assert all("r_sim" in r and "r_real" in r for r in result)

    def test_skips_records_without_r_real(self, tmp_path, monkeypatch):
        import integration.otto_gate as module
        mem_path = tmp_path / "strategy_memory.json"
        data = {
            "rec1": {"value": {"r_sim": 0.05}},          # r_real 없음 → skip
            "rec2": {"value": {"r_sim": 0.02, "r_real": 0.01}},  # 포함
        }
        mem_path.write_text(json.dumps(data))
        monkeypatch.setattr(module, "_STRATEGY_MEM_PATH", mem_path)
        result = _load_reward_history()
        assert len(result) == 1

    def test_capped_at_n(self, tmp_path, monkeypatch):
        import integration.otto_gate as module
        mem_path = tmp_path / "strategy_memory.json"
        data = {
            f"rec{i}": {"value": {"r_sim": 0.01 * i, "r_real": 0.005 * i}}
            for i in range(20)
        }
        mem_path.write_text(json.dumps(data))
        monkeypatch.setattr(module, "_STRATEGY_MEM_PATH", mem_path)
        result = _load_reward_history(n=5)
        assert len(result) <= 5

    def test_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        import integration.otto_gate as module
        mem_path = tmp_path / "strategy_memory.json"
        mem_path.write_text("NOT VALID JSON {{{{")
        monkeypatch.setattr(module, "_STRATEGY_MEM_PATH", mem_path)
        result = _load_reward_history()
        assert result == []


# ─── run_otto_approval 인터페이스 테스트 ──────────────────────────────────────

class MockLLM:
    def chat(self, messages, system="", **kwargs):
        return json.dumps(make_otto_output())


class TestRunOttoApproval:
    def test_returns_dict(self):
        llm = MockLLM()
        result = run_otto_approval(
            llm, "2024-01-15",
            make_emily_output(), {}, make_dave_output(), make_portfolio()
        )
        assert isinstance(result, dict)

    def test_empty_emily_returns_empty(self):
        llm = MockLLM()
        result = run_otto_approval(
            llm, "2024-01-15", {}, {}, make_dave_output(), make_portfolio()
        )
        assert result == {}

    def test_empty_portfolio_returns_empty(self):
        llm = MockLLM()
        result = run_otto_approval(
            llm, "2024-01-15", make_emily_output(), {}, make_dave_output(), {}
        )
        assert result == {}

    def test_result_has_approval_status(self):
        llm = MockLLM()
        result = run_otto_approval(
            llm, "2024-01-15",
            make_emily_output(), {}, make_dave_output(), make_portfolio()
        )
        assert "approval_status" in result

    def test_result_has_valid_approval_status(self):
        llm = MockLLM()
        result = run_otto_approval(
            llm, "2024-01-15",
            make_emily_output(), {}, make_dave_output(), make_portfolio()
        )
        valid = {"approved", "approved_with_modification", "conditional_approval", "rejected"}
        assert result.get("approval_status") in valid
