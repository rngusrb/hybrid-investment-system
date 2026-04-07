"""DAILY_POLICY_SELECTION node — Emily→Bob→Dave→Otto 실제 에이전트 호출."""
from graph.state import SystemState
from utils.utility import compute_utility_from_state

_UTILITY_DOWNGRADE_THRESHOLD = -0.1


def daily_policy_selection(state: SystemState) -> SystemState:
    """
    Emily→Bob→Dave→Otto 순서로 에이전트 실제 호출.
    _llm_analyst / _llm_decision / _trading_engine 이 state에 있으면 실제 LLM 호출.
    없으면 placeholder 로직으로 fallback.
    """
    updated = dict(state)

    llm_analyst = state.get("_llm_analyst")
    llm_decision = state.get("_llm_decision")
    trading_engine = state.get("_trading_engine")
    date = state.get("current_date", "")

    if llm_analyst is not None and llm_decision is not None:
        _run_real_agents(updated, state, llm_analyst, llm_decision, trading_engine, date)
    else:
        _run_placeholder(updated, state)

    # utility 계산 (항상 utils/utility.py 단일 소스)
    approval_status = (updated.get("otto_output") or {}).get("approval_status", "rejected")
    utility_score = compute_utility_from_state(updated, approval_status)

    if utility_score < _UTILITY_DOWNGRADE_THRESHOLD and approval_status == "approved":
        approval_status = "conditional_approval"
        updated["otto_output"] = dict(updated.get("otto_output") or {})
        updated["otto_output"]["approval_status"] = "conditional_approval"
        updated["flow_decision_reason"] = (
            f"utility={utility_score:.3f} below threshold={_UTILITY_DOWNGRADE_THRESHOLD} — downgraded"
        )

    # utility_score를 otto_output에도 기록 (테스트 및 하류 노드 참조용)
    updated["otto_output"] = dict(updated.get("otto_output") or {})
    updated["otto_output"]["utility_score"] = round(utility_score, 4)

    updated["otto_policy_packet"] = {
        "action": (updated.get("otto_output") or {}).get("selected_policy", "hold"),
        "approval_status": approval_status,
        "utility_score": round(utility_score, 4),
    }
    updated["utility_score"] = round(utility_score, 4)
    updated["approval_status"] = approval_status
    updated["next_node"] = "DAILY_EXECUTION_FEASIBILITY_CHECK"
    return updated


def _run_real_agents(updated, state, llm_analyst, llm_decision, trading_engine, date):
    """Emily→Bob→Dave→Otto 실제 호출."""
    from agents.emily import EmilyAgent
    from agents.bob import BobAgent
    from agents.dave import DaveAgent
    from agents.otto import OttoAgent
    from transforms.emily_to_bob import transform_emily_to_bob
    from transforms.bob_to_dave import transform_bob_to_dave
    from transforms.all_to_otto import transform_all_to_otto

    config_base = state.get("_agent_config", {})

    # Emily
    emily = EmilyAgent(
        llm=llm_analyst,
        config={**config_base, "name": "Emily", "system_prompt_path": "prompts/emily_system.md"},
    )
    emily_input = {
        "current_date": date,
        "raw_market_data": state.get("raw_market_data", {}),
        "raw_news": state.get("raw_news", []),
    }
    eo = emily.run(emily_input, state=dict(state))
    updated["emily_output"] = eo

    # Bob
    from simulation.trading_engine import SimulatedTradingEngine
    engine = trading_engine or SimulatedTradingEngine()
    bob = BobAgent(
        llm=llm_analyst,
        config={**config_base, "name": "Bob", "system_prompt_path": "prompts/bob_system.md"},
        trading_engine=engine,
    )
    emily_to_bob = emily.to_bob_packet(eo, date)
    bo = bob.run(emily_to_bob, state=dict(state))
    updated["bob_output"] = bo
    updated["emily_to_bob_packet"] = emily_to_bob
    updated["bob_to_execution_packet"] = bob.to_execution_packet(bo, date)

    # Dave
    dave = DaveAgent(
        llm=llm_analyst,
        config={**config_base, "name": "Dave", "system_prompt_path": "prompts/dave_system.md"},
    )
    bob_to_dave = transform_bob_to_dave(bo, date)
    do = dave.run(bob_to_dave, state=dict(state))
    updated["dave_output"] = do
    updated["bob_to_dave_packet"] = bob_to_dave
    updated["risk_score"] = do.get("risk_score", 0.5)

    # Otto
    otto = OttoAgent(
        llm=llm_decision,
        config={**config_base, "name": "Otto", "system_prompt_path": "prompts/otto_system.md"},
    )
    exec_packet = updated["bob_to_execution_packet"]
    otto_packet = transform_all_to_otto(emily_to_bob, bob_to_dave, do, exec_packet, date)
    oo = otto.run(otto_packet, state=dict(state))
    updated["otto_output"] = oo


def _run_placeholder(updated, state):
    """LLM 없을 때 fallback — 기존 dave_output 기반 단순 판단."""
    risk_score = state.get("risk_score", 0.5)
    uncertainty = state.get("uncertainty_level", 0.5)
    risk_alert = state.get("risk_alert_triggered", False)

    if risk_alert:
        approval_status = "rejected"
        policy_action = "hold"
    elif risk_score > 0.6 or uncertainty > 0.7:
        approval_status = "conditional_approval"
        policy_action = "reduce_exposure"
    else:
        approval_status = "approved"
        policy_action = "execute"

    updated["otto_output"] = {
        "approval_status": approval_status,
        "selected_policy": policy_action,
        "risk_score_at_decision": risk_score,
    }
    updated["flow_decision_reason"] = "placeholder — no LLM connected"
