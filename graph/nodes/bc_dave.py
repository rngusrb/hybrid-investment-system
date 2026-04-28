"""graph/nodes/bc_dave.py — BC_DAVE 노드: 포트폴리오 레벨 리스크 평가."""
import logging
logger = logging.getLogger(__name__)


def bc_dave_node(state: dict) -> dict:
    """
    Dave 에이전트로 Portfolio Manager 결과에 대한 리스크 평가.
    portfolio가 비어있으면 graceful skip.
    """
    from integration.dave_context import run_dave_for_portfolio

    llm_decision  = state.get("_llm_decision")
    portfolio     = state.get("portfolio", {})
    stock_results = state.get("stock_results", [])
    date          = state["current_date"]
    errors        = list(state.get("errors", []))

    if not portfolio:
        logger.warning("[BC_DAVE] portfolio 없음 — 스킵")
        return {"dave_output": {}, "errors": errors}

    try:
        dave_output, _ = run_dave_for_portfolio(
            llm_decision, portfolio, stock_results, date
        )
        risk_score = dave_output.get("risk_score", 0)
        logger.info(
            f"[BC_DAVE] risk_score={risk_score:.2f}  "
            f"level={dave_output.get('risk_level','?')}  "
            f"alert={dave_output.get('trigger_risk_alert_meeting', False)}"
        )
        return {"dave_output": dave_output, "errors": errors}

    except Exception as e:
        logger.warning(f"[BC_DAVE] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_DAVE", "error": str(e)})
        return {"dave_output": {}, "errors": errors}
