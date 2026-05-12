"""graph/nodes/bc_portfolio.py — BC_PORTFOLIO_MANAGER 노드: 최종 포트폴리오 배분 결정.

Otto rejected 재실행 시 otto_feedback이 state에 있으면 user 메시지에 주입.
"""
import logging
logger = logging.getLogger(__name__)


def _compute_execution_feasibility(
    portfolio: dict,
    sim_results: dict,
    dave_output: dict,
) -> dict:
    """
    Execution feasibility score 계산.
    score < 0.4 → bc_otto에서 staggered/hold 처리.

    구성 요소:
    - sharpe_score   (0.4 가중): 전략 평균 Sharpe [0, 2] → [0, 1]
    - cash_score     (0.3 가중): 포트폴리오 현금 비중 → 여유 클수록 높음
    - risk_feasibility (0.3 가중): 1 - dave_risk_score
    """
    sharpe_vals = [
        float((s.get("best") or {}).get("sharpe", 0.0))
        for s in sim_results.values() if isinstance(s, dict)
    ]
    avg_sharpe = sum(sharpe_vals) / max(len(sharpe_vals), 1)
    sharpe_score = min(max(avg_sharpe / 2.0, 0.0), 1.0)

    cash_pct = float(portfolio.get("cash_pct", 0.3))
    cash_score = min(cash_pct * 2.0, 1.0)

    risk_score = float((dave_output or {}).get("risk_score", 0.5))
    risk_feas = 1.0 - risk_score

    score = round(0.4 * sharpe_score + 0.3 * cash_score + 0.3 * risk_feas, 4)

    turnover_vals = [
        float((s.get("best") or {}).get("turnover", 0.3))
        for s in sim_results.values() if isinstance(s, dict)
    ]
    avg_turnover = sum(turnover_vals) / max(len(turnover_vals), 1)

    return {
        "feasibility_score":  score,
        "rebalance_urgency":  round(min(avg_turnover, 0.9), 4),
        "avg_sharpe":         round(avg_sharpe, 4),
        "cash_pct":           cash_pct,
        "dave_risk_score":    risk_score,
    }


def bc_portfolio_node(state: dict) -> dict:
    """Portfolio Manager 실행. Otto rejected 재실행 시 거부 이유 주입."""
    from scripts.portfolio_pipeline import run_portfolio_manager

    llm_decision        = state.get("_llm_decision")
    date                = state["current_date"]
    stock_results       = state.get("stock_results", [])
    sim_results         = state.get("sim_results", {})
    dave_output         = state.get("dave_output", {})
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
        feasibility = _compute_execution_feasibility(portfolio, sim_results, dave_output)
        eq   = portfolio.get("total_equity_pct", 0) * 100
        cash = portfolio.get("cash_pct", 0) * 100
        logger.info(
            f"[BC_PORTFOLIO] equity={eq:.0f}%  cash={cash:.0f}%  "
            f"feasibility={feasibility['feasibility_score']:.2f}"
        )
        return {
            "portfolio":            portfolio,
            "execution_feasibility": feasibility,
            "errors":               errors,
        }

    except Exception as e:
        logger.warning(f"[BC_PORTFOLIO] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_PORTFOLIO", "error": str(e)})
        return {"portfolio": {}, "errors": errors}
