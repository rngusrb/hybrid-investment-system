"""schemas.dave_schema - Pydantic schemas for Dave (Risk Control Analyst) v3.6."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from schemas.base_schema import AgentBaseOutput, PacketBase


class RiskComponents(BaseModel):
    beta: float = Field(ge=0.0)
    illiquidity: float = Field(ge=0.0)
    sector_concentration: float = Field(ge=0.0)
    volatility: float = Field(ge=0.0)


class StressTest(BaseModel):
    severity_score: float = Field(ge=0.0, le=1.0)
    worst_case_drawdown: float = Field(ge=0.0)


class RiskConstraints(BaseModel):
    max_single_sector_weight: float = Field(ge=0.0, le=1.0)
    max_beta: float = Field(ge=0.0)
    max_gross_exposure: float = Field(ge=0.0, le=1.0)


class DaveOutput(AgentBaseOutput):
    agent: str = "Dave"
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_components: RiskComponents
    signal_conflict_risk: float = Field(ge=0.0, le=1.0, default=0.0)
    stress_test: StressTest
    risk_level: Literal["low", "medium", "high", "critical"]
    recommended_controls: List[str]
    risk_constraints: RiskConstraints
    trigger_risk_alert_meeting: bool  # risk_score > 0.75이면 True
