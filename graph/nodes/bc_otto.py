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
    from graph.nodes.bc_portfolio import _compute_execution_feasibility

    llm_decision       = state.get("_llm_decision")
    date               = state["current_date"]
    emily_output       = state.get("emily_output", {})
    sim_results        = state.get("sim_results", {})
    dave_output        = state.get("dave_output", {})
    portfolio          = state.get("portfolio", {})
    retry_count           = state.get("otto_retry_count", 0)
    reliability_summary   = state.get("reliability_summary", {})
    # Dave가 Portfolio 이후에 실행되므로 state의 feasibility는 stale.
    # 현재 dave_output 기준으로 즉시 재산출.
    execution_feasibility = _compute_execution_feasibility(portfolio, sim_results, dave_output)
    errors                = list(state.get("errors", []))

    if not emily_output or not portfolio:
        logger.warning("[BC_OTTO] emily_output 또는 portfolio 없음 — 스킵")
        return {"otto_output": {}, "errors": errors}

    try:
        otto_output = run_otto_approval(
            llm_decision, date,
            emily_output, sim_results, dave_output, portfolio,
            agent_reliability=reliability_summary or None,
        )

        # Reliability gating: 핵심 agent가 floor 이하이면 conditional_approval 강제 적용
        _FLOOR = 0.35
        _CRITICAL_AGENTS = ["trader", "risk_manager", "researcher"]
        below_floor = [
            a for a in _CRITICAL_AGENTS
            if isinstance(reliability_summary.get(a), (int, float))
            and reliability_summary[a] < _FLOOR
        ]
        status = otto_output.get("approval_status", "approved")
        if below_floor and status == "approved":
            otto_output = dict(otto_output)
            otto_output["approval_status"] = "conditional_approval"
            status = "conditional_approval"
            logger.warning(
                f"[BC_OTTO] reliability floor 이하 agents={below_floor} → conditional_approval 강제 적용"
            )
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

        # Execution feasibility gating: score 낮으면 staggered 강제 적용
        _FEASIBILITY_THRESHOLD = 0.4
        feasibility_score = float(execution_feasibility.get("feasibility_score", 1.0))
        if feasibility_score < _FEASIBILITY_THRESHOLD and status in ("approved", "conditional_approval"):
            otto_output = dict(otto_output)
            execution_plan = dict(otto_output.get("execution_plan") or {})
            execution_plan["execution_style"] = "staggered"
            otto_output["execution_plan"] = execution_plan
            logger.warning(
                f"[BC_OTTO] feasibility_score={feasibility_score:.2f} < {_FEASIBILITY_THRESHOLD} "
                f"→ execution_style=staggered 강제 적용"
            )

        # approved / conditional_approval → portfolio 즉시 조정
        adjusted_portfolio = apply_otto_decision(otto_output, portfolio)
        if feasibility_score < _FEASIBILITY_THRESHOLD:
            adjusted_portfolio = dict(adjusted_portfolio)
            adjusted_portfolio["execution_style"] = "staggered"

        # Uncertainty Propagation 링크 3:
        # Dave risk_score > 0.7 + Emily regime_confidence < 0.55 → exposure shrinkage
        _RISK_SHRINK_THRESHOLD   = 0.7
        _UNCERTAINTY_THRESHOLD   = 0.55
        _SHRINK_FACTOR           = 0.85
        dave_risk    = float(dave_output.get("risk_score", 0.0)) if dave_output else 0.0
        emily_conf   = float(emily_output.get("regime_confidence", 1.0)) if emily_output else 1.0
        if (dave_risk > _RISK_SHRINK_THRESHOLD
                and emily_conf < _UNCERTAINTY_THRESHOLD
                and status in ("approved", "conditional_approval")):
            adjusted_portfolio = dict(adjusted_portfolio)
            old_equity = float(adjusted_portfolio.get("total_equity_pct", 0.6))
            new_equity = round(old_equity * _SHRINK_FACTOR, 4)
            cash_delta = round(old_equity - new_equity, 4)
            adjusted_portfolio["total_equity_pct"] = new_equity
            adjusted_portfolio["cash_pct"] = round(
                float(adjusted_portfolio.get("cash_pct", 0.3)) + cash_delta, 4
            )
            adjusted_portfolio["exposure_shrinkage_applied"] = True
            logger.warning(
                f"[BC_OTTO] uncertainty propagation: dave_risk={dave_risk:.2f} > {_RISK_SHRINK_THRESHOLD} "
                f"AND emily_conf={emily_conf:.2f} < {_UNCERTAINTY_THRESHOLD} "
                f"→ equity shrinkage {old_equity:.2f} → {new_equity:.2f}"
            )

        return {
            "otto_output": otto_output,
            "portfolio":   adjusted_portfolio,
            "errors":      errors,
        }

    except Exception as e:
        logger.warning(f"[BC_OTTO] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_OTTO", "error": str(e)})
        return {"otto_output": {}, "errors": errors}
