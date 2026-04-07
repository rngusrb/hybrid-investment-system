"""DAILY_EXECUTION_FEASIBILITY_CHECK node — 실행 가능성 검증."""
from graph.state import SystemState
from schemas.audit_schema import NodeResult

FEASIBILITY_THRESHOLD = 0.3


def daily_execution_feasibility_check(state: SystemState) -> SystemState:
    """
    Otto의 정책 패킷을 받아 실행 가능성 점수 산출.
    - feasibility_score < 0.3: execution_plan을 None으로 유지하고 WAIT_NEXT_BAR
    - feasibility_score >= 0.3: ORDER_PLAN_GENERATION으로 진행
    실제 구현에서는 ExecutionFeasibilityChecker 호출.
    """
    updated = dict(state)

    otto_output = state.get("otto_output") or {}
    approval_status = otto_output.get("approval_status", "rejected")
    policy_action = otto_output.get("policy_action", "hold")

    # feasibility score 계산 (실제는 market microstructure 기반)
    if approval_status == "approved" and policy_action == "execute":
        feasibility_score = 0.8
    elif approval_status == "conditional":
        feasibility_score = 0.5
    else:
        feasibility_score = 0.1

    updated["execution_feasibility_score"] = feasibility_score

    if feasibility_score < FEASIBILITY_THRESHOLD:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "DAILY_EXECUTION_FEASIBILITY_CHECK",
            "reason": f"feasibility_score={feasibility_score} below threshold {FEASIBILITY_THRESHOLD}",
            "date": state.get("current_date"),
        }]
        updated["next_node"] = "WAIT_NEXT_BAR"
    else:
        updated["next_node"] = "DAILY_ORDER_PLAN_GENERATION"

    return updated
