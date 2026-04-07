"""schemas.meeting_schema - Pydantic schemas for Meeting protocol v3.6."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class BullCase(BaseModel):
    growth_path: str
    upside_catalysts: List[str]
    sustainability: str


class BearCase(BaseModel):
    downside_risks: List[str]
    fragility: str
    reversal_triggers: List[str]


class DebateResolution(BaseModel):
    bull_case: BullCase
    bear_case: BearCase
    moderator_summary: str
    unresolved_issues: List[str]
    regime_confidence_adjustment: float = Field(ge=-0.5, le=0.5)


class ConflictItem(BaseModel):
    signal_a: str
    signal_b: str
    conflict_type: Literal["time_horizon_mismatch", "direction_conflict", "magnitude_conflict", "regime_mismatch"]
    resolution: str


class SignalConflictResolution(BaseModel):
    conflict_matrix: List[ConflictItem]


class WeeklyMarketReport(BaseModel):
    date: str
    market_regime: str
    regime_confidence: float
    preferred_sectors: List[str]
    avoid_sectors: List[str]
    unresolved_risks: List[str]
    debate_resolution: DebateResolution
    signal_conflict_resolution: SignalConflictResolution
    technical_summary_packet: dict  # TechnicalSignalState-like


class WeeklyStrategySet(BaseModel):
    date: str
    candidate_strategies: List[str]
    selected_strategies: List[str]
    rejection_reasons: dict  # strategy_name → reason
    optimization_notes: List[str]
    execution_feasibility_hints: List[str]
    technical_alignment_summary: str
