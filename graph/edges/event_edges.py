"""event-driven 전이 규칙."""
from graph.state import SystemState


def route_after_risk_alert(state: SystemState) -> str:
    """risk alert meeting 후 — de-risk 처리 또는 정책 재선택."""
    otto_output = state.get("otto_output")
    if otto_output and otto_output.get("approval_status") == "rejected":
        return "WAIT_NEXT_BAR"
    return "DAILY_EXECUTION_FEASIBILITY_CHECK"
