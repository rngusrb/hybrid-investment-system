"""DAILY_POST_EXECUTION_LOGGING node — execution 결과를 Decision Journal에 기록.

spec 4.2 step 9: 거래 종료 후 DAILY_POST_EXECUTION_LOGGING과 memory/ledger 기록
- execution_plan, risk_score, approval_status, signal 상태를 Ledger에 기록
- propagation_audit_log가 아닌 Ledger의 final_policy_decision / execution_plan 타입으로 저장
"""
from graph.state import SystemState
from ledger.shared_ledger import SharedLedger
from memory.registry import strategy_memory
from utils.forward_return import fetch_forward_return


def daily_post_execution_logging(state: SystemState) -> SystemState:
    """
    실행 결과를 Ledger에 공식 기록.
    propagation_audit_log가 아닌 Ledger 전용 entry로 저장.
    """
    updated = dict(state)
    current_date = state.get("current_date", "")

    otto_output = state.get("otto_output") or {}
    execution_plan = state.get("execution_plan") or {}
    dave_output = state.get("dave_output") or {}

    # ── Ledger 기록 ────────────────────────────────────────────────────────
    ledger: SharedLedger = state.get("_ledger")
    if ledger is None:
        ledger = SharedLedger()

    # final_policy_decision
    policy_entry = {
        "date": current_date,
        "approval_status": otto_output.get("approval_status", "unknown"),
        "selected_policy": otto_output.get("selected_policy", ""),
        "risk_score": state.get("risk_score", 0.0),
        "risk_alert_triggered": state.get("risk_alert_triggered", False),
        "technical_confidence": state.get("technical_confidence", 0.5),
        "uncertainty_level": state.get("uncertainty_level", 0.5),
        "agent_reliability": state.get("agent_reliability", {}),
    }
    try:
        ledger.record("final_policy_decision", policy_entry, current_date, "Orchestrator")
    except ValueError:
        pass  # 이미 기록된 경우 skip

    # execution_plan
    if execution_plan:
        exec_entry = {
            "date": current_date,
            "plan": execution_plan,
            "feasibility_score": state.get("execution_feasibility_score", 0.0),
            "risk_constraints": (dave_output.get("risk_constraints") or {}),
        }
        try:
            ledger.record("execution_plan", exec_entry, current_date, "Orchestrator")
        except ValueError:
            pass

    # ── 실행 후 상태 로그 (propagation_audit_log와 분리된 별도 항목) ────────
    exec_log_entry = {
        "type": "execution_log",
        "date": current_date,
        "node": "DAILY_POST_EXECUTION_LOGGING",
        "execution_plan_present": execution_plan is not None and bool(execution_plan),
        "risk_score": state.get("risk_score", 0.0),
        "approval_status": otto_output.get("approval_status", "unknown"),
        "risk_alert_triggered": state.get("risk_alert_triggered", False),
        "skip_count": len(state.get("skip_log", [])),
        "retry_count": len(state.get("retry_log", [])),
    }
    updated["calibration_log"] = list(state.get("calibration_log", [])) + [exec_log_entry]

    # ── strategy_memory에 실행 outcome 저장 ────────────────────────────────
    if current_date:
        # r_sim: Bob 선택 전략의 sim_metrics.return (LLM → 실제 백테스트 교체된 값)
        bob_output = state.get("bob_output") or {}
        selected_names = bob_output.get("selected_for_review", [])
        candidates = {c["name"]: c for c in bob_output.get("candidate_strategies", [])}
        _sel = (
            candidates.get(selected_names[0])
            if selected_names and selected_names[0] in candidates
            else (list(candidates.values())[0] if candidates else None)
        )
        r_sim = float(_sel.get("sim_metrics", {}).get("return", 0.0)) if _sel else 0.0

        # r_real: Polygon에서 T+1 실제 수익률 취득 시도.
        # state에 _polygon_fetcher와 _execution_ticker가 있으면 실제 forward return 계산.
        # API 실패 또는 T+1이 아직 미래(실시간 모드)이면 r_sim으로 fallback.
        polygon_fetcher = state.get("_polygon_fetcher")
        execution_ticker = state.get("_execution_ticker", "SPY")
        r_real_fetched = fetch_forward_return(
            fetcher=polygon_fetcher,
            ticker=execution_ticker,
            execution_date=current_date,
        ) if polygon_fetcher and current_date else None
        r_real = r_real_fetched if r_real_fetched is not None else r_sim
        r_real_source = "polygon_t1" if r_real_fetched is not None else "r_sim_proxy"

        outcome_entry = {
            "approval_status": otto_output.get("approval_status", "unknown"),
            "selected_policy": otto_output.get("selected_policy", ""),
            "risk_score": state.get("risk_score", 0.0),
            "execution_feasibility_score": state.get("execution_feasibility_score", 0.0),
            "technical_confidence": state.get("technical_confidence", 0.5),
            "uncertainty_level": state.get("uncertainty_level", 0.5),
            "risk_alert_triggered": state.get("risk_alert_triggered", False),
            "outcome_horizon": "daily",
            "horizon_closed": True,
            "r_sim": r_sim,           # adaptive weights 계산용
            "r_real": r_real,         # adaptive weights 계산용 (polygon T+1 or r_sim proxy)
            "r_real_source": r_real_source,  # "polygon_t1" | "r_sim_proxy"
            "rationale": f"Policy {otto_output.get('selected_policy', '')} executed with risk_score={state.get('risk_score', 0.0):.2f}",
        }
        approval = otto_output.get("approval_status", "unknown")
        tags = ["outcome", "horizon_closed", approval]
        strategy_memory.store(
            key=f"outcome_{current_date}",
            value=outcome_entry,
            date=current_date,
            tags=tags,
        )

    updated["next_node"] = None  # route_daily_end가 담당
    return updated
