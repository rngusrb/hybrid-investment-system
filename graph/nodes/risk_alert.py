"""RISK_ALERT_MEETING node — event-driven 위기 대응."""
from graph.state import SystemState
from schemas.audit_schema import NodeResult


def risk_alert_meeting(state: SystemState) -> SystemState:
    """
    risk_score가 임계값을 초과했을 때 긴급 meeting 실행.
    Otto의 de-risk 정책 적용 또는 wait 결정.
    실제 구현에서는 RiskAlertMeeting(state).run() 호출.
    """
    updated = dict(state)

    risk_score = state.get("risk_score", 0.75)
    current_date = state.get("current_date")

    # 긴급 정책 결정 (실제는 RiskAlertMeeting)
    if risk_score >= 0.9:
        # 극단적 위기 → 완전 hold
        approval_status = "rejected"
        policy_action = "full_hold"
        flow_reason = f"extreme risk_score={risk_score} — full hold enforced"
    else:
        # 부분적 de-risk
        approval_status = "conditional"
        policy_action = "de_risk"
        flow_reason = f"risk_score={risk_score} — partial de-risk"

    updated["otto_output"] = {
        "approval_status": approval_status,
        "policy_action": policy_action,
        "risk_score_at_decision": risk_score,
        "emergency_meeting": True,
    }
    updated["risk_alert_triggered"] = False  # meeting 처리 완료
    updated["flow_decision_reason"] = flow_reason

    updated["propagation_audit_log"] = list(state.get("propagation_audit_log", [])) + [{
        "date": current_date,
        "node": "RISK_ALERT_MEETING",
        "risk_score": risk_score,
        "policy_action": policy_action,
    }]

    updated["next_node"] = "DAILY_EXECUTION_FEASIBILITY_CHECK" if approval_status == "conditional" else "WAIT_NEXT_BAR"
    return updated
