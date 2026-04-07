"""schemas.otto_schema - Pydantic schemas for Otto (Fund Manager) v3.6.
주의: Otto는 raw data 필드 절대 없음. packet만 받음.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from schemas.base_schema import AgentBaseOutput, PacketBase


class AdaptiveWeights(BaseModel):
    w_sim: float = Field(ge=0.0, le=1.0)
    w_real: float = Field(ge=0.0, le=1.0)
    lookback_steps: int = Field(ge=1)


class Allocation(BaseModel):
    equities: float = Field(ge=0.0, le=1.0)
    hedge: float = Field(ge=0.0, le=1.0)
    cash: float = Field(ge=0.0, le=1.0)


class ExecutionPlan(BaseModel):
    entry_style: Literal["immediate", "staggered", "phased", "hold"]
    rebalance_frequency: Literal["daily", "weekly", "monthly", "event_driven"]
    stop_loss: float = Field(ge=0.0, le=1.0)


class OttoOutput(AgentBaseOutput):
    agent: str = "Otto"
    candidate_policies: List[str]
    adaptive_weights: AdaptiveWeights
    selected_policy: str
    allocation: Allocation
    execution_plan: ExecutionPlan
    policy_reasoning_summary: List[str]
    approval_status: Literal["approved", "approved_with_modification", "conditional_approval", "rejected"]


class OttoPolicyPacket(PacketBase):
    """3 agent packets + execution → Otto policy packet."""
    source_agent: str = "Aggregator"
    target_agent: str = "Otto"
    # Emily packet 요약
    market_regime: str
    regime_confidence: float
    market_bias: str
    technical_confidence: float
    reversal_risk: float
    market_uncertainty: float
    # Bob packet 요약
    selected_strategy_name: str
    strategy_confidence: float
    technical_alignment: float
    failure_conditions: List[str]
    # Dave packet 요약
    risk_score: float
    risk_level: str
    risk_constraints: dict
    trigger_risk_alert: bool
    # Execution feasibility
    rebalance_urgency: float
    execution_constraints_hint: List[str]
    # Reliability summary (agent별 신뢰도)
    agent_reliability_summary: dict  # {"emily": 0.8, "bob": 0.7, "dave": 0.75}
    # Reward history
    recent_reward_summary: Optional[dict] = None
