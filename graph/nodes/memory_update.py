"""UPDATE_MARKET_MEMORY node — 시장 데이터 및 agent 출력을 memory에 반영."""
from graph.state import SystemState
from memory.registry import (
    market_memory,
    strategy_memory,
    market_retriever,
    strategy_retriever,
)


def update_market_memory(state: SystemState) -> SystemState:
    """
    emily_output / bob_output을 memory store에 기록하고,
    현재 regime으로 유사 케이스를 검색하여 state에 저장.
    point-in-time 준수: 저장 및 검색 모두 current_date 기준.
    """
    updated = dict(state)

    # memory가 이미 업데이트된 경우 스킵
    if state.get("retrieved_market_cases") is not None:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "UPDATE_MARKET_MEMORY",
            "reason": "retrieved_market_cases already present",
            "date": state.get("current_date"),
        }]
        updated["next_node"] = "DAILY_SIGNAL_CALIBRATION"
        return updated

    current_date = state.get("current_date", "")
    emily_output = state.get("emily_output")
    bob_output = state.get("bob_output")

    # emily_output이 없으면 저장/검색 skip하고 빈 리스트 반환
    if emily_output is None:
        updated["retrieved_market_cases"] = []
        updated["retrieved_strategy_cases"] = []
        updated["next_node"] = "DAILY_SIGNAL_CALIBRATION"
        return updated

    # emily_output을 market_memory에 저장
    market_memory.store(
        key=f"market_{current_date}",
        value=emily_output,
        date=current_date,
        tags=["emily_output", emily_output.get("market_regime", "unknown")],
    )

    # bob_output이 있으면 strategy_memory에 저장
    if bob_output is not None:
        strategy_memory.store(
            key=f"strategy_{current_date}",
            value=bob_output,
            date=current_date,
            tags=["bob_output", bob_output.get("strategy_bias", "unknown")],
        )

    # 현재 regime으로 query 빌드
    current_regime = emily_output.get("market_regime", "mixed")
    query = {
        "market_regime": emily_output.get("market_regime", "mixed"),
        "regime_confidence": emily_output.get("regime_confidence", 0.5),
        "recommended_market_bias": emily_output.get("recommended_market_bias", "neutral"),
    }

    # Retriever 호출 (point-in-time: as_of=current_date)
    retrieved_market = market_retriever.retrieve(
        query=query,
        as_of=current_date,
        current_regime=current_regime,
    )
    retrieved_strategy = strategy_retriever.retrieve(
        query=query,
        as_of=current_date,
        current_regime=current_regime,
    )

    updated["retrieved_market_cases"] = retrieved_market
    updated["retrieved_strategy_cases"] = retrieved_strategy
    updated["next_node"] = "DAILY_SIGNAL_CALIBRATION"
    return updated
