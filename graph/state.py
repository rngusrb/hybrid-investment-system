"""SystemState — LangGraph 전체 상태 정의."""
from typing import TypedDict, Optional, Literal, List


class SystemState(TypedDict, total=False):
    # 시간 컨텍스트
    current_date: str
    cycle_type: Literal["daily", "weekly", "event"]
    is_week_end: bool

    # Raw data (ingest 노드만 채움, Otto는 접근 안 함)
    raw_market_data: Optional[dict]
    raw_news: Optional[list]

    # Agent 공식 outputs
    emily_output: Optional[dict]
    bob_output: Optional[dict]
    dave_output: Optional[dict]
    otto_output: Optional[dict]

    # Transformation packets
    emily_to_bob_packet: Optional[dict]
    bob_to_dave_packet: Optional[dict]
    bob_to_execution_packet: Optional[dict]
    otto_policy_packet: Optional[dict]

    # 제어 신호
    risk_alert_triggered: bool
    risk_score: float
    uncertainty_level: float
    technical_confidence: float

    # Agent reliability
    agent_reliability: dict

    # 감사 / 캘리브레이션
    propagation_audit_log: list
    calibration_log: list
    skip_log: list
    retry_log: list

    # Memory retrieval 결과
    retrieved_market_cases: Optional[list]
    retrieved_strategy_cases: Optional[list]

    # 실행
    execution_plan: Optional[dict]
    execution_feasibility_score: float

    # 주간 meeting 출력
    weekly_market_report: Optional[dict]
    debate_resolution: Optional[dict]
    signal_conflict_resolution: Optional[dict]
    weekly_strategy_set: Optional[dict]

    # 다음 노드 제어
    next_node: Optional[str]
    flow_decision_reason: Optional[str]

    # 실행 컨텍스트 (position sizing용)
    _portfolio_value: Optional[float]   # 계좌 잔고 (USD)
    _current_prices: Optional[dict]     # {"SPY": 500.0, "SH": 41.0, ...}
    _equity_ticker: Optional[str]       # 주식 종목 (default "SPY")
    _hedge_ticker: Optional[str]        # 헤지 종목 (default "SH")

    # 런타임 주입 (orchestrator → 노드, LangGraph state로 전달)
    _llm_analyst: Optional[object]      # analyst 역할 LLM provider
    _llm_decision: Optional[object]     # decision 역할 LLM provider
    _polygon_fetcher: Optional[object]  # Polygon REST fetcher
    _trading_engine: Optional[object]   # SimulatedTradingEngine
    _agent_config: Optional[dict]       # 에이전트 공통 config


def make_initial_state(current_date: str, cycle_type: str = "daily", is_week_end: bool = False) -> SystemState:
    """초기 state 생성."""
    return {
        "current_date": current_date,
        "cycle_type": cycle_type,
        "is_week_end": is_week_end,
        "raw_market_data": None,
        "raw_news": None,
        "emily_output": None,
        "bob_output": None,
        "dave_output": None,
        "otto_output": None,
        "emily_to_bob_packet": None,
        "bob_to_dave_packet": None,
        "bob_to_execution_packet": None,
        "otto_policy_packet": None,
        "risk_alert_triggered": False,
        "risk_score": 0.0,
        "uncertainty_level": 0.5,
        "technical_confidence": 0.5,
        "agent_reliability": {"emily": 0.5, "bob": 0.5, "dave": 0.5, "otto": 0.5},
        "propagation_audit_log": [],
        "calibration_log": [],
        "skip_log": [],
        "retry_log": [],
        "retrieved_market_cases": None,
        "retrieved_strategy_cases": None,
        "execution_plan": None,
        "execution_feasibility_score": 0.5,
        "weekly_market_report": None,
        "debate_resolution": None,
        "signal_conflict_resolution": None,
        "weekly_strategy_set": None,
        "next_node": None,
        "flow_decision_reason": None,
    }


# 사이클 간 유지해야 하는 필드 (리셋하면 안 됨)
_CROSS_CYCLE_KEYS = frozenset([
    "agent_reliability",     # 매 사이클 calibration으로 업데이트
    "calibration_log",       # 누적 기록
    "_ledger",               # SharedLedger 인스턴스
    "_polygon_fetcher",      # API 클라이언트 재사용
    "_trading_engine",       # 백테스트 엔진 재사용
    "_execution_ticker",     # 종목 설정
])


def reset_for_next_cycle(
    prev_state: SystemState,
    next_date: str,
    cycle_type: str = "daily",
    is_week_end: bool = False,
) -> SystemState:
    """
    이전 사이클 state에서 사이클별 데이터를 초기화하고 새 날짜로 재설정.

    cross-cycle 필드(agent_reliability, calibration_log, ledger 등)는 유지.
    사이클별 필드(agent outputs, raw data, packets, logs 등)는 초기화.

    멀티사이클 실행 시 state 오염 방지용.
    """
    fresh = make_initial_state(next_date, cycle_type, is_week_end)
    # 유지해야 하는 필드를 이전 state에서 복사
    for key in _CROSS_CYCLE_KEYS:
        if key in prev_state:
            fresh[key] = prev_state[key]
    return fresh
