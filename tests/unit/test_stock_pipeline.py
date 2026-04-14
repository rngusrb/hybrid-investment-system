"""tests/unit/test_stock_pipeline.py — 개별 종목 파이프라인 스키마/유틸 테스트."""
import pytest
from schemas.stock_schemas import (
    FundamentalAnalystOutput,
    SentimentAnalystOutput,
    NewsAnalystOutput,
    TechnicalAnalystOutput,
    ResearcherOutput,
    TraderOutput,
    RiskManagerOutput,
)
from schemas.portfolio_schemas import PortfolioManagerOutput, StockAllocation


# ──────────────────────────────────────────
# FundamentalAnalystOutput
# ──────────────────────────────────────────

class TestFundamentalAnalystOutput:
    def test_defaults(self):
        o = FundamentalAnalystOutput(ticker="AAPL", date="2024-01-15")
        assert o.fundamental_score == 0.5
        assert o.intrinsic_value_signal == "fairly_valued"

    def test_score_bounds(self):
        o = FundamentalAnalystOutput(ticker="AAPL", date="2024-01-15", fundamental_score=0.0)
        assert o.fundamental_score == 0.0
        with pytest.raises(Exception):
            FundamentalAnalystOutput(ticker="AAPL", date="2024-01-15", fundamental_score=1.5)

    def test_literal_field(self):
        with pytest.raises(Exception):
            FundamentalAnalystOutput(ticker="AAPL", date="2024-01-15", intrinsic_value_signal="cheap")


# ──────────────────────────────────────────
# SentimentAnalystOutput
# ──────────────────────────────────────────

class TestSentimentAnalystOutput:
    def test_score_range(self):
        o = SentimentAnalystOutput(ticker="AAPL", date="2024-01-15", sentiment_score=-0.5)
        assert o.sentiment_score == -0.5

    def test_invalid_score(self):
        with pytest.raises(Exception):
            SentimentAnalystOutput(ticker="AAPL", date="2024-01-15", sentiment_score=2.0)

    def test_dominant_emotion_literal(self):
        with pytest.raises(Exception):
            SentimentAnalystOutput(ticker="AAPL", date="2024-01-15", dominant_emotion="happy")


# ──────────────────────────────────────────
# TechnicalAnalystOutput
# ──────────────────────────────────────────

class TestTechnicalAnalystOutput:
    def test_defaults(self):
        o = TechnicalAnalystOutput(ticker="AAPL", date="2024-01-15")
        assert o.trend_direction == "sideways"
        assert o.macd_signal == "neutral"
        assert o.entry_signal == "neutral"

    def test_rsi_bounds(self):
        o = TechnicalAnalystOutput(ticker="AAPL", date="2024-01-15", rsi=75.0)
        assert o.rsi == 75.0
        with pytest.raises(Exception):
            TechnicalAnalystOutput(ticker="AAPL", date="2024-01-15", rsi=110.0)

    def test_invalid_entry_signal(self):
        with pytest.raises(Exception):
            TechnicalAnalystOutput(ticker="AAPL", date="2024-01-15", entry_signal="strong")


# ──────────────────────────────────────────
# ResearcherOutput
# ──────────────────────────────────────────

class TestResearcherOutput:
    def test_consensus_literal(self):
        with pytest.raises(Exception):
            ResearcherOutput(ticker="AAPL", date="2024-01-15", consensus="mixed")

    def test_conviction_bounds(self):
        o = ResearcherOutput(ticker="AAPL", date="2024-01-15", conviction=0.8)
        assert o.conviction == 0.8
        with pytest.raises(Exception):
            ResearcherOutput(ticker="AAPL", date="2024-01-15", conviction=1.5)


# ──────────────────────────────────────────
# TraderOutput
# ──────────────────────────────────────────

