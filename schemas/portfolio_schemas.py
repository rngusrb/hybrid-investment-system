"""포트폴리오 매니저 스키마 — 멀티 종목 signal → 최종 포트폴리오 배분."""
from typing import Literal, Optional, List, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


class StockAllocation(BaseModel):
    """개별 종목 배분."""
    ticker: str
    weight: float = Field(0.0, ge=0, le=1)          # 포트폴리오 대비 비중
    action: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    rationale: str = ""                               # 이 종목 배분 근거


class PortfolioManagerOutput(BaseModel):
    """멀티 종목 signal을 받아 포트폴리오 전체 배분 결정."""
    date: str
    tickers_analyzed: List[str] = Field(default_factory=list)

    # 종목별 배분
    allocations: List[StockAllocation] = Field(default_factory=list)

    # 포트폴리오 수준 배분
    total_equity_pct: float = Field(0.0, ge=0, le=1)   # 주식 전체 비중
    cash_pct: float = Field(0.0, ge=0, le=1)            # 현금 비중
    hedge_pct: float = Field(0.0, ge=0, le=1)           # 헤지 비중

    # 헤지 전략
    hedge_instrument: Literal["none", "put_option", "inverse_etf", "stop_order"] = "none"

    # 포트폴리오 리스크
    portfolio_risk_level: Literal["low", "moderate", "high", "extreme"] = "moderate"
    concentration_risk: bool = False                    # 특정 종목 쏠림 여부
    diversification_score: float = Field(0.5, ge=0, le=1)  # 분산도 (1=완전분산)

    # 실행 계획
    rebalance_urgency: Literal["immediate", "this_week", "this_month", "monitor"] = "monitor"
    entry_style: Literal["immediate", "staggered", "phased", "hold"] = "hold"

    # 판단 근거
    market_outlook: str = ""                            # 전반적 시장 전망
    key_risks: List[str] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_total(self):
        total = round(self.total_equity_pct + self.cash_pct + self.hedge_pct, 4)
        if abs(total - 1.0) > 0.05:
            # 합이 100%가 아니면 현금으로 보정
            self.cash_pct = round(1.0 - self.total_equity_pct - self.hedge_pct, 4)
            self.cash_pct = max(0.0, min(1.0, self.cash_pct))
        return self

    @field_validator("total_equity_pct", "cash_pct", "hedge_pct", "diversification_score")
    @classmethod
    def clamp_pct(cls, v):
        return round(min(max(v, 0.0), 1.0), 4)
