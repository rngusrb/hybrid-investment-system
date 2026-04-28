"""integration/otto_gate.py — Otto 최종 승인 게이트.

Pipeline B/C용 어댑터:
  Emily(시장 레짐) + sim_results(전략 Pool) + Dave(포트폴리오 리스크) + portfolio
  → Otto 승인 → apply_otto_decision으로 portfolio 조정.

compute_adaptive_weights() 연결:
  strategy_memory.json에서 reward_history 로드 → w_sim/w_real 계산.
  (이전까지 이 함수가 실제 reward_history로 호출된 적 없었음 — TASK-003)

DEV_GUIDE.md 전역 금지사항 1번: Otto에 raw data(bars, articles) 절대 금지.
  _FORBIDDEN_RAW_FIELDS frozenset 검사가 run() 진입 시 실행됨.
"""
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.otto import OttoAgent

_OTTO_CONFIG = {
    "name": "Otto",
    "system_prompt_path": "prompts/otto_system.md",
    "temperature": 0.2,
    "max_tokens": 4096,
    "max_retries": 3,
}

_STRATEGY_MEM_PATH = ROOT / "results" / "strategy_memory.json"


def _load_reward_history(n: int = 10) -> list[dict]:
    """
    strategy_memory.json에서 r_sim + r_real이 모두 있는 최근 n개 레코드 추출.
    파일이 없거나 손상된 경우 빈 리스트 반환 (Silent Failure 방지).
    """
    try:
        if not _STRATEGY_MEM_PATH.exists():
            return []
        raw = json.loads(_STRATEGY_MEM_PATH.read_text())
        history = []
        for record in raw.values():
            if not isinstance(record, dict):
                continue
            val = record.get("value") or record
            r_sim = val.get("r_sim")
            r_real = val.get("r_real")
            if r_sim is not None and r_real is not None:
                history.append({"r_sim": float(r_sim), "r_real": float(r_real)})
        return history[-n:]
    except Exception:
        return []


def build_otto_input(
    emily_output: dict,
    sim_results: dict,
    dave_output: dict,
    portfolio: dict,
    date: str,
    adaptive_weights: Optional[dict] = None,
    agent_reliability: Optional[dict] = None,
) -> dict:
    """
    B/C 컨텍스트용 Otto 입력 패킷 구성.

    transforms/all_to_otto.py의 OttoPolicyPacket과 논리적으로 동일하지만
    BobToDavePacket/BobToExecutionPacket 대신 sim_results(backtester 출력)를 사용.

    raw market data 포함 금지 — _FORBIDDEN_RAW_FIELDS 검사 통과해야 함.
    (bars, articles, raw_market_data, ohlcv 등 절대 포함 금지)
    """
    ts = (emily_output.get("technical_signal_state") or {})
    reliability = agent_reliability or {"emily": 0.5, "bob": 0.5, "dave": 0.5}
    aw = adaptive_weights or {"w_sim": 0.5, "w_real": 0.5}

    # sim_results: {"AAPL": {selected_strategy, best: {sharpe, mdd, ...}}, ...}
    # 전략 Pool 요약 (Bob 역할 대리)
    selected_strategies = []
    avg_sharpe = 0.0
    strategy_count = 0
    for ticker_sim in sim_results.values():
        if not isinstance(ticker_sim, dict):
            continue
        strat = ticker_sim.get("selected_strategy", "")
        if strat:
            selected_strategies.append(strat)
        best = ticker_sim.get("best") or {}
        sharpe = best.get("sharpe")
        if sharpe is not None:
            avg_sharpe += float(sharpe)
            strategy_count += 1

    if strategy_count > 0:
        avg_sharpe /= strategy_count

    # 가장 많이 선택된 전략
    if selected_strategies:
        strategy_name = max(set(selected_strategies), key=selected_strategies.count)
    else:
        strategy_name = "defensive"

    # Dave 요약 (없으면 기본값)
    risk_score = float(dave_output.get("risk_score", 0.3)) if dave_output else 0.3
    risk_level = dave_output.get("risk_level", "medium") if dave_output else "medium"
    risk_constraints = (
        (dave_output.get("risk_constraints") or {})
        if dave_output
        else {"max_single_sector_weight": 0.4, "max_beta": 1.5, "max_gross_exposure": 1.0}
    )
    trigger_risk_alert = bool(dave_output.get("trigger_risk_alert_meeting", False)) if dave_output else False

    return {
        # Emily 요약
        "market_regime": emily_output.get("market_regime", "mixed"),
        "regime_confidence": float(emily_output.get("regime_confidence", 0.5)),
        "market_bias": emily_output.get("recommended_market_bias", "neutral"),
        "technical_direction": ts.get("trend_direction", "mixed"),
        "technical_confidence": float(ts.get("technical_confidence", 0.5)),
        "reversal_risk": float(ts.get("reversal_risk", 0.3)),
        "market_uncertainty": min(
            len(emily_output.get("uncertainty_reasons") or []) * 0.1, 0.9
        ),
        # Bob 대리 (backtester 전략 Pool 요약)
        "selected_strategy_name": strategy_name,
        "strategy_confidence": min(max(avg_sharpe / 3.0, 0.0), 1.0),  # Sharpe [0,3] → [0,1]
        "technical_alignment": float(ts.get("technical_confidence", 0.5)),
        "failure_conditions": emily_output.get("bear_catalysts") or [],
        # Dave 요약
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_constraints": risk_constraints,
        "trigger_risk_alert": trigger_risk_alert,
        # Execution (portfolio 정보 기반)
        "rebalance_urgency": float(portfolio.get("rebalance_urgency", 0.5)),
        "execution_constraints_hint": [portfolio.get("entry_style", "staggered")],
        # Portfolio 요약 (Otto의 approval_status 결정 근거)
        "portfolio_summary": {
            "total_equity_pct": portfolio.get("total_equity_pct", 0.6),
            "cash_pct": portfolio.get("cash_pct", 0.3),
            "hedge_pct": portfolio.get("hedge_pct", 0.1),
            "portfolio_risk_level": portfolio.get("portfolio_risk_level", "medium"),
            "n_allocations": len(portfolio.get("allocations") or []),
        },
        # Reliability + Adaptive Weights
        "agent_reliability_summary": reliability,
        "recent_reward_summary": {
            "w_sim": aw.get("w_sim", 0.5),
            "w_real": aw.get("w_real", 0.5),
        },
        # 날짜
        "date": date,
    }


