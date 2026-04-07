"""DAILY_SIGNAL_CALIBRATION node — AgentCalibrator로 실제 score 보정.

spec 9.6: 모든 score 기반 specialist output은 상위 단계 전달 전 Calibration Layer 통과 필수.
Emily: regime_confidence, technical_confidence, reversal_risk
Bob: 선택된 전략의 confidence, technical_alignment
Dave: risk_score, signal_conflict_risk
"""
from graph.state import SystemState
from calibration.calibrator import AgentCalibrator

# module-level calibrator 인스턴스 (rolling history 유지)
_calibrators = {
    "emily": AgentCalibrator("emily", rolling_window=20, shrinkage_factor=0.3),
    "bob": AgentCalibrator("bob", rolling_window=20, shrinkage_factor=0.3),
    "dave": AgentCalibrator("dave", rolling_window=20, shrinkage_factor=0.3),
}


def daily_signal_calibration(state: SystemState) -> SystemState:
    """
    Emily / Bob / Dave output의 핵심 score 필드를 rolling_std + shrinkage로 보정.
    보정된 값을 state에 반영하고 CalibrationLog를 calibration_log에 추가.
    """
    updated = dict(state)
    current_date = state.get("current_date", "")
    new_cal_logs = []

    # ── Emily ──────────────────────────────────────────────────────────────
    emily = state.get("emily_output")
    if isinstance(emily, dict):
        emily_copy = dict(emily)

        # regime_confidence: rolling_std 보정
        rc = emily_copy.get("regime_confidence")
        if rc is not None:
            cal_rc, log_rc = _calibrators["emily"].calibrate(
                "regime_confidence", float(rc), current_date,
                confidence=float(rc), method="rolling_std"
            )
            emily_copy["regime_confidence"] = cal_rc
            new_cal_logs.append(log_rc.model_dump())

        # technical_signal_state 내부 필드 shrinkage
        ts = emily_copy.get("technical_signal_state")
        if isinstance(ts, dict):
            ts_copy = dict(ts)
            for field in ("technical_confidence", "reversal_risk", "continuation_strength"):
                val = ts_copy.get(field)
                if val is not None:
                    cal_val, log_val = _calibrators["emily"].calibrate(
                        field, float(val), current_date,
                        confidence=float(rc or 0.5), method="shrinkage"
                    )
                    ts_copy[field] = cal_val
                    new_cal_logs.append(log_val.model_dump())
            emily_copy["technical_signal_state"] = ts_copy

        updated["emily_output"] = emily_copy
        # state level technical_confidence 동기화
        updated["technical_confidence"] = emily_copy.get(
            "technical_signal_state", {}
        ).get("technical_confidence", state.get("technical_confidence", 0.5))

    # ── Bob ───────────────────────────────────────────────────────────────
    bob = state.get("bob_output")
    if isinstance(bob, dict):
        bob_copy = dict(bob)
        candidates = bob_copy.get("candidate_strategies", [])
        cal_candidates = []
        for c in candidates:
            c_copy = dict(c)
            for field in ("confidence", "technical_alignment", "regime_fit"):
                val = c_copy.get(field)
                if val is not None:
                    cal_val, log_val = _calibrators["bob"].calibrate(
                        field, float(val), current_date,
                        confidence=float(c_copy.get("confidence", 0.5)), method="rolling_std"
                    )
                    c_copy[field] = cal_val
                    new_cal_logs.append(log_val.model_dump())
            cal_candidates.append(c_copy)
        bob_copy["candidate_strategies"] = cal_candidates
        updated["bob_output"] = bob_copy

    # ── Dave ──────────────────────────────────────────────────────────────
    dave = state.get("dave_output")
    if isinstance(dave, dict):
        dave_copy = dict(dave)
        dave_risk_score = float(dave_copy.get("risk_score") or 0.5)
        dave_confidence = min(0.5 + abs(dave_risk_score - 0.5), 0.9)
        for field in ("risk_score", "signal_conflict_risk"):
            val = dave_copy.get(field)
            if val is not None:
                cal_val, log_val = _calibrators["dave"].calibrate(
                    field, float(val), current_date,
                    confidence=dave_confidence, method="clipping"
                )
                dave_copy[field] = cal_val
                new_cal_logs.append(log_val.model_dump())
        updated["dave_output"] = dave_copy
        # state level risk_score 동기화
        updated["risk_score"] = dave_copy.get("risk_score", state.get("risk_score", 0.0))

    # ── uncertainty_level ─────────────────────────────────────────────────
    emily_out = updated.get("emily_output") or {}
    uncertainty_reasons = emily_out.get("uncertainty_reasons", [])
    updated["uncertainty_level"] = min(len(uncertainty_reasons) * 0.1, 0.9)

    # calibration_log 누적
    updated["calibration_log"] = list(state.get("calibration_log", [])) + new_cal_logs + [{
        "date": current_date,
        "node": "DAILY_SIGNAL_CALIBRATION",
        "fields_calibrated": len(new_cal_logs),
    }]

    updated["next_node"] = "DAILY_AGENT_RELIABILITY_UPDATE"
    return updated
