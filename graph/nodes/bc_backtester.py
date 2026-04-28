"""graph/nodes/bc_backtester.py — BC_BACKTESTER 노드: 전략 Pool 백테스트.

risk_mode="defensive" 시 Dave risk > 0.7 트리거 재실행.
emily_output을 emily_context로 전달해 레짐 기반 Sharpe 보정 활성화.
"""
import logging
logger = logging.getLogger(__name__)


def bc_backtester_node(state: dict) -> dict:
    """
    stock_results의 각 종목 bars로 backtest_all() 실행.

    risk_mode: state에서 읽음 ("normal" | "defensive").
      - "normal"    : 첫 실행 (Meetings 전)
      - "defensive" : Dave risk > 0.7 트리거 재실행

    emily_output: regime-aware Sharpe 보정에 사용.
    """
    from simulation.backtester import backtest_all, save_sim_result, format_sim_for_prompt

    date          = state["current_date"]
    stock_results = state.get("stock_results", [])
    emily_output  = state.get("emily_output") or {}
    w_real        = state.get("w_real", 0.5)
    risk_mode     = state.get("risk_mode", "normal")

    sim_results = {}
    errors = list(state.get("errors", []))

    for r in stock_results:
        ticker = r["ticker"]
        bars   = r.get("bars", [])
        try:
            sim = backtest_all(
                bars,
                ticker=ticker,
                as_of=date,
                w_real=w_real,
                emily_context=emily_output or {},
                risk_mode=risk_mode,
            )
            save_sim_result(sim)
            sim_results[ticker] = sim
            logger.info(
                f"[BC_BACKTESTER] {ticker} strategy={sim['selected_strategy']}  "
                f"Sharpe={sim['best'].get('sharpe',0):.2f}  risk_mode={risk_mode}"
            )
        except Exception as e:
            logger.warning(f"[BC_BACKTESTER] {ticker} 실패: {e}", exc_info=True)
            errors.append({"node": "BC_BACKTESTER", "ticker": ticker, "error": str(e)})

    sim_context = format_sim_for_prompt(sim_results)
    return {"sim_results": sim_results, "sim_context": sim_context, "errors": errors}
