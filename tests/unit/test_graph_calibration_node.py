"""
tests/unit/test_graph_calibration_node.py
TASK-010: Dave Calibration shrinkage 활성화 검증.
graph/nodes/calibration.py — daily_signal_calibration()
"""
import pytest


def _make_state(dave_risk_score: float, stress_severity: float, risk_level: str = "medium") -> dict:
    """daily_signal_calibration 에 필요한 최소 state 구성."""
    return {
        "current_date": "2024-01-15",
        "dave_output": {
            "agent": "Dave",
            "date": "2024-01-15",
            "risk_score": dave_risk_score,
            "signal_conflict_risk": 0.3,
            "stress_test": {"severity_score": stress_severity, "worst_case_drawdown": 0.12},
            "risk_level": risk_level,
            "risk_components": {
                "beta": 0.5, "illiquidity": 0.3,
                "sector_concentration": 0.4, "volatility": 0.35,
            },
            "recommended_controls": [],
            "risk_constraints": {
                "max_single_sector_weight": 0.3,
                "max_beta": 1.2,
                "max_gross_exposure": 0.9,
            },
            "trigger_risk_alert_meeting": False,
        },
        "emily_output": None,
        "bob_output": None,
        "calibration_log": [],
    }


class TestDaveCalibrationShrinkage:
    """TASK-010: stress_severity 기반 shrinkage — high severity → 중립 방향으로 이동."""

    def test_high_severity_shrinks_toward_neutral(self):
        """risk_level=critical (severity=0.9) → calibrated risk_score closer to 0.5."""
        from graph.nodes.calibration import daily_signal_calibration

        # 충분한 rolling history 없으면 shrinkage 효과가 즉시 나타남
        state = _make_state(dave_risk_score=0.9, stress_severity=0.9, risk_level="critical")
        result = daily_signal_calibration(state)
        cal_score = result["dave_output"]["risk_score"]
        # severity=0.9 → confidence=0.1 → shrinkage toward 0.5
        # raw=0.9, expected calibrated < 0.9 and closer to 0.5
        assert cal_score < 0.9, f"Expected shrinkage from 0.9, got {cal_score}"
        assert cal_score > 0.5, f"Expected above 0.5 (not fully neutral), got {cal_score}"
        dist_raw = abs(0.9 - 0.5)
        dist_cal = abs(cal_score - 0.5)
        assert dist_cal < dist_raw, (
            f"Calibrated ({cal_score}) should be closer to 0.5 than raw (0.9)"
        )

    def test_low_severity_less_shrinkage(self):
        """severity=0.1 → confidence=0.9 → calibrated closer to raw."""
        from graph.nodes.calibration import daily_signal_calibration

        state = _make_state(dave_risk_score=0.9, stress_severity=0.1)
        result = daily_signal_calibration(state)
        cal_score_low = result["dave_output"]["risk_score"]

        state2 = _make_state(dave_risk_score=0.9, stress_severity=0.9, risk_level="critical")
        result2 = daily_signal_calibration(state2)
        cal_score_high = result2["dave_output"]["risk_score"]

        # 낮은 severity → calibrated가 raw에 더 가까움
        assert cal_score_low > cal_score_high, (
            f"Low severity ({cal_score_low}) should produce less shrinkage than high ({cal_score_high})"
        )

    def test_dave_score_propagated_to_state_risk_score(self):
        """dave_output.risk_score가 state.risk_score로 동기화됨."""
        from graph.nodes.calibration import daily_signal_calibration

        state = _make_state(dave_risk_score=0.7, stress_severity=0.4)
        result = daily_signal_calibration(state)
        assert result["risk_score"] == result["dave_output"]["risk_score"]

    def test_calibration_log_updated(self):
        """calibration_log에 Dave 필드 항목이 추가됨."""
        from graph.nodes.calibration import daily_signal_calibration

        state = _make_state(dave_risk_score=0.6, stress_severity=0.5)
        result = daily_signal_calibration(state)
        log = result.get("calibration_log", [])
        assert len(log) > 0
