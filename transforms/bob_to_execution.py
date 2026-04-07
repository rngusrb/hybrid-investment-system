"""
Bob selected strategy → Execution feasibility packet.
주의: 이 packet은 실행 명령이 아니라 feasibility 힌트임.
"""
from schemas.bob_schema import BobOutput, BobToExecutionPacket


def transform_bob_to_execution(bob_output: dict, date: str) -> dict:
    """
    BobOutput → BobToExecutionPacket
    실행 가능성 힌트만 추출. 실행 명령이 아님.
    """
    bob = BobOutput(**bob_output)

    candidates = {c.name: c for c in bob.candidate_strategies}
    strategy_name = (
        bob.selected_for_review[0]
        if bob.selected_for_review and bob.selected_for_review[0] in candidates
        else (list(candidates.keys())[0] if candidates else "unknown")
    )

    strategy = candidates.get(strategy_name)

    # rebalance_urgency: sim sharpe가 높고 regime_fit도 높으면 urgency 낮음 (서두를 필요 없음)
    if strategy:
        sharpe = strategy.sim_metrics.sharpe
        regime_fit = strategy.regime_fit
        urgency = max(0.1, 1.0 - (sharpe * 0.1 + regime_fit * 0.3))
        urgency = min(urgency, 0.9)

        # hedge_preference: technical_alignment 낮으면 moderate hedge
        if strategy.technical_alignment < 0.4:
            hedge_pref = "moderate"
        elif strategy.technical_alignment < 0.6:
            hedge_pref = "light"
        else:
            hedge_pref = "none"

        turnover = strategy.sim_metrics.turnover
        constraints = strategy.failure_conditions[:2]  # 상위 2개 failure condition을 hint로 전달
    else:
        urgency = 0.5
        hedge_pref = "light"
        turnover = 0.3
        constraints = []

    packet = BobToExecutionPacket(
        source_agent="Bob",
        target_agent="Execution",
        date=date,
        selected_strategy_name=strategy_name,
        target_posture="neutral",
        rebalance_urgency=urgency,
        expected_turnover=turnover,
        hedge_preference=hedge_pref,
        execution_constraints_hint=constraints,
    )
    return packet.model_dump()
