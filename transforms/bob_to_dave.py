"""Bob strategy output → Dave risk assessment packet."""
from schemas.bob_schema import BobOutput, BobToDavePacket


def transform_bob_to_dave(bob_output: dict, date: str) -> dict:
    """
    BobOutput → BobToDavePacket
    selected_for_review 중 첫 번째 strategy를 기준으로 패킷 생성.
    없으면 confidence 가장 높은 전략 선택.
    """
    bob = BobOutput(**bob_output)

    # selected_for_review 중 첫 번째, 없으면 confidence 가장 높은 것
    candidates = {c.name: c for c in bob.candidate_strategies}

    if bob.selected_for_review and bob.selected_for_review[0] in candidates:
        strategy = candidates[bob.selected_for_review[0]]
    elif candidates:
        strategy = max(candidates.values(), key=lambda c: c.confidence)
    else:
        raise ValueError("BobOutput has no candidate strategies")

    packet = BobToDavePacket(
        source_agent="Bob",
        target_agent="Dave",
        date=date,
        strategy_name=strategy.name,
        expected_turnover=strategy.sim_metrics.turnover,
        sector_bias=[],  # sector_bias는 strategy logic에서 파생 — 현재는 빈 리스트
        expected_vol_profile=strategy.sim_metrics.mdd,
        failure_conditions=strategy.failure_conditions,
        strategy_confidence=strategy.confidence,
        technical_alignment=strategy.technical_alignment,
    )
    return packet.model_dump()
