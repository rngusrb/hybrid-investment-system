"""
tests.integration.test_weekly_cycle - Integration tests for Phase 11 meeting protocols.
Covers MarketAnalysisMeeting, StrategyDevelopmentMeeting, RiskAlertMeeting.
No real LLM calls — all mock state.
"""

import pytest
from ledger.shared_ledger import SharedLedger
from meetings.market_analysis import MarketAnalysisMeeting
from meetings.strategy_development import StrategyDevelopmentMeeting
from meetings.risk_alert import RiskAlertMeeting


# ---------------------------------------------------------------------------
# Shared mock state builders
# ---------------------------------------------------------------------------

def _emily_output(regime_confidence=0.7, tech_direction="up", market_regime="risk_on",
                   market_bias="selective_long", reversal_risk=0.2):
    return {
        "agent": "Emily",
        "date": "2026-04-01",
        "market_regime": market_regime,
        "regime_confidence": regime_confidence,
        "macro_state": {
            "rates": 0.1, "inflation": 0.2, "growth": 0.3,
            "liquidity": 0.1, "risk_sentiment": 0.4,
        },
        "technical_signal_state": {
            "trend_direction": tech_direction,
            "continuation_strength": 0.6,
            "reversal_risk": reversal_risk,
            "technical_confidence": 0.7,
        },
        "sector_preference": [
            {"sector": "tech", "score": 0.8},
            {"sector": "energy", "score": 0.3},
            {"sector": "healthcare", "score": 0.65},
        ],
        "bull_catalysts": ["strong_earnings", "fed_pause"],
        "bear_catalysts": ["inflation_spike"],
        "event_sensitivity_map": [{"event": "CPI", "risk_level": 0.4}],
        "technical_conflict_flags": [],
        "risk_flags": [],
        "uncertainty_reasons": ["mixed_signals"],
        "recommended_market_bias": market_bias,
    }


def _bob_output(candidates=None, selected=None):
    if candidates is None:
        candidates = [
            {
                "name": "momentum_long",
                "type": "momentum",
                "logic_summary": "Follow trend",
                "regime_fit": 0.8,
                "technical_alignment": 0.75,
                "sim_window": {"train_start": "2025-01-01", "train_end": "2025-12-31"},
                "sim_metrics": {
                    "return": 0.15, "sharpe": 1.2, "sortino": 1.5,
                    "mdd": 0.1, "turnover": 0.3, "hit_rate": 0.55,
                },
                "failure_conditions": ["vol_spike", "regime_change"],
                "optimization_suggestions": ["tighten_stop_loss"],
                "confidence": 0.7,
            },
            {
                "name": "low_confidence_strat",
                "type": "defensive",
                "logic_summary": "Safety first",
                "regime_fit": 0.4,
                "technical_alignment": 0.3,
                "sim_window": {"train_start": "2025-01-01", "train_end": "2025-12-31"},
                "sim_metrics": {
                    "return": 0.05, "sharpe": 0.5, "sortino": 0.6,
                    "mdd": 0.05, "turnover": 0.1, "hit_rate": 0.48,
                },
                "failure_conditions": ["liquidity_crunch"],
                "optimization_suggestions": [],
                "confidence": 0.3,  # below floor 0.45
            },
        ]
    if selected is None:
        selected = ["momentum_long"]
    return {
        "agent": "Bob",
        "date": "2026-04-01",
        "candidate_strategies": candidates,
        "selected_for_review": selected,
    }


def _dave_output(risk_score=0.5, stress_severity=0.4):
    return {
        "agent": "Dave",
        "date": "2026-04-01",
        "risk_score": risk_score,
        "risk_components": {
            "beta": 0.9, "illiquidity": 0.1,
            "sector_concentration": 0.2, "volatility": 0.15,
        },
        "signal_conflict_risk": 0.2,
        "stress_test": {"severity_score": stress_severity, "worst_case_drawdown": 0.12},
        "risk_level": "medium",
        "recommended_controls": ["monitor_vol"],
        "risk_constraints": {
            "max_single_sector_weight": 0.3,
            "max_beta": 1.2,
            "max_gross_exposure": 0.9,
        },
        "trigger_risk_alert_meeting": False,
    }


