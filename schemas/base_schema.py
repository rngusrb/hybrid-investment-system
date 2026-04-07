"""공통 base schema 및 공통 field."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import date


class AgentBaseOutput(BaseModel):
    """모든 agent output의 base class."""
    agent: str
    date: str  # YYYY-MM-DD


class PacketBase(BaseModel):
    """agent 간 transformation packet base."""
    source_agent: str
    target_agent: str
    date: str


class ControlSignal(BaseModel):
    """uncertainty/confidence 제어 신호 — 실제 흐름 제어에 사용됨."""
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    needs_retry: bool = False
    retry_reason: Optional[str] = None
