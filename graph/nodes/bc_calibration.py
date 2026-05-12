"""graph/nodes/bc_calibration.py — BC_CALIBRATION 노드: 신뢰도 감사 + gating 갱신."""
import logging
logger = logging.getLogger(__name__)


def bc_calibration_node(state: dict) -> dict:
    """Calibration 감사 실행. gating 결정을 state에 갱신."""
    from calibration.run_calibration import run_calibration_audit, format_calibration_for_prompt

    stock_results = state.get("stock_results", [])
    sim_results   = state.get("sim_results", {})
    date          = state["current_date"]
    errors        = list(state.get("errors", []))

    try:
        cal_result = run_calibration_audit(stock_results, sim_results, date)
        calibration_context = format_calibration_for_prompt(cal_result)

        # gating 갱신 (이번 사이클 calibration 결과 반영)
        new_gating = cal_result.get("gating_decisions", state.get("gating", {}))

        flags = cal_result.get("flags", [])
        hard_gated = [a for a, g in new_gating.items() if g == "hard_gate"]
        if hard_gated:
            logger.warning(f"[BC_CALIBRATION] HARD_GATE: {hard_gated}")
        for flag in flags[:3]:
            logger.info(f"[BC_CALIBRATION] {flag}")

        reliability_summary = cal_result.get("reliability_scores", {})
        below_floor = [a for a, s in reliability_summary.items() if isinstance(s, (int, float)) and s < 0.35]
        if below_floor:
            logger.warning(f"[BC_CALIBRATION] reliability floor 이하: {below_floor}")

        return {
            "calibration":        cal_result,
            "calibration_context": calibration_context,
            "gating":             new_gating,
            "reliability_summary": reliability_summary,
            "errors":             errors,
        }

    except Exception as e:
        logger.warning(f"[BC_CALIBRATION] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_CALIBRATION", "error": str(e)})
        return {"calibration": {}, "calibration_context": "", "errors": errors}
