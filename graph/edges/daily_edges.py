"""일간 전이 규칙 — state 기반 conditional edge."""
from graph.state import SystemState


def route_after_risk_check(state: SystemState) -> str:
    """
    risk check 후 다음 노드 결정.
    state의 risk_alert_triggered와 risk_score를 실제로 확인.
    """
    if state.get("risk_alert_triggered", False):
        return "RISK_ALERT_MEETING"

    execution_score = state.get("execution_feasibility_score", 0.5)
    if execution_score < 0.3:
        return "WAIT_NEXT_BAR"  # execution 불가

    return "DAILY_POLICY_SELECTION"


def route_after_policy(state: SystemState) -> str:
    """정책 선택 후 execution feasibility check 또는 wait."""
    otto_output = state.get("otto_output")
    if otto_output is None:
        return "WAIT_NEXT_BAR"

    approval = otto_output.get("approval_status", "rejected")
    if approval == "rejected":
        return "WAIT_NEXT_BAR"

    return "DAILY_EXECUTION_FEASIBILITY_CHECK"


def route_after_ingest(state: SystemState) -> str:
    """ingest 후 다음 노드."""
    return state.get("next_node", "UPDATE_MARKET_MEMORY")


def route_daily_end(state: SystemState) -> str:
    """일간 종료 후 주간 meeting 필요 여부."""
    if state.get("is_week_end", False):
        return "WEEKLY_MARKET_ANALYSIS_MEETING"
    return "WAIT_NEXT_BAR"
