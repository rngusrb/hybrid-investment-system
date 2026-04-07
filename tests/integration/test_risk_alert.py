"""
Integration tests for event-driven risk alert flow.
Covers run_risk_alert_cycle, RiskAlertMeeting logic, _compute_risk_reward,
and daily_risk_check → risk_alert_triggered linkage.
Mock state used — real meeting logic executed (no LLM calls).
"""

import pytest
from ledger.shared_ledger import SharedLedger
from meetings.risk_alert import RiskAlertMeeting
from orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Shared mock state builders
# ---------------------------------------------------------------------------

def _dave_output(risk_score: float = 0.5, stress_severity: float = 0.4) -> dict:
    return {
        "agent": "Dave",
        "date": "2024-01-15",
        "risk_score": risk_score,
        "risk_components": {
            "beta": 0.9, "illiquidity": 0.1,
            "sector_concentration": 0.2, "volatility": 0.15,
        },
        "signal_conflict_risk": 0.2,
        "stress_test": {"severity_score": stress_severity, "worst_case_drawdown": 0.12},
        "risk_level": "high" if risk_score > 0.75 else "medium",
        "recommended_controls": ["monitor_vol"],
        "risk_constraints": {
            "max_single_sector_weight": 0.3,
            "max_beta": 1.2,
            "max_gross_exposure": 0.9,
        },
        "trigger_risk_alert_meeting": risk_score > 0.75,
    }


def _emily_output(regime_confidence: float = 0.7, reversal_risk: float = 0.3) -> dict:
    return {
        "agent": "Emily",
        "date": "2024-01-15",
        "market_regime": "risk_on",
        "regime_confidence": regime_confidence,
        "macro_state": {
            "rates": 0.1, "inflation": 0.2, "growth": 0.3,
            "liquidity": 0.1, "risk_sentiment": 0.4,
        },
        "technical_signal_state": {
            "trend_direction": "up",
            "continuation_strength": 0.6,
            "reversal_risk": reversal_risk,
            "technical_confidence": 0.7,
        },
        "sector_preference": [{"sector": "tech", "score": 0.8}],
        "bull_catalysts": ["strong_earnings"],
        "bear_catalysts": ["inflation_spike"],
        "event_sensitivity_map": [],
        "technical_conflict_flags": [],
        "risk_flags": [],
        "uncertainty_reasons": [],
        "recommended_market_bias": "selective_long",
    }


def _otto_output() -> dict:
    return {
        "agent": "Otto",
        "date": "2024-01-15",
        "candidate_policies": ["policy_a"],
        "adaptive_weights": {"w_sim": 0.4, "w_real": 0.6, "lookback_steps": 10},
        "selected_policy": "policy_a",
        "allocation": {"equities": 0.6, "hedge": 0.1, "cash": 0.3},
        "execution_plan": {
            "entry_style": "staggered",
            "rebalance_frequency": "weekly",
            "stop_loss": 0.05,
        },
        "policy_reasoning_summary": ["risk-adjusted portfolio"],
        "approval_status": "approved",
    }


def _make_risk_state(risk_score: float = 0.8, stress_severity: float = 0.4) -> dict:
    return {
        "current_date": "2024-01-15",
        "cycle_type": "event",
        "risk_alert_triggered": True,
        "risk_score": risk_score,
        "dave_output": _dave_output(risk_score=risk_score, stress_severity=stress_severity),
        "emily_output": _emily_output(),
        "otto_output": _otto_output(),
        "skip_log": [],
        "propagation_audit_log": [],
    }


# ---------------------------------------------------------------------------
# TestRiskAlertCycleOrchestrator
# ---------------------------------------------------------------------------

