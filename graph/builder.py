"""
LangGraph graph 조립.

핵심: 단순 순차 파이프라인이 아니라
conditional edge로 흐름을 제어하는 유연한 state machine.
"""
from langgraph.graph import StateGraph, END

from graph.state import SystemState
from graph.nodes import (
    ingest,
    memory_update,
    calibration,
    agent_reliability,
    risk_check,
    policy,
    execution,
    order,
    logging_node,
    weekly_market,
    weekly_strategy,
    propagation_audit,
    risk_alert,
    consolidation,
)
from graph.edges.daily_edges import (
    route_after_risk_check,
    route_after_policy,
    route_after_ingest,
    route_daily_end,
)
from graph.edges.weekly_edges import (
    route_after_weekly_market,
    route_after_weekly_strategy,
    route_after_propagation_audit,
)
from graph.edges.event_edges import route_after_risk_alert


def build_graph() -> StateGraph:
    """
    전체 투자 의사결정 state machine 조립.
    conditional edge로 LLM 판단 기반 흐름 제어.
    """
    graph = StateGraph(SystemState)

    # 노드 등록
    graph.add_node("INGEST_DAILY_DATA", ingest.ingest_daily_data)
    graph.add_node("UPDATE_MARKET_MEMORY", memory_update.update_market_memory)
    graph.add_node("DAILY_SIGNAL_CALIBRATION", calibration.daily_signal_calibration)
    graph.add_node("DAILY_AGENT_RELIABILITY_UPDATE", agent_reliability.daily_agent_reliability_update)
    graph.add_node("DAILY_RISK_CHECK", risk_check.daily_risk_check)
    graph.add_node("DAILY_POLICY_SELECTION", policy.daily_policy_selection)
    graph.add_node("DAILY_EXECUTION_FEASIBILITY_CHECK", execution.daily_execution_feasibility_check)
    graph.add_node("DAILY_ORDER_PLAN_GENERATION", order.daily_order_plan_generation)
    graph.add_node("DAILY_POST_EXECUTION_LOGGING", logging_node.daily_post_execution_logging)
    graph.add_node("WEEKLY_MARKET_ANALYSIS_MEETING", weekly_market.weekly_market_analysis_meeting)
    graph.add_node("WEEKLY_STRATEGY_DEVELOPMENT_MEETING", weekly_strategy.weekly_strategy_development_meeting)
    graph.add_node("WEEKLY_PROPAGATION_AUDIT", propagation_audit.weekly_propagation_audit)
    graph.add_node("RISK_ALERT_MEETING", risk_alert.risk_alert_meeting)
    graph.add_node("MEMORY_CONSOLIDATION", consolidation.memory_consolidation)

    # 시작 노드
    graph.set_entry_point("INGEST_DAILY_DATA")

    # Conditional edges (핵심 — state 기반 분기)
    graph.add_conditional_edges(
        "INGEST_DAILY_DATA",
        route_after_ingest,
        {
            "UPDATE_MARKET_MEMORY": "UPDATE_MARKET_MEMORY",
            "DAILY_RISK_CHECK": "DAILY_RISK_CHECK",   # next_node 오버라이드 허용
            "WAIT_NEXT_BAR": END,
        },
    )
    graph.add_edge("UPDATE_MARKET_MEMORY", "DAILY_SIGNAL_CALIBRATION")
    graph.add_edge("DAILY_SIGNAL_CALIBRATION", "DAILY_AGENT_RELIABILITY_UPDATE")
    graph.add_edge("DAILY_AGENT_RELIABILITY_UPDATE", "DAILY_RISK_CHECK")

    graph.add_conditional_edges(
        "DAILY_RISK_CHECK",
        route_after_risk_check,
        {
            "DAILY_POLICY_SELECTION": "DAILY_POLICY_SELECTION",
            "RISK_ALERT_MEETING": "RISK_ALERT_MEETING",
            "WAIT_NEXT_BAR": END,
        },
    )

    graph.add_conditional_edges(
        "DAILY_POLICY_SELECTION",
        route_after_policy,
        {
            "DAILY_EXECUTION_FEASIBILITY_CHECK": "DAILY_EXECUTION_FEASIBILITY_CHECK",
            "WAIT_NEXT_BAR": END,
        },
    )

    graph.add_edge("DAILY_EXECUTION_FEASIBILITY_CHECK", "DAILY_ORDER_PLAN_GENERATION")
    graph.add_edge("DAILY_ORDER_PLAN_GENERATION", "DAILY_POST_EXECUTION_LOGGING")

    graph.add_conditional_edges(
        "DAILY_POST_EXECUTION_LOGGING",
        route_daily_end,
        {
            "WEEKLY_MARKET_ANALYSIS_MEETING": "WEEKLY_MARKET_ANALYSIS_MEETING",
            "WAIT_NEXT_BAR": END,
        },
    )

    # 주간 cycle
    graph.add_conditional_edges(
        "WEEKLY_MARKET_ANALYSIS_MEETING",
        route_after_weekly_market,
        {"WEEKLY_STRATEGY_DEVELOPMENT_MEETING": "WEEKLY_STRATEGY_DEVELOPMENT_MEETING"},
    )
    graph.add_conditional_edges(
        "WEEKLY_STRATEGY_DEVELOPMENT_MEETING",
        route_after_weekly_strategy,
        {"WEEKLY_PROPAGATION_AUDIT": "WEEKLY_PROPAGATION_AUDIT"},
    )
    graph.add_conditional_edges(
        "WEEKLY_PROPAGATION_AUDIT",
        route_after_propagation_audit,
        {"MEMORY_CONSOLIDATION": "MEMORY_CONSOLIDATION"},
    )
    graph.add_edge("MEMORY_CONSOLIDATION", END)

    # event-driven
    graph.add_conditional_edges(
        "RISK_ALERT_MEETING",
        route_after_risk_alert,
        {
            "DAILY_EXECUTION_FEASIBILITY_CHECK": "DAILY_EXECUTION_FEASIBILITY_CHECK",
            "WAIT_NEXT_BAR": END,
        },
    )

    return graph


def compile_graph():
    """graph 컴파일 및 반환."""
    graph = build_graph()
    return graph.compile()
