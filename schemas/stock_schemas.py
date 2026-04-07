"""개별 종목 분석 파이프라인 스키마 (TradingAgents 구조)."""
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────
# Analyst Outputs
# ──────────────────────────────────────────

class FundamentalAnalystOutput(BaseModel):
    ticker: str
    date: str
    revenue: Optional[float] = None           # 최근 연간 매출 (USD)
    net_income: Optional[float] = None        # 순이익
    eps: Optional[float] = None               # 주당순이익
    pe_ratio: Optional[float] = None          # 주가수익비율
    revenue_growth_yoy: Optional[float] = None  # 매출 전년비 성장률 [-1,1]
    profit_margin: Optional[float] = None     # 영업이익률 [0,1]
    intrinsic_value_signal: Literal["undervalued", "fairly_valued", "overvalued"] = "fairly_valued"
    fundamental_score: float = Field(0.5, ge=0, le=1)  # 0=매우 약함 / 1=매우 강함
    key_risks: List[str] = Field(default_factory=list)
    key_strengths: List[str] = Field(default_factory=list)
    summary: str = ""


class SentimentAnalystOutput(BaseModel):
    ticker: str
    date: str
    sentiment_score: float = Field(0.0, ge=-1, le=1)   # -1=극도 부정 / 1=극도 긍정
    uncertainty: float = Field(0.5, ge=0, le=1)
    dominant_emotion: Literal["fear", "greed", "neutral", "optimism", "panic"] = "neutral"
    news_volume: int = 0                                # 분석된 뉴스 건수
    key_themes: List[str] = Field(default_factory=list)
    summary: str = ""


class NewsAnalystOutput(BaseModel):
    ticker: str
    date: str
    macro_impact: float = Field(0.0, ge=-1, le=1)     # 거시경제 영향 (-1=매우 부정 / 1=매우 긍정)
    company_events: List[str] = Field(default_factory=list)   # 주요 회사 이벤트
    industry_trends: List[str] = Field(default_factory=list)  # 산업 트렌드
    event_risk_level: float = Field(0.3, ge=0, le=1)  # 이벤트 리스크
    catalyst_signals: List[str] = Field(default_factory=list) # 상승/하락 촉매
    summary: str = ""


class TechnicalAnalystOutput(BaseModel):
    ticker: str
    date: str
    trend_direction: Literal["up", "down", "sideways"] = "sideways"
    trend_strength: float = Field(0.5, ge=0, le=1)
    rsi: Optional[float] = Field(None, ge=0, le=100)
    macd_signal: Literal["bullish", "bearish", "neutral"] = "neutral"
    bollinger_position: Literal["upper", "middle", "lower"] = "middle"  # 볼린저 밴드 위치
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    entry_signal: Literal["strong_buy", "buy", "neutral", "sell", "strong_sell"] = "neutral"
    technical_score: float = Field(0.5, ge=0, le=1)   # 0=매우 약함 / 1=매우 강함
    summary: str = ""


# ──────────────────────────────────────────
# Researcher Output
# ──────────────────────────────────────────

class ResearcherOutput(BaseModel):
    ticker: str
    date: str
    bull_thesis: str = ""                              # 매수 논거
    bear_thesis: str = ""                              # 매도 논거
    consensus: Literal["bullish", "bearish", "neutral"] = "neutral"
    conviction: float = Field(0.5, ge=0, le=1)        # 합의 확신도
    key_debate_points: List[str] = Field(default_factory=list)
    risk_reward_ratio: Optional[float] = None          # 기대수익/리스크 비율
    summary: str = ""


# ──────────────────────────────────────────
# Trader Output
# ──────────────────────────────────────────

class TraderOutput(BaseModel):
    ticker: str
    date: str
    action: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    confidence: float = Field(0.5, ge=0, le=1)
    position_size_pct: float = Field(0.0, ge=0, le=1) # 포트폴리오 대비 비중
    target_price: Optional[float] = None               # 목표주가
    stop_loss_price: Optional[float] = None            # 손절가
    time_horizon: Literal["short", "medium", "long"] = "medium"  # 단기/중기/장기
    reasoning: List[str] = Field(default_factory=list)
    key_signals_used: List[str] = Field(default_factory=list)

    @field_validator("position_size_pct")
    @classmethod
    def validate_position(cls, v):
        return round(min(max(v, 0.0), 1.0), 4)
