"""주간 전이 규칙."""
from graph.state import SystemState


def route_after_weekly_market(state: SystemState) -> str:
    """주간 시장 분석 후 전략 개발로."""
    return "WEEKLY_STRATEGY_DEVELOPMENT_MEETING"


def route_after_weekly_strategy(state: SystemState) -> str:
    """주간 전략 개발 후 propagation audit."""
    return "WEEKLY_PROPAGATION_AUDIT"


def route_after_propagation_audit(state: SystemState) -> str:
    """propagation audit 후 memory consolidation."""
    return "MEMORY_CONSOLIDATION"
