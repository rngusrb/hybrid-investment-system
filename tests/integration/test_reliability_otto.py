"""
tests/integration/test_reliability_otto.py — E-001 완료 기준 검증

완료 기준: reliability floor 이하 agent 의존 시 Otto가 conditional_approval 반환.

검증 시나리오:
  1. reliability_summary 비어있음 → Otto approved 그대로 통과
  2. 핵심 agent(trader/risk_manager/researcher) 모두 floor 이상 → approved 유지
  3. trader score < floor(0.35) → Otto approved 결과가 conditional_approval로 변환
  4. risk_manager score < floor → conditional_approval 변환
  5. researcher score < floor → conditional_approval 변환
  6. 이미 rejected 상태 → reliability gating 무시 (rejected 유지)
  7. conditional_approval 원래 반환 → gating 불필요 (그대로 유지)
  8. bc_calibration_node → reliability_summary 저장 검증
  9. bc_state.py reliability_summary 초기값 검증
"""
import pytest
from unittest.mock import patch, MagicMock

from graph.bc_state import make_initial_bc_state, SystemStateBC
from graph.nodes.bc_otto import bc_otto_node
from graph.nodes.bc_calibration import bc_calibration_node


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _base_state(**overrides) -> dict:
    s = make_initial_bc_state(
        current_date="2024-01-15",
        tickers=["AAPL"],
        llm_analyst=None,
        llm_decision=None,
    )
    s.update(overrides)
    return s


def _otto_state(reliability_summary: dict, otto_status: str = "approved") -> dict:
    """bc_otto_node 호출용 최소 state."""
    return _base_state(
        emily_output={"market_regime": "bull", "regime_confidence": 0.7},
        portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1},
        dave_output={"risk_score": 0.4},
        reliability_summary=reliability_summary,
        _mock_otto_status=otto_status,  # 테스트 내에서 stub에 전달
    )


# ── bc_state 초기값 검증 ───────────────────────────────────────────────────────

class TestBcStateReliability:
    def test_initial_state_has_reliability_summary(self):
        s = make_initial_bc_state("2024-01-15", ["AAPL"], None, None)
        assert "reliability_summary" in s
        assert s["reliability_summary"] == {}

    def test_reliability_summary_is_dict_type(self):
        s = make_initial_bc_state("2024-01-15", ["AAPL"], None, None)
        assert isinstance(s["reliability_summary"], dict)


# ── bc_calibration_node reliability_summary 저장 검증 ────────────────────────

class TestCalibrationNodeReliability:
    def test_calibration_node_stores_reliability_summary(self):
        """run_calibration_audit()가 reliability_scores 반환 시 state에 저장됨."""
        mock_cal_result = {
            "calibration_scores": {},
            "propagation_audit": {},
            "reliability_scores": {
                "fundamental": 0.6,
                "sentiment": 0.55,
                "news": 0.58,
                "technical": 0.62,
                "researcher": 0.57,
                "trader": 0.53,
                "risk_manager": 0.60,
            },
            "gating_decisions": {},
            "flags": [],
        }

        with patch("calibration.run_calibration.run_calibration_audit", return_value=mock_cal_result), \
             patch("calibration.run_calibration.format_calibration_for_prompt", return_value="ctx"):
            state = _base_state()
            result = bc_calibration_node(state)

        assert "reliability_summary" in result
        assert result["reliability_summary"]["trader"] == 0.53

    def test_calibration_node_empty_reliability_scores(self):
        """run_calibration_audit()가 reliability_scores 없을 때 빈 dict 저장."""
        mock_cal_result = {
            "calibration_scores": {},
            "propagation_audit": {},
            "gating_decisions": {},
            "flags": [],
            # reliability_scores 없음
        }

        with patch("calibration.run_calibration.run_calibration_audit", return_value=mock_cal_result), \
             patch("calibration.run_calibration.format_calibration_for_prompt", return_value="ctx"):
            state = _base_state()
            result = bc_calibration_node(state)

        assert result.get("reliability_summary", {}) == {}

    def test_calibration_node_logs_below_floor_agents(self, caplog):
        """floor(0.35) 이하 agent가 있을 때 warning 로그 발생."""
        import logging
        mock_cal_result = {
            "reliability_scores": {"trader": 0.30, "risk_manager": 0.40},
            "gating_decisions": {},
            "flags": [],
        }

        with patch("calibration.run_calibration.run_calibration_audit", return_value=mock_cal_result), \
             patch("calibration.run_calibration.format_calibration_for_prompt", return_value="ctx"), \
             caplog.at_level(logging.WARNING, logger="graph.nodes.bc_calibration"):
            bc_calibration_node(_base_state())

        assert any("floor 이하" in r.message for r in caplog.records)


# ── bc_otto_node reliability gating 검증 ─────────────────────────────────────

def _mock_run_otto_approval(status: str):
    """run_otto_approval stub — 지정 status 반환."""
    def _stub(*args, **kwargs):
        return {"approval_status": status, "selected_policy": "test_policy"}
    return _stub


