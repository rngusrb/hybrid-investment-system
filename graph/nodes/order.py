"""DAILY_ORDER_PLAN_GENERATION node — 주문 계획 생성."""
from graph.state import SystemState
from schemas.audit_schema import NodeResult
from execution.position_sizer import PositionSizer


def daily_order_plan_generation(state: SystemState) -> SystemState:
    """
    Otto allocation → 실제 주문 계획 (종목, 수량, 손절가) 생성.

    state에서 읽는 값:
        _portfolio_value   : float (계좌 잔고, 기본 1,000,000)
        _current_prices    : dict  ({"SPY": 500.0, ...})
        _equity_ticker     : str   (기본 "SPY")
        _hedge_ticker      : str   (기본 "SH")
        otto_output        : dict  (allocation, execution_plan, selected_policy)
        execution_feasibility_score : float
    """
    updated = dict(state)

    otto_output = state.get("otto_output") or {}
    otto_policy = state.get("otto_policy_packet") or {}
    feasibility_score = state.get("execution_feasibility_score", 0.5)
    current_date = state.get("current_date", "")
    approval_status = otto_output.get("approval_status", otto_policy.get("approval_status", "rejected"))
    action = otto_policy.get("action", "hold")

    # hold / rejected이면 빈 주문 계획
    if action in ("hold",) or approval_status == "rejected":
        updated["execution_plan"] = {
            "date": current_date,
            "action": action,
            "feasibility_score": feasibility_score,
            "status": "no_order",
            "orders": [],
            "reason": f"approval_status={approval_status}, action={action}",
        }
    else:
        portfolio_value = float(state.get("_portfolio_value", 1_000_000))
        current_prices = state.get("_current_prices") or {}
        equity_ticker = state.get("_equity_ticker", "SPY")
        hedge_ticker = state.get("_hedge_ticker", "SH")

        allocation = otto_output.get("allocation") or {"equities": 0.6, "hedge": 0.1, "cash": 0.3}
        exec_plan_meta = otto_output.get("execution_plan") or {}
        strategy_name = otto_output.get("selected_policy", "unknown")

        if current_prices:
            sizer = PositionSizer(
                portfolio_value=portfolio_value,
                current_prices=current_prices,
            )
            order_plan = sizer.compute(
                allocation=allocation,
                execution_plan=exec_plan_meta,
                strategy_name=strategy_name,
                approval_status=approval_status,
                date=current_date,
                equity_ticker=equity_ticker,
                hedge_ticker=hedge_ticker,
                feasibility_score=feasibility_score,
            )
            plan_dict = order_plan.to_dict()
        else:
            # 가격 정보 없음 — notional만 계산
            plan_dict = {
                "date": current_date,
                "action": action,
                "feasibility_score": feasibility_score,
                "status": "no_price_data",
                "orders": [],
                "allocation": allocation,
                "note": "Set _current_prices in state to enable position sizing",
            }

        plan_dict["status"] = "planned"
        updated["execution_plan"] = plan_dict

    # propagation_audit_log 갱신
    updated["propagation_audit_log"] = list(state.get("propagation_audit_log", [])) + [{
        "date": current_date,
        "node": "DAILY_ORDER_PLAN_GENERATION",
        "execution_plan_created": True,
        "feasibility_score": feasibility_score,
        "order_count": len(updated["execution_plan"].get("orders", [])),
    }]

    updated["next_node"] = "DAILY_POST_EXECUTION_LOGGING"
    return updated
