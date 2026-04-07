"""schemas.audit_schema - Pydantic schemas for propagation audit and calibration v3.6."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class NodeResult(BaseModel):
    """LangGraph node 결과 — LLM 판단 기반 흐름 제어에 사용됨."""
    next: str                          # 다음 노드 이름
    skip_reason: Optional[str] = None  # 스킵 이유
    retry: bool = False                # 재시도 요청
    retry_reason: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class PropagationAuditLog(BaseModel):
    """하위 signal이 상위 결정에 실제로 반영됐는지 추적."""
    date: str
    source_agent: str
    target_agent: str
    adopted_keyword_rate: float = Field(ge=0.0, le=1.0)
    dropped_critical_signal_rate: float = Field(ge=0.0, le=1.0)
    has_contradiction: bool
    semantic_similarity_score: float = Field(ge=0.0, le=1.0)
    technical_signal_adoption_rate: float = Field(ge=0.0, le=1.0)
    notes: Optional[str] = None


class CalibrationLog(BaseModel):
    """calibration 통과 기록."""
    date: str
    agent: str
    field_name: str
    raw_value: float
    calibrated_value: float
    method: Literal["rolling_std", "sector_relative", "shrinkage", "clipping"]
    was_clipped: bool = False
    was_shrunk: bool = False
