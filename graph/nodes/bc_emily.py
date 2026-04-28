"""graph/nodes/bc_emily.py — BC_EMILY 노드: Emily SPY 레짐 분석."""
import logging
logger = logging.getLogger(__name__)


def bc_emily_node(state: dict) -> dict:
    """
    Emily 에이전트로 SPY 시장 레짐 분석.
    실패 시 빈 emily_output/emily_context로 graceful continue.
    """
    try:
        from scripts.stock_pipeline import fetch_data
        from integration.emily_context import run_emily_for_context

        llm  = state.get("_llm_analyst")
        date = state["current_date"]

        spy_data = fetch_data("SPY", date)
        emily_output, emily_context = run_emily_for_context(llm, spy_data, date)

        logger.info(
            f"[BC_EMILY] regime={emily_output.get('market_regime','?')}  "
            f"conf={emily_output.get('regime_confidence',0):.2f}"
        )
        return {"emily_output": emily_output, "emily_context": emily_context}

    except Exception as e:
        logger.warning(f"[BC_EMILY] 실패: {e}", exc_info=True)
        errors = list(state.get("errors", []))
        errors.append({"node": "BC_EMILY", "error": str(e)})
        return {"emily_output": {}, "emily_context": "", "errors": errors}