def run_otto_approval(
    llm_decision,
    date: str,
    emily_output: dict,
    sim_results: dict,
    dave_output: dict,
    portfolio: dict,
    agent_reliability: Optional[dict] = None,
) -> dict:
    """
    Otto 최종 승인 게이트 실행.

    compute_adaptive_weights()를 strategy_memory.json의 실제 reward_history로 호출.
    (이전까지 한 번도 실제 history로 호출되지 않았던 함수 — TASK-003 핵심)

    Args:
        llm_decision: LLM provider (decision tier)
        date: 실행 날짜
        emily_output: run_emily_for_context() 결과 dict
        sim_results: {ticker: backtest_all() 결과} dict
        dave_output: run_dave_for_portfolio() 결과 dict
        portfolio: run_portfolio_manager() 결과 dict
        agent_reliability: 에이전트별 신뢰도 dict (없으면 기본값 0.5)

    Returns:
        otto_output dict (OttoOutput schema)
        emily_output 또는 portfolio가 비어있으면 {} graceful skip.
    """
    if not emily_output or not portfolio:
        return {}

    agent = OttoAgent(llm=llm_decision, config=_OTTO_CONFIG)

    # compute_adaptive_weights: 실제 reward_history 로드 후 호출
    reward_history = _load_reward_history(n=10)
    adaptive_weights = agent.compute_adaptive_weights(reward_history)

    input_packet = build_otto_input(
        emily_output=emily_output,
        sim_results=sim_results,
        dave_output=dave_output,
        portfolio=portfolio,
        date=date,
        adaptive_weights=adaptive_weights,
        agent_reliability=agent_reliability,
    )

    return agent.run(input_packet, state={"current_date": date})


def apply_otto_decision(otto_output: dict, portfolio: dict) -> dict:
    """
    Otto approval_status에 따라 portfolio dict 조정.

    - approved                 → 원본 반환
    - approved_with_modification → equity 비중 스케일 다운 (allocation 기반)
    - conditional_approval     → hedge_pct 상향, 고위험 포지션 HOLD 전환
    - rejected                 → 전체 HOLD + cash_pct=0.9

    portfolio 스키마(PortfolioManagerOutput) 구조 보존:
      allocations, total_equity_pct, cash_pct, hedge_pct 필드 유지.
    otto_output이 없으면 원본 portfolio 반환.
    """
    if not otto_output or not portfolio:
        return portfolio

    status = otto_output.get("approval_status", "approved")
    result = dict(portfolio)

    if status == "approved":
        return result

    allocations = list(result.get("allocations") or [])

    if status == "approved_with_modification":
        # Otto allocation의 equities 비율로 equity 비중 스케일 다운
        otto_alloc = otto_output.get("allocation") or {}
        otto_equity = float(otto_alloc.get("equities", 0.6))
        current_equity = float(result.get("total_equity_pct") or 0.6)

        if current_equity > 0:
            scale = otto_equity / current_equity
            scale = min(max(scale, 0.1), 1.0)  # 최소 10%, 최대 현재 비중 유지
            scaled_allocs = []
            for a in allocations:
                a = dict(a)
                w = float(a.get("weight") or 0.0)
                a["weight"] = round(w * scale, 4)
                scaled_allocs.append(a)
            result["allocations"] = scaled_allocs
            result["total_equity_pct"] = round(current_equity * scale, 4)
            result["cash_pct"] = round(1.0 - result["total_equity_pct"] - float(result.get("hedge_pct") or 0.0), 4)

    elif status == "conditional_approval":
        # hedge_pct 상향 (현재 + 10%, 최대 30%)
        current_hedge = float(result.get("hedge_pct") or 0.0)
        new_hedge = min(current_hedge + 0.10, 0.30)
        result["hedge_pct"] = round(new_hedge, 4)
        result["cash_pct"] = round(max(float(result.get("cash_pct") or 0.0) - 0.05, 0.0), 4)

        # 고위험 포지션(risk_level=high/critical) HOLD 전환
        updated_allocs = []
        for a in allocations:
            a = dict(a)
            if a.get("action") in ("BUY", "SELL"):
                # risk_manager risk_level 정보가 없으면 HOLD 유지하지 않음
                # allocation에 risk_level 필드가 있으면 참고
                if a.get("risk_level") in ("high", "critical"):
                    a["action"] = "HOLD"
            updated_allocs.append(a)
        result["allocations"] = updated_allocs

    elif status == "rejected":
        # 전체 HOLD + 현금 최대화
        hold_allocs = []
        for a in allocations:
            a = dict(a)
            a["action"] = "HOLD"
            a["weight"] = 0.0
            hold_allocs.append(a)
        result["allocations"] = hold_allocs
        result["total_equity_pct"] = 0.05
        result["cash_pct"] = 0.90
        result["hedge_pct"] = 0.05

    return result
