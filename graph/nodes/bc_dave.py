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
    sim_results   = state.get("sim_results", {})
    date          = state["current_date"]
    errors        = list(state.get("errors", []))

    if not portfolio:
        logger.warning("[BC_DAVE] portfolio 없음 — 스킵")
        return {"dave_output": {}, "errors": errors}

    try:
        dave_output, _ = run_dave_for_portfolio(
            llm_decision, portfolio, stock_results, date
        )

        # Uncertainty Propagation 링크 2:
        # strategy_confidence 낮음(avg_sharpe < 0.5) → stress multiplier 상향
        sharpe_vals = [
            float((s.get("best") or {}).get("sharpe", 0.0))
            for s in sim_results.values() if isinstance(s, dict)
        ]
        avg_sharpe = sum(sharpe_vals) / max(len(sharpe_vals), 1)
        _STRATEGY_CONFIDENCE_THRESHOLD = 0.5
        if avg_sharpe < _STRATEGY_CONFIDENCE_THRESHOLD and sim_results:
            stress_mult = round(1.0 + (_STRATEGY_CONFIDENCE_THRESHOLD - avg_sharpe) * 0.2, 4)
            stress_mult = min(stress_mult, 1.15)  # 최대 15%
            original_risk = float(dave_output.get("risk_score", 0.5))
            dave_output = dict(dave_output)
            dave_output["risk_score"] = round(min(1.0, original_risk * stress_mult), 4)
            dave_output["stress_multiplier_applied"] = stress_mult
            logger.info(
                f"[BC_DAVE] strategy_confidence 낮음 (avg_sharpe={avg_sharpe:.2f} < {_STRATEGY_CONFIDENCE_THRESHOLD}) "
                f"→ stress_multiplier={stress_mult:.4f} 적용 "
                f"risk_score: {original_risk:.2f} → {dave_output['risk_score']:.2f}"
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
