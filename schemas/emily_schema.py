"""schemas.emily_schema - Pydantic schemas for Emily (Market Analyst) v3.6."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from schemas.base_schema import AgentBaseOutput, PacketBase


class MacroState(BaseModel):
    rates: float = Field(ge=-1.0, le=1.0)
    inflation: float = Field(ge=-1.0, le=1.0)
    growth: float = Field(ge=-1.0, le=1.0)
    liquidity: float = Field(ge=-1.0, le=1.0)
    risk_sentiment: float = Field(ge=-1.0, le=1.0)


class TechnicalSignalState(BaseModel):
    """technical signal은 macro/news에 묻히지 않는 독립 필드."""
    trend_direction: Literal["up", "down", "mixed"]
    continuation_strength: float = Field(ge=0.0, le=1.0)
    reversal_risk: float = Field(ge=0.0, le=1.0)
    technical_confidence: float = Field(ge=0.0, le=1.0)


class SectorScore(BaseModel):
    sector: str
    score: float = Field(ge=0.0, le=1.0)


class EmilyOutput(AgentBaseOutput):
    agent: str = "Emily"
    market_regime: Literal["risk_on", "risk_off", "mixed", "fragile_rebound", "transition"]
    regime_confidence: float = Field(ge=0.0, le=1.0)
    macro_state: MacroState
    technical_signal_state: TechnicalSignalState  # 독립 필드 — macro에 묻히면 안 됨
    sector_preference: List[SectorScore]
    bull_catalysts: List[str]
    bear_catalysts: List[str]
    event_sensitivity_map: List[dict]
    technical_conflict_flags: List[str]
    risk_flags: List[str]
    uncertainty_reasons: List[str]
    recommended_market_bias: Literal["selective_long", "defensive", "neutral"]


class EmilyToBobPacket(PacketBase):
    """Emily full report → Bob feature packet (transformation)."""
    source_agent: str = "Emily"
    target_agent: str = "Bob"
    regime: Literal["risk_on", "risk_off", "mixed", "fragile_rebound", "transition"]
    regime_confidence: float = Field(ge=0.0, le=1.0)
    preferred_sectors: List[str]
    avoid_sectors: List[str]
    market_bias: Literal["selective_long", "defensive", "neutral"]
    event_risk_level: float = Field(ge=0.0, le=1.0)
    market_uncertainty: float = Field(ge=0.0, le=1.0)
    technical_direction: Literal["up", "down", "mixed"]
    technical_confidence: float = Field(ge=0.0, le=1.0)
    reversal_risk: float = Field(ge=0.0, le=1.0)
