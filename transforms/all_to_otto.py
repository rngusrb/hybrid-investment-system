"""
3개 agent packet + execution feasibility → Otto policy packet.
Otto는 이 packet만 봄. raw data 절대 포함 금지.
"""
from typing import Optional
from schemas.otto_schema import OttoPolicyPacket
from schemas.emily_schema import EmilyToBobPacket
from schemas.bob_schema import BobToDavePacket, BobToExecutionPacket
from schemas.dave_schema import DaveOutput
from memory.registry import strategy_memory


def transform_all_to_otto(
    emily_packet: dict,
    bob_dave_packet: dict,
    dave_output: dict,
    execution_packet: dict,
    date: str,
    agent_reliability_summary: Optional[dict] = None,
    recent_reward_summary: Optional[dict] = None,
) -> dict:
    """
    3 agent packets → Otto policy packet.
    raw data 유입 차단: 각 packet은 schema로 검증 후 요약 필드만 추출.
    """
    emily = EmilyToBobPacket(**emily_packet)
    bob_dave = BobToDavePacket(**bob_dave_packet)
    dave = DaveOutput(**dave_output)
    execution = BobToExecutionPacket(**execution_packet)

    reliability = agent_reliability_summary or {"emily": 0.5, "bob": 0.5, "dave": 0.5}

    # reward_history: strategy_memory에서 r_sim/r_real 저장된 최근 10개 outcome 조회
    if recent_reward_summary is None:
        reward_history = []
        for record in strategy_memory._store.values():
            if isinstance(record, dict):
                val = record.get("value", {})
                if isinstance(val, dict) and "r_sim" in val and "r_real" in val:
                    reward_history.append({"r_sim": val["r_sim"], "r_real": val["r_real"]})
        recent_reward_summary = {
            "reward_history": reward_history[-10:],
            "count": len(reward_history),
        }

    packet = OttoPolicyPacket(
        source_agent="Aggregator",
        target_agent="Otto",
        date=date,
        # Emily 요약
        market_regime=emily.regime,
        regime_confidence=emily.regime_confidence,
        market_bias=emily.market_bias,
        technical_confidence=emily.technical_confidence,
        reversal_risk=emily.reversal_risk,
        market_uncertainty=emily.market_uncertainty,
        # Bob 요약
        selected_strategy_name=bob_dave.strategy_name,
        strategy_confidence=bob_dave.strategy_confidence,
        technical_alignment=bob_dave.technical_alignment,
        failure_conditions=bob_dave.failure_conditions,
        # Dave 요약
        risk_score=dave.risk_score,
        risk_level=dave.risk_level,
        risk_constraints=dave.risk_constraints.model_dump(),
        trigger_risk_alert=dave.trigger_risk_alert_meeting,
        # Execution
        rebalance_urgency=execution.rebalance_urgency,
        execution_constraints_hint=execution.execution_constraints_hint,
        # Reliability
        agent_reliability_summary=reliability,
        recent_reward_summary=recent_reward_summary,
    )
    return packet.model_dump()