class TestOttoReliabilityGating:
    """bc_otto_node의 reliability floor 이하 → conditional_approval 강제 변환."""

    def _run_otto(self, reliability_summary: dict, otto_status: str = "approved") -> dict:
        state = _base_state(
            emily_output={"market_regime": "bull", "regime_confidence": 0.7},
            portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3, "hedge_pct": 0.1},
            dave_output={"risk_score": 0.4},
            reliability_summary=reliability_summary,
        )
        with patch("integration.otto_gate.run_otto_approval", side_effect=_mock_run_otto_approval(otto_status)), \
             patch("integration.otto_gate.apply_otto_decision", side_effect=lambda o, p: p):
            return bc_otto_node(state)

    # ── 1. reliability_summary 비어있음 → approved 그대로 ──────────────────────

    def test_empty_reliability_summary_approved_unchanged(self):
        result = self._run_otto(reliability_summary={}, otto_status="approved")
        assert result["otto_output"]["approval_status"] == "approved"

    # ── 2. 모든 핵심 agent floor 이상 → approved 유지 ─────────────────────────

    def test_all_above_floor_approved_unchanged(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.55, "risk_manager": 0.60, "researcher": 0.58},
            otto_status="approved",
        )
        assert result["otto_output"]["approval_status"] == "approved"

    # ── 3. trader floor 이하 → conditional_approval ───────────────────────────

    def test_trader_below_floor_forces_conditional_approval(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.30, "risk_manager": 0.60, "researcher": 0.58},
            otto_status="approved",
        )
        assert result["otto_output"]["approval_status"] == "conditional_approval"

    # ── 4. risk_manager floor 이하 → conditional_approval ────────────────────

    def test_risk_manager_below_floor_forces_conditional_approval(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.55, "risk_manager": 0.20, "researcher": 0.58},
            otto_status="approved",
        )
        assert result["otto_output"]["approval_status"] == "conditional_approval"

    # ── 5. researcher floor 이하 → conditional_approval ──────────────────────

    def test_researcher_below_floor_forces_conditional_approval(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.55, "risk_manager": 0.60, "researcher": 0.10},
            otto_status="approved",
        )
        assert result["otto_output"]["approval_status"] == "conditional_approval"

    # ── 6. 경계값: 정확히 floor(0.35) = 미달 아님 → approved 유지 ─────────────

    def test_exactly_at_floor_not_below_approved_unchanged(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.35, "risk_manager": 0.60, "researcher": 0.58},
            otto_status="approved",
        )
        # 0.35 < 0.35 는 False → gating 발동 안 됨
        assert result["otto_output"]["approval_status"] == "approved"

    # ── 7. 원래 rejected → gating 무관하게 rejected 유지 ─────────────────────

    def test_rejected_status_not_overridden_by_reliability_gating(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.10, "risk_manager": 0.10, "researcher": 0.10},
            otto_status="rejected",
        )
        # rejected는 gating 조건(status == "approved")을 충족하지 않으므로 변환 안 됨
        assert result["otto_output"]["approval_status"] == "rejected"

    # ── 8. 원래 conditional_approval → 그대로 유지 ────────────────────────────

    def test_already_conditional_approval_unchanged(self):
        result = self._run_otto(
            reliability_summary={"trader": 0.10, "risk_manager": 0.60, "researcher": 0.58},
            otto_status="conditional_approval",
        )
        assert result["otto_output"]["approval_status"] == "conditional_approval"

    # ── 9. reliability_summary에 핵심 agent 없으면 gating 미발동 ──────────────

    def test_missing_critical_agents_in_summary_approved_unchanged(self):
        """critical agent 키 자체가 없으면 기본값 처리 → gating 발동 안 됨."""
        result = self._run_otto(
            reliability_summary={"fundamental": 0.10, "sentiment": 0.10},
            otto_status="approved",
        )
        assert result["otto_output"]["approval_status"] == "approved"

    # ── 10. reliability 주입 확인: run_otto_approval에 agent_reliability 전달 ──

    def test_reliability_summary_passed_to_run_otto_approval(self):
        """bc_otto_node가 reliability_summary를 agent_reliability 인자로 전달함."""
        captured = {}

        def capture_stub(*args, **kwargs):
            captured["agent_reliability"] = kwargs.get("agent_reliability")
            return {"approval_status": "approved", "selected_policy": "p"}

        state = _base_state(
            emily_output={"market_regime": "bull", "regime_confidence": 0.7},
            portfolio={"total_equity_pct": 0.6, "cash_pct": 0.3},
            dave_output={"risk_score": 0.4},
            reliability_summary={"trader": 0.55, "risk_manager": 0.60},
        )
        with patch("integration.otto_gate.run_otto_approval", side_effect=capture_stub), \
             patch("integration.otto_gate.apply_otto_decision", side_effect=lambda o, p: p):
            bc_otto_node(state)

        assert captured.get("agent_reliability") == {"trader": 0.55, "risk_manager": 0.60}
