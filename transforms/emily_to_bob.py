"""
Emily full report → Bob feature packet transformation.
technical signal 필드가 손실 없이 전달되는지 이 모듈이 보장.
"""
from typing import Optional
from schemas.emily_schema import EmilyOutput, EmilyToBobPacket


def transform_emily_to_bob(emily_output: dict, date: str) -> dict:
    """
    EmilyOutput → EmilyToBobPacket
    technical_direction, technical_confidence, reversal_risk 보존 필수.
    """
    # schema validation
    emily = EmilyOutput(**emily_output)
    ts = emily.technical_signal_state

    preferred = [s.sector for s in emily.sector_preference if s.score >= 0.6]
    avoid = [s.sector for s in emily.sector_preference if s.score < 0.4]

    # event_risk_level: event_sensitivity_map이 있으면 평균, 없으면 0.3
    event_risk = 0.3
    if emily.event_sensitivity_map:
        risk_vals = [e.get("risk_level", 0.3) for e in emily.event_sensitivity_map if isinstance(e, dict)]
        if risk_vals:
            event_risk = sum(risk_vals) / len(risk_vals)

    # market_uncertainty: uncertainty_reasons 수에 비례
    market_uncertainty = min(len(emily.uncertainty_reasons) * 0.12, 0.9)

    packet = EmilyToBobPacket(
        source_agent="Emily",
        target_agent="Bob",
        date=date,
        regime=emily.market_regime,
        regime_confidence=emily.regime_confidence,
        preferred_sectors=preferred,
        avoid_sectors=avoid,
        market_bias=emily.recommended_market_bias,
        event_risk_level=event_risk,
        market_uncertainty=market_uncertainty,
        technical_direction=ts.trend_direction,
        technical_confidence=ts.technical_confidence,
        reversal_risk=ts.reversal_risk,
    )
    return packet.model_dump()
