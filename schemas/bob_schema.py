"""schemas.bob_schema - Pydantic schemas for Bob (Strategy Analyst) v3.6."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from schemas.base_schema import AgentBaseOutput, PacketBase


class SimWindow(BaseModel):
    train_start: str  # YYYY-MM-DD
    train_end: str    # YYYY-MM-DD


class SimMetrics(BaseModel):
    return_: float = Field(alias="return")  # 'return'은 예약어라 alias 사용
    sharpe: float
    sortino: float
    mdd: float = Field(ge=0.0)
    turnover: float = Field(ge=0.0)
    hit_rate: float = Field(ge=0.0, le=1.0)

    model_config = {"populate_by_name": True}


class CandidateStrategy(BaseModel):
    name: str
    type: Literal["directional", "hedged", "market_neutral", "momentum", "defensive"]
    logic_summary: str
    regime_fit: float = Field(ge=0.0, le=1.0)
    technical_alignment: float = Field(ge=0.0, le=1.0)
    sim_window: SimWindow
    sim_metrics: SimMetrics
    failure_conditions: List[str]
    optimization_suggestions: List[str]
    confidence: float = Field(ge=0.0, le=1.0)


class BobOutput(AgentBaseOutput):
    agent: str = "Bob"
    candidate_strategies: List[CandidateStrategy]
    selected_for_review: List[str]  # strategy names


class BobToDavePacket(PacketBase):
    source_agent: str = "Bob"
    target_agent: str = "Dave"
    strategy_name: str
    expected_turnover: float = Field(ge=0.0)
    sector_bias: List[str]
    expected_vol_profile: float = Field(ge=0.0)
    failure_conditions: List[str]
    strategy_confidence: float = Field(ge=0.0, le=1.0)
    technical_alignment: float = Field(ge=0.0, le=1.0)


class BobToExecutionPacket(PacketBase):
    source_agent: str = "Bob"
    target_agent: str = "Execution"
    selected_strategy_name: str
    target_posture: str
    rebalance_urgency: float = Field(ge=0.0, le=1.0)
    expected_turnover: float = Field(ge=0.0)
    hedge_preference: Literal["none", "light", "moderate", "heavy"]
    execution_constraints_hint: List[str]
