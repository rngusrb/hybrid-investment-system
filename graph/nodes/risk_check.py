"""DAILY_RISK_CHECK node — risk_score 낮고 regime stable하면 경량화."""
from graph.state import SystemState
from schemas.audit_schema import NodeResult
from tools.technical import TechnicalAnalyzer

_tech_analyzer = TechnicalAnalyzer()

RISK_ALERT_THRESHOLD = 0.75
LIGHTWEIGHT_THRESHOLD = 0.3  # risk 낮으면 경량화 허용


def daily_risk_check(state: SystemState) -> SystemState:
    """
    Dave의 risk_score 확인.
    - risk_score > 0.75: risk_alert_triggered = True
    - risk_score < 0.3 AND regime stable: 경량화 (skip_log 기록)
    """
    updated = dict(state)
    dave_output = state.get("dave_output")

    if dave_output is None:
        # Dave output 없으면 보수적으로 medium risk 가정
        updated["risk_score"] = 0.5
        updated["risk_alert_triggered"] = False
        updated["next_node"] = "DAILY_POLICY_SELECTION"
        return updated

    risk_score = dave_output.get("risk_score", 0.5)

    # 기술적 신호 기반 risk_score 보정
    emily_output = state.get("emily_output") or {}
    ts = emily_output.get("technical_signal_state") or {}
    reversal_risk = float(ts.get("reversal_risk", 0.0))
    technical_confidence = float(ts.get("technical_confidence", 0.5))

    # reversal_risk 높고 technical_confidence 낮으면 risk_score 상향
    tech_risk_adjustment = reversal_risk * (1.0 - technical_confidence) * 0.15
    adjusted_risk_score = min(risk_score + tech_risk_adjustment, 1.0)

    if adjusted_risk_score != risk_score:
        updated["calibration_log"] = list(state.get("calibration_log", [])) + [{
            "node": "DAILY_RISK_CHECK",
            "type": "tech_risk_adjustment",
            "original_risk_score": risk_score,
            "adjusted_risk_score": round(adjusted_risk_score, 4),
            "reversal_risk": reversal_risk,
            "technical_confidence": technical_confidence,
            "date": state.get("current_date", ""),
        }]
        risk_score = adjusted_risk_score
        updated["risk_score"] = risk_score

    updated["risk_score"] = risk_score

    # risk alert 트리거
    if risk_score > RISK_ALERT_THRESHOLD:
        updated["risk_alert_triggered"] = True
        updated["next_node"] = "RISK_ALERT_MEETING"
        updated["flow_decision_reason"] = f"risk_score={risk_score} exceeds threshold {RISK_ALERT_THRESHOLD}"
        return updated

    # 경량화 조건: risk 낮고 regime stable
    regime = (state.get("emily_output") or {}).get("market_regime", "mixed")
    is_stable_regime = regime in ("risk_on",)

    if risk_score < LIGHTWEIGHT_THRESHOLD and is_stable_regime:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "DAILY_RISK_CHECK",
            "reason": f"risk_score={risk_score} low and regime={regime} stable — lightweight mode",
            "date": state.get("current_date"),
        }]
        updated["flow_decision_reason"] = "lightweight risk check"

    updated["risk_alert_triggered"] = False
    updated["next_node"] = "DAILY_POLICY_SELECTION"
    return updated
