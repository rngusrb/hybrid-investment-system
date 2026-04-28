"""graph/nodes/bc_otto.py — BC_OTTO 노드: 최종 승인 게이트.

approval_status에 따라 portfolio 조정.
rejected 시 otto_feedback + otto_retry_count를 state에 기록 (conditional edge가 PM으로 회송).
"""
import logging
logger = logging.getLogger(__name__)


def bc_otto_node(state: dict) -> dict:
    """
    Otto 승인 게이트 실행.
    - approved / conditional_approval: apply_otto_decision으로 portfolio 조정
    - rejected: otto_feedback 생성, otto_retry_count 증가 (route_after_otto가 PM으로 회송)
    """
    from integration.otto_gate import run_otto_approval, apply_otto_decision

    llm_decision  = state.get("_llm_decision")
    date          = state["current_date"]
    emily_output  = state.get("emily_output", {})
    sim_results   = state.get("sim_results", {})
    dave_output   = state.get("dave_output", {})
    portfolio     = state.get("portfolio", {})
    retry_count   = state.get("otto_retry_count", 0)
    errors        = list(state.get("errors", []))

    if not emily_output or not portfolio:
        logger.warning("[BC_OTTO] emily_output 또는 portfolio 없음 — 스킵")
        return {"otto_output": {}, "errors": errors}

    try:
        otto_output = run_otto_approval(
            llm_decision, date,
            emily_output, sim_results, dave_output, portfolio,
        )
        status = otto_output.get("approval_status", "approved")
        logger.info(
            f"[BC_OTTO] status={status}  "
            f"policy={otto_output.get('selected_policy','?')}  "
            f"retry_count={retry_count}"
        )

        if status == "rejected":
            # PM 재실행을 위한 피드백 생성 (portfolio는 아직 조정 안 함)
            reasons = otto_output.get("execution_plan", {}).get("rationale", "")
            otto_feedback = (
                f"[OTTO 거부 #{retry_count + 1}] 이전 배분이 거부됨. "
                f"거부 이유: {reasons or '리스크 과다'} "
                f"더 보수적인 배분(현금 비중 상향, 고위험 포지션 축소)으로 재배분하라."
            )
            return {
                "otto_output":      otto_output,
                "otto_feedback":    otto_feedback,
                "otto_retry_count": retry_count + 1,
                "errors":           errors,
                # portfolio는 그대로 유지 (PM이 재실행 후 덮어씀)
            }

        # approved / conditional_approval → portfolio 즉시 조정
        adjusted_portfolio = apply_otto_decision(otto_output, portfolio)
        return {
            "otto_output": otto_output,
            "portfolio":   adjusted_portfolio,
            "errors":      errors,
        }

    except Exception as e:
        logger.warning(f"[BC_OTTO] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_OTTO", "error": str(e)})
        return {"otto_output": {}, "errors": errors}