class TestTraderOutput:
    def test_action_literal(self):
        o = TraderOutput(ticker="AAPL", date="2024-01-15", action="BUY")
        assert o.action == "BUY"
        with pytest.raises(Exception):
            TraderOutput(ticker="AAPL", date="2024-01-15", action="STRONG_BUY")

    def test_position_size_clamp(self):
        o = TraderOutput(ticker="AAPL", date="2024-01-15", position_size_pct=0.08)
        assert o.position_size_pct == 0.08
        # validator clamps
        o2 = TraderOutput(ticker="AAPL", date="2024-01-15", position_size_pct=1.5)
        assert o2.position_size_pct == 1.0

    def test_time_horizon_literal(self):
        with pytest.raises(Exception):
            TraderOutput(ticker="AAPL", date="2024-01-15", time_horizon="yearly")


# ──────────────────────────────────────────
# RiskManagerOutput
# ──────────────────────────────────────────

class TestRiskManagerOutput:
    def test_defaults(self):
        o = RiskManagerOutput(ticker="AAPL", date="2024-01-15")
        assert o.final_action == "HOLD"
        assert o.action_changed is False
        assert o.hedge_type == "none"
        assert o.risk_level == "moderate"

    def test_action_changed_flag(self):
        o = RiskManagerOutput(
            ticker="AAPL", date="2024-01-15",
            final_action="HOLD", action_changed=True,
            final_position_size_pct=0.0, position_adjustment=-0.05
        )
        assert o.action_changed is True
        assert o.position_adjustment == -0.05

    def test_pct_clamp(self):
        o = RiskManagerOutput(ticker="AAPL", date="2024-01-15",
                              final_position_size_pct=1.5)
        assert o.final_position_size_pct == 1.0

    def test_risk_level_literal(self):
        with pytest.raises(Exception):
            RiskManagerOutput(ticker="AAPL", date="2024-01-15", risk_level="very_high")

    def test_hedge_type_literal(self):
        with pytest.raises(Exception):
            RiskManagerOutput(ticker="AAPL", date="2024-01-15", hedge_type="futures")


# ──────────────────────────────────────────
# PortfolioManagerOutput
# ──────────────────────────────────────────

class TestPortfolioManagerOutput:
    def _make(self, **kwargs):
        defaults = dict(
            date="2024-01-15",
            tickers_analyzed=["AAPL", "NVDA"],
            allocations=[
                StockAllocation(ticker="AAPL", weight=0.0, action="HOLD"),
                StockAllocation(ticker="NVDA", weight=0.35, action="BUY"),
            ],
            total_equity_pct=0.35,
            cash_pct=0.60,
            hedge_pct=0.05,
        )
        defaults.update(kwargs)
        return PortfolioManagerOutput(**defaults)

    def test_valid_allocation(self):
        o = self._make()
        assert o.total_equity_pct == 0.35
        assert o.cash_pct == 0.60

    def test_cash_autocorrect(self):
        # 합이 1.0 아닐 때 cash로 보정
        o = PortfolioManagerOutput(
            date="2024-01-15",
            total_equity_pct=0.40,
            cash_pct=0.70,   # 합이 1.1 → 보정
            hedge_pct=0.00,
        )
        # model_validator가 cash를 0.60으로 보정
        assert o.cash_pct == 0.60

    def test_risk_level_literal(self):
        with pytest.raises(Exception):
            self._make(portfolio_risk_level="very_low")

    def test_rebalance_urgency_literal(self):
        with pytest.raises(Exception):
            self._make(rebalance_urgency="asap")

    def test_entry_style_literal(self):
        with pytest.raises(Exception):
            self._make(entry_style="random")

    def test_stock_allocation_weight_bounds(self):
        with pytest.raises(Exception):
            StockAllocation(ticker="AAPL", weight=1.5, action="BUY")

    def test_stock_allocation_action_literal(self):
        with pytest.raises(Exception):
            StockAllocation(ticker="AAPL", weight=0.1, action="STRONG_BUY")
