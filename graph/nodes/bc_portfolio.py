"""graph/nodes/bc_portfolio.py — BC_PORTFOLIO_MANAGER 노드: 최종 포트폴리오 배분 결정.

Otto rejected 재실행 시 otto_feedback이 state에 있으면 user 메시지에 주입.
"""
import logging
logger = logging.getLogger(__name__)


def bc_portfolio_node(state: dict) -> dict:
    """Portfolio Manager 실행. Otto rejected 재실행 시 거부 이유 주입."""
    from scripts.portfolio_pipeline import run_portfolio_manager

    llm_decision        = state.get("_llm_decision")
    date                = state["current_date"]
    stock_results       = state.get("stock_results", [])
    memory_context      = state.get("memory_context", "")
    emily_context       = state.get("emily_context", "")
    sim_context         = state.get("sim_context", "")
    meetings_context    = state.get("meetings_context", "")
    calibration_context = state.get("calibration_context", "")
    otto_feedback       = state.get("otto_feedback", "")
    retry_count         = state.get("otto_retry_count", 0)
    errors              = list(state.get("errors", []))

    if not stock_results:
        logger.warning("[BC_PORTFOLIO] stock_results 없음 — 스킵")
        return {"portfolio": {}, "errors": errors}

    if retry_count > 0:
        logger.info(f"[BC_PORTFOLIO] Otto rejected 재실행 (시도 {retry_count + 1})")

    try:
        portfolio = run_portfolio_manager(
            llm_decision, date, stock_results,
            memory_context=memory_context,
            emily_context=emily_context,
            sim_context=sim_context,
            meetings_context=meetings_context,
            calibration_context=calibration_context,
            otto_feedback=otto_feedback,
        )
        eq   = portfolio.get("total_equity_pct", 0) * 100
        cash = portfolio.get("cash_pct", 0) * 100
        logger.info(f"[BC_PORTFOLIO] equity={eq:.0f}%  cash={cash:.0f}%")
        return {"portfolio": portfolio, "errors": errors}

    except Exception as e:
        logger.warning(f"[BC_PORTFOLIO] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_PORTFOLIO", "error": str(e)})
        return {"portfolio": {}, "errors": errors}
