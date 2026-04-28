"""graph/nodes/bc_stock.py — BC_STOCK_ANALYSIS 노드: 종목별 B 파이프라인 순차 실행."""
import logging
logger = logging.getLogger(__name__)


def bc_stock_node(state: dict) -> dict:
    """
    tickers 목록에 대해 run_single_stock() 순차 실행.
    gating 적용 (hard_gate / downweight).
    개별 종목 실패 시 errors에 기록하고 계속 진행.
    """
    from scripts.portfolio_pipeline import run_single_stock

    llm          = state.get("_llm_analyst")
    llm_decision = state.get("_llm_decision")
    date         = state["current_date"]
    tickers      = state.get("tickers", [])
    gating       = state.get("gating", {})

    stock_results = []
    errors = list(state.get("errors", []))

    for ticker in tickers:
        try:
            result = run_single_stock(ticker, date, llm, llm_decision, gating=gating)
            stock_results.append(result)
            logger.info(f"[BC_STOCK] {ticker} 완료")
        except Exception as e:
            logger.warning(f"[BC_STOCK] {ticker} 실패: {e}", exc_info=True)
            errors.append({"node": "BC_STOCK", "ticker": ticker, "error": str(e)})

    return {"stock_results": stock_results, "errors": errors}
