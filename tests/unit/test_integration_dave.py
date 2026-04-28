"""tests/unit/test_integration_dave.py — integration/dave_context.py 단위 테스트 (LLM 없음)."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from integration.dave_context import build_dave_input, format_dave_for_prompt, run_dave_for_portfolio


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_portfolio(**overrides) -> dict:
    base = {
        "allocations": [
            {"ticker": "AAPL", "weight": 0.3, "action": "BUY"},
            {"ticker": "NVDA", "weight": 0.3, "action": "BUY"},
            {"ticker": "MSFT", "weight": 0.2, "action": "HOLD"},
        ],
        "total_equity_pct": 0.8,
        "cash_pct": 0.15,
        "hedge_pct": 0.05,
        "portfolio_risk_level": "medium",
        "rebalance_urgency": 0.5,
        "entry_style": "staggered",
    }
    base.update(overrides)
    return base


def make_stock_result(ticker: str, tech_score: float = 0.6, risk_level: str = "medium",
                       sector: str = "tech") -> dict:
    return {
        "ticker": ticker,
        "current_price": 100.0,
        "technical": {"technical_score": tech_score},
        "fundamental": {"sector": sector},
        "risk_manager": {"risk_level": risk_level, "final_action": "BUY"},
    }


def make_dave_output(**overrides) -> dict:
    base = {
        "agent": "Dave",
        "date": "2024-01-15",
        "risk_score": 0.42,
        "risk_components": {
            "beta": 0.35, "illiquidity": 0.12,
            "sector_concentration": 0.28, "volatility": 0.31,
        },
        "signal_conflict_risk": 0.1,
        "stress_test": {"severity_score": 0.45, "worst_case_drawdown": 0.142},
        "risk_level": "medium",
        "recommended_controls": ["reduce_exposure", "add_hedge"],
        "risk_constraints": {
            "max_single_sector_weight": 0.4,
            "max_beta": 1.5,
            "max_gross_exposure": 1.0,
        },
        "trigger_risk_alert_meeting": False,
        "confidence": 0.75,
    }
    base.update(overrides)
    return base


# ─── build_dave_input 테스트 ──────────────────────────────────────────────────

class TestBuildDaveInput:
    def test_returns_dict(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL"), make_stock_result("NVDA")]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        assert isinstance(result, dict)

    def test_has_date(self):
        portfolio = make_portfolio()
        result = build_dave_input(portfolio, [], "2024-01-15")
        assert result["date"] == "2024-01-15"

    def test_has_portfolio_summary(self):
        portfolio = make_portfolio()
        result = build_dave_input(portfolio, [], "2024-01-15")
        assert "portfolio_summary" in result
        ps = result["portfolio_summary"]
        assert "total_equity_pct" in ps
        assert "cash_pct" in ps
        assert "hedge_pct" in ps

    def test_has_pre_computed_risk_components(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL"), make_stock_result("NVDA"), make_stock_result("MSFT")]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        comp = result["pre_computed_risk_components"]
        assert "beta" in comp
        assert "illiquidity" in comp
        assert "sector_concentration" in comp
        assert "volatility" in comp

    def test_risk_components_in_0_1_range(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result(t) for t in ["AAPL", "NVDA", "MSFT"]]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        comp = result["pre_computed_risk_components"]
        for key, val in comp.items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"

    def test_hhi_single_sector_equals_1(self):
        """모든 종목이 같은 섹터 → HHI = 1.0."""
        portfolio = make_portfolio(
            allocations=[
                {"ticker": "AAPL", "weight": 0.5, "action": "BUY"},
                {"ticker": "MSFT", "weight": 0.5, "action": "BUY"},
            ]
        )
        stocks = [
            make_stock_result("AAPL", sector="tech"),
            make_stock_result("MSFT", sector="tech"),
        ]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        hhi = result["pre_computed_risk_components"]["sector_concentration"]
        assert abs(hhi - 1.0) < 1e-6

    def test_hhi_two_equal_sectors_less_than_1(self):
        """두 섹터 균등 분포 → HHI = 0.5."""
        portfolio = make_portfolio(
            allocations=[
                {"ticker": "AAPL", "weight": 0.5, "action": "BUY"},
                {"ticker": "XOM", "weight": 0.5, "action": "BUY"},
            ]
        )
        stocks = [
            make_stock_result("AAPL", sector="tech"),
            make_stock_result("XOM", sector="energy"),
        ]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        hhi = result["pre_computed_risk_components"]["sector_concentration"]
        assert abs(hhi - 0.5) < 1e-6

    def test_illiquidity_zero_when_no_hedge(self):
        portfolio = make_portfolio(hedge_pct=0.0, total_equity_pct=1.0)
        result = build_dave_input(portfolio, [], "2024-01-15")
        assert result["pre_computed_risk_components"]["illiquidity"] < 0.01

    def test_allocations_summary_included(self):
        portfolio = make_portfolio()
        result = build_dave_input(portfolio, [], "2024-01-15")
        assert "allocations" in result
        assert len(result["allocations"]) == 3

    def test_no_raw_data_in_output(self):
        """bars, articles 등 raw data 필드가 없어야 함 (Otto 위반 방지)."""
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL")]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        forbidden = {"bars", "articles", "raw_market_data", "ohlcv", "news_articles"}
        assert not (set(result.keys()) & forbidden)

    def test_empty_allocations_still_returns_dict(self):
        portfolio = make_portfolio(allocations=[])
        result = build_dave_input(portfolio, [], "2024-01-15")
        assert isinstance(result, dict)
        assert result["pre_computed_risk_components"]["beta"] == 0.0

    def test_high_risk_stock_raises_volatility(self):
        portfolio = make_portfolio(
            allocations=[{"ticker": "TSLA", "weight": 1.0, "action": "BUY"}]
        )
        stocks = [make_stock_result("TSLA", risk_level="critical")]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        vol = result["pre_computed_risk_components"]["volatility"]
        assert vol >= 0.8  # critical → 0.9 proxy

    def test_sector_breakdown_included(self):
        portfolio = make_portfolio()
        stocks = [
            make_stock_result("AAPL", sector="tech"),
            make_stock_result("NVDA", sector="semiconductor"),
            make_stock_result("MSFT", sector="tech"),
        ]
        result = build_dave_input(portfolio, stocks, "2024-01-15")
        assert "sector_breakdown" in result


# ─── format_dave_for_prompt 테스트 ───────────────────────────────────────────

class TestFormatDaveForPrompt:
    def test_basic_header(self):
        out = make_dave_output()
        result = format_dave_for_prompt(out)
        assert "=== PORTFOLIO RISK (Dave" in result

    def test_contains_risk_score(self):
        out = make_dave_output(risk_score=0.42)
        result = format_dave_for_prompt(out)
        assert "0.42" in result

    def test_contains_risk_level(self):
        out = make_dave_output(risk_level="high")
        result = format_dave_for_prompt(out)
        assert "high" in result

    def test_contains_components(self):
        out = make_dave_output()
        result = format_dave_for_prompt(out)
        assert "beta=" in result
        assert "illiquidity=" in result
        assert "sector_conc=" in result
        assert "vol=" in result

    def test_contains_stress_test(self):
        out = make_dave_output()
        result = format_dave_for_prompt(out)
        assert "Stress Test" in result
        assert "worst_case=" in result

    def test_controls_shown(self):
        out = make_dave_output(recommended_controls=["reduce_exposure"])
        result = format_dave_for_prompt(out)
        assert "Controls" in result
        assert "reduce_exposure" in result

    def test_risk_alert_shown_when_triggered(self):
        out = make_dave_output(trigger_risk_alert_meeting=True, risk_score=0.8)
        result = format_dave_for_prompt(out)
        assert "Risk Alert" in result

    def test_risk_alert_not_shown_when_not_triggered(self):
        out = make_dave_output(trigger_risk_alert_meeting=False)
        result = format_dave_for_prompt(out)
        assert "Risk Alert" not in result

    def test_empty_dict_returns_empty_string(self):
        assert format_dave_for_prompt({}) == ""

    def test_none_returns_empty_string(self):
        assert format_dave_for_prompt(None) == ""

    def test_stress_test_drawdown_as_percent(self):
        """worst_case_drawdown=0.142 → 표시 14.2%."""
        out = make_dave_output()
        result = format_dave_for_prompt(out)
        assert "14.2%" in result


# ─── run_dave_for_portfolio 인터페이스 테스트 ─────────────────────────────────

class MockLLM:
    def chat(self, messages, system="", **kwargs):
        import json
        return json.dumps(make_dave_output())


class TestRunDaveForPortfolio:
    def test_returns_tuple(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL"), make_stock_result("NVDA")]
        llm = MockLLM()
        result = run_dave_for_portfolio(llm, portfolio, stocks, "2024-01-15")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_dict_and_str(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL")]
        llm = MockLLM()
        dave_out, ctx = run_dave_for_portfolio(llm, portfolio, stocks, "2024-01-15")
        assert isinstance(dave_out, dict)
        assert isinstance(ctx, str)

    def test_context_has_header(self):
        portfolio = make_portfolio()
        stocks = [make_stock_result("AAPL")]
        llm = MockLLM()
        _, ctx = run_dave_for_portfolio(llm, portfolio, stocks, "2024-01-15")
        assert "=== PORTFOLIO RISK" in ctx

    def test_empty_portfolio_returns_empty(self):
        llm = MockLLM()
        dave_out, ctx = run_dave_for_portfolio(llm, {}, [], "2024-01-15")
        assert dave_out == {}
        assert ctx == ""

    def test_portfolio_without_allocations_returns_empty(self):
        portfolio = make_portfolio(allocations=[])
        llm = MockLLM()
        dave_out, ctx = run_dave_for_portfolio(llm, portfolio, [], "2024-01-15")
        assert dave_out == {}
        assert ctx == ""