def _otto_output():
    return {
        "agent": "Otto",
        "date": "2026-04-01",
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


# ---------------------------------------------------------------------------
# TestMarketAnalysisMeeting
# ---------------------------------------------------------------------------

class TestMarketAnalysisMeeting:
    """Tests for MarketAnalysisMeeting (items 1-6)."""

    def test_run_produces_all_required_keys(self):
        """1. run() → debate_resolution, signal_conflict_resolution, weekly_market_report 모두 생성."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(),
        }
        result = meeting.run(state)

        assert "debate_resolution" in result
        assert "signal_conflict_resolution" in result
        assert "weekly_market_report" in result

    def test_debate_resolution_has_all_fields(self):
        """2. debate_resolution이 DebateResolution 구조체 필드를 모두 포함."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(regime_confidence=0.6),
        }
        result = meeting.run(state)
        dr = result["debate_resolution"]

        assert "bull_case" in dr
        assert "bear_case" in dr
        assert "moderator_summary" in dr
        assert "unresolved_issues" in dr
        assert "regime_confidence_adjustment" in dr
        # bull_case sub-fields
        assert "growth_path" in dr["bull_case"]
        assert "upside_catalysts" in dr["bull_case"]
        assert "sustainability" in dr["bull_case"]
        # bear_case sub-fields
        assert "downside_risks" in dr["bear_case"]
        assert "fragility" in dr["bear_case"]
        assert "reversal_triggers" in dr["bear_case"]

    def test_high_confidence_debate_simplified(self):
        """3. Emily confidence >= 0.85이면 unresolved_issues = []."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(
                regime_confidence=0.90,
                market_regime="risk_on",
            ),
        }
        result = meeting.run(state)
        dr = result["debate_resolution"]

        assert dr["unresolved_issues"] == []
        assert dr["regime_confidence_adjustment"] == 0.0

    def test_technical_macro_conflict_produces_nonempty_conflict_matrix(self):
        """4. technical vs macro 충돌이 있으면 signal_conflict_resolution.conflict_matrix 비어있지 않음."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        # tech up + macro risk_off → 충돌
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(
                tech_direction="up",
                market_regime="risk_off",
                market_bias="selective_long",
            ),
        }
        result = meeting.run(state)
        conflict_matrix = result["signal_conflict_resolution"]["conflict_matrix"]

        assert len(conflict_matrix) > 0

    def test_aligned_signals_produce_empty_conflict_matrix(self):
        """5. technical/macro 방향 일치하면 conflict_matrix가 비어있음."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        # tech up + macro risk_on + bias selective_long + low reversal risk → 충돌 없음
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(
                tech_direction="up",
                market_regime="risk_on",
                market_bias="selective_long",
                reversal_risk=0.2,  # below 0.6 threshold
            ),
        }
        result = meeting.run(state)
        conflict_matrix = result["signal_conflict_resolution"]["conflict_matrix"]

        assert conflict_matrix == []

    def test_ledger_records_required_entries(self):
        """6. MarketAnalysisMeeting 실행 후 shared_ledger에 final_market_report, debate_resolution, signal_conflict_resolution 기록."""
        ledger = SharedLedger()
        meeting = MarketAnalysisMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "emily_output": _emily_output(),
        }
        meeting.run(state)

        entry_types = {e["entry_type"] for e in ledger.get_all()}
        assert "final_market_report" in entry_types
        assert "debate_resolution" in entry_types
        assert "signal_conflict_resolution" in entry_types


# ---------------------------------------------------------------------------
# TestStrategyDevelopmentMeeting
# ---------------------------------------------------------------------------

class TestStrategyDevelopmentMeeting:
    """Tests for StrategyDevelopmentMeeting (items 7-9)."""

    def test_run_produces_weekly_strategy_set(self):
        """7. run() → weekly_strategy_set 생성."""
        ledger = SharedLedger()
        meeting = StrategyDevelopmentMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "bob_output": _bob_output(),
        }
        result = meeting.run(state)

        assert "weekly_strategy_set" in result

    def test_execution_packet_separate_from_selected_strategy(self):
        """8. selected strategy와 별도로 bob_to_execution_packet이 생성됨."""
        ledger = SharedLedger()
        meeting = StrategyDevelopmentMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "bob_output": _bob_output(),
        }
        result = meeting.run(state)

        assert "bob_to_execution_packet" in result
        # execution packet != selected strategy list
        wss = result["weekly_strategy_set"]
        exec_packet = result["bob_to_execution_packet"]
        assert isinstance(exec_packet, dict)
        # execution packet has feasibility fields, not just a strategy name list
        assert "rebalance_urgency" in exec_packet
        assert "hedge_preference" in exec_packet
        assert "execution_constraints_hint" in exec_packet

    def test_low_confidence_strategy_in_rejection_reasons(self):
        """9. confidence < 0.45인 전략은 rejection_reasons에 포함."""
        ledger = SharedLedger()
        meeting = StrategyDevelopmentMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "bob_output": _bob_output(),
        }
        result = meeting.run(state)

        rejection_reasons = result["weekly_strategy_set"]["rejection_reasons"]
        assert "low_confidence_strat" in rejection_reasons


# ---------------------------------------------------------------------------
# TestRiskAlertMeeting
# ---------------------------------------------------------------------------

class TestRiskAlertMeeting:
    """Tests for RiskAlertMeeting (items 10-12)."""

    def test_risk_override_recorded_in_ledger(self):
        """10. RiskAlertMeeting.run() → risk_override_record가 ledger에 기록됨."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "dave_output": _dave_output(risk_score=0.8),
            "emily_output": _emily_output(),
            "otto_output": _otto_output(),
        }
        meeting.run(state)

        entries = ledger.get_entries_by_type("risk_override_record")
        assert len(entries) > 0

    def test_risk_adjusted_utility_in_flow_decision_reason(self):
        """11. RiskAdjustedUtility 계산 결과가 flow_decision_reason에 포함됨."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "dave_output": _dave_output(risk_score=0.8),
            "emily_output": _emily_output(),
            "otto_output": _otto_output(),
        }
        result = meeting.run(state)

        assert "flow_decision_reason" in result
        assert "utility=" in result["flow_decision_reason"]
        assert "controls=" in result["flow_decision_reason"]

    def test_high_risk_score_triggers_immediate_de_risk(self):
        """12. risk_score > 0.85이면 emergency_controls에 'immediate_de_risk' 포함."""
        ledger = SharedLedger()
        meeting = RiskAlertMeeting(ledger=ledger)
        state = {
            "current_date": "2026-04-01",
            "dave_output": _dave_output(risk_score=0.9),
            "emily_output": _emily_output(),
            "otto_output": _otto_output(),
        }
        meeting.run(state)

        entries = ledger.get_entries_by_type("risk_override_record")
        assert len(entries) > 0
        risk_override = entries[0]["content"]
        assert "immediate_de_risk" in risk_override["emergency_controls"]