class TestRiskAlertCycleOrchestrator:
    """Tests 1-2: Orchestrator.run_risk_alert_cycle 검증."""

    def test_run_risk_alert_cycle_no_error(self):
        """Test 1: run_risk_alert_cycle() — 오류 없이 실행."""
        orchestrator = Orchestrator()
        result = orchestrator.run_risk_alert_cycle("2024-01-15", trigger_reason="vix_spike")

        assert result is not None
        assert isinstance(result, dict)

    def test_run_risk_alert_cycle_ledger_records_risk_override(self):
        """Test 2: run_risk_alert_cycle() — ledger에 risk_override_record 기록됨."""
        orchestrator = Orchestrator()
        orchestrator.run_risk_alert_cycle("2024-01-15", trigger_reason="vix_spike")

        entries = orchestrator.ledger.get_entries_by_type("risk_override_record")
        assert len(entries) > 0
        assert entries[0]["entry_type"] == "risk_override_record"


# ---------------------------------------------------------------------------
# TestRiskAlertMeetingLogic
# ---------------------------------------------------------------------------

class TestRiskAlertMeetingLogic:
    """Tests 3-5: RiskAlertMeeting 실제 로직 검증."""

    def test_high_risk_score_triggers_immediate_de_risk(self):
        """Test 3: RiskAlertMeeting.run() — risk_score > 0.85이면 'immediate_de_risk' emergency control 포함."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)
        state = _make_risk_state(risk_score=0.90)

        meeting.run(state)

        entries = ledger.get_entries_by_type("risk_override_record")
        assert len(entries) > 0
        risk_override = entries[0]["content"]
        assert "immediate_de_risk" in risk_override["emergency_controls"]

    def test_flow_decision_reason_contains_utility_value(self):
        """Test 4: RiskAlertMeeting.run() — flow_decision_reason에 utility 수치 포함."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)
        state = _make_risk_state(risk_score=0.80)

        result = meeting.run(state)

        assert "flow_decision_reason" in result
        reason = result["flow_decision_reason"]
        assert "utility=" in reason
        assert "controls=" in reason

    def test_compute_risk_reward_higher_risk_score_gives_lower_value(self):
        """Test 5: RiskAlertMeeting._compute_risk_reward() — risk_score 높으면 risk_reward 더 낮음 (더 많은 패널티)."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)

        # 동일한 다른 파라미터, risk_score만 다르게
        rr_low_risk = meeting._compute_risk_reward(
            risk_score=0.3,
            stress_severity=0.4,
            sentiment_safety=0.5,
            technical_reversal_penalty=0.3,
        )
        rr_high_risk = meeting._compute_risk_reward(
            risk_score=0.9,
            stress_severity=0.4,
            sentiment_safety=0.5,
            technical_reversal_penalty=0.3,
        )

        # risk_score 높으면 risk_reward (음수에 가까운 방향) 더 낮아야 함
        assert rr_high_risk < rr_low_risk


# ---------------------------------------------------------------------------
# TestDailyRiskCheckIntegration
# ---------------------------------------------------------------------------

class TestDailyRiskCheckIntegration:
    """Test 6: daily_risk_check와 risk_alert_triggered 연동 검증."""

    def test_dave_high_risk_score_sets_risk_alert_triggered(self):
        """Test 6: dave_output.risk_score > 0.75이면 daily_risk_check에서 risk_alert_triggered=True."""
        from graph.nodes.risk_check import daily_risk_check
        from graph.state import make_initial_state

        state = make_initial_state("2024-01-15", cycle_type="daily")
        state["dave_output"] = _dave_output(risk_score=0.80)

        result = daily_risk_check(state)

        assert result["risk_alert_triggered"] is True
        assert result["next_node"] == "RISK_ALERT_MEETING"
        assert result["risk_score"] == 0.80

    def test_dave_low_risk_score_does_not_trigger_alert(self):
        """dave_output.risk_score <= 0.75이면 risk_alert_triggered=False."""
        from graph.nodes.risk_check import daily_risk_check
        from graph.state import make_initial_state

        state = make_initial_state("2024-01-15", cycle_type="daily")
        state["dave_output"] = _dave_output(risk_score=0.50)

        result = daily_risk_check(state)

        assert result["risk_alert_triggered"] is False
        assert result["next_node"] == "DAILY_POLICY_SELECTION"
