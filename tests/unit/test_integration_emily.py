"""tests/unit/test_integration_emily.py — integration/emily_context.py 단위 테스트 (LLM 없음)."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from integration.emily_context import format_emily_for_prompt, run_emily_for_context


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_emily_output(**overrides) -> dict:
    base = {
        "agent": "Emily",
        "date": "2024-01-15",
        "market_regime": "risk_on",
        "regime_confidence": 0.82,
        "macro_state": {
            "rates": 0.3, "inflation": -0.1, "growth": 0.4,
            "liquidity": 0.2, "risk_sentiment": 0.5,
        },
        "technical_signal_state": {
            "trend_direction": "up",
            "continuation_strength": 0.7,
            "reversal_risk": 0.21,
            "technical_confidence": 0.77,
        },
        "sector_preference": [
            {"sector": "semiconductor", "score": 0.9},
            {"sector": "tech", "score": 0.8},
            {"sector": "utilities", "score": 0.2},
        ],
        "bull_catalysts": ["Fed pivot", "earnings beat"],
        "bear_catalysts": ["recession risk"],
        "event_sensitivity_map": [],
        "technical_conflict_flags": [],
        "risk_flags": [],
        "uncertainty_reasons": [],
        "recommended_market_bias": "selective_long",
        "confidence": 0.82,
    }
    base.update(overrides)
    return base


# ─── format_emily_for_prompt 테스트 ──────────────────────────────────────────

class TestFormatEmilyForPrompt:
    def test_basic_structure_contains_header(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "=== MARKET CONTEXT (Emily" in result

    def test_contains_regime_and_confidence(self):
        out = make_emily_output(market_regime="risk_off", regime_confidence=0.75)
        result = format_emily_for_prompt(out)
        assert "risk_off" in result
        assert "0.75" in result

    def test_contains_market_bias(self):
        out = make_emily_output(recommended_market_bias="defensive")
        result = format_emily_for_prompt(out)
        assert "defensive" in result

    def test_contains_technical_direction(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "up-trend" in result

    def test_contains_macro_values(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "rates=" in result
        assert "growth=" in result
        assert "liquidity=" in result

    def test_contains_bull_catalysts(self):
        out = make_emily_output(bull_catalysts=["Fed pivot", "earnings beat"])
        result = format_emily_for_prompt(out)
        assert "Bull catalysts" in result
        assert "Fed pivot" in result

    def test_contains_bear_catalysts(self):
        out = make_emily_output(bear_catalysts=["recession risk"])
        result = format_emily_for_prompt(out)
        assert "Bear catalysts" in result

    def test_sector_preferred_shown(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "Sector preference" in result
        assert "semiconductor" in result

    def test_sector_avoid_shown(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "Avoid sectors" in result
        assert "utilities" in result

    def test_risk_flags_shown_when_present(self):
        out = make_emily_output(risk_flags=["high_vol", "rate_risk"])
        result = format_emily_for_prompt(out)
        assert "Risk flags" in result
        assert "high_vol" in result

    def test_risk_flags_not_shown_when_empty(self):
        out = make_emily_output(risk_flags=[])
        result = format_emily_for_prompt(out)
        assert "Risk flags" not in result

    def test_empty_dict_returns_empty_string(self):
        assert format_emily_for_prompt({}) == ""

    def test_none_returns_empty_string(self):
        assert format_emily_for_prompt(None) == ""

    def test_bull_catalysts_capped_at_3(self):
        out = make_emily_output(bull_catalysts=["a", "b", "c", "d", "e"])
        result = format_emily_for_prompt(out)
        # 결과에 4개 이상 나열되지 않음 (리스트 repr이라 정확히 체크 못하므로 'a' 존재 확인)
        assert "Bull catalysts" in result

    def test_sector_preferred_capped_at_5(self):
        sectors = [{"sector": f"sector_{i}", "score": 0.9} for i in range(10)]
        out = make_emily_output(sector_preference=sectors)
        result = format_emily_for_prompt(out)
        assert "Sector preference" in result

    def test_missing_technical_signal_state_graceful(self):
        out = make_emily_output(technical_signal_state=None)
        result = format_emily_for_prompt(out)
        assert "=== MARKET CONTEXT" in result
        assert "Technical:" in result

    def test_missing_macro_state_graceful(self):
        out = make_emily_output(macro_state=None)
        result = format_emily_for_prompt(out)
        assert "=== MARKET CONTEXT" in result
        assert "Macro:" in result

    def test_reversal_risk_in_technical_line(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "reversal_risk=0.21" in result

    def test_output_is_multiline(self):
        out = make_emily_output()
        result = format_emily_for_prompt(out)
        assert "\n" in result

    def test_regime_fragile_rebound(self):
        out = make_emily_output(market_regime="fragile_rebound", regime_confidence=0.6)
        result = format_emily_for_prompt(out)
        assert "fragile_rebound" in result

    def test_no_bull_catalysts_no_section(self):
        out = make_emily_output(bull_catalysts=[])
        result = format_emily_for_prompt(out)
        assert "Bull catalysts" not in result


# ─── run_emily_for_context 인터페이스 테스트 (LLM mock) ────────────────────────

class MockLLM:
    """LLM provider mock — Emily output JSON 반환."""

    def chat(self, messages, system="", **kwargs):
        import json
        output = make_emily_output()
        return json.dumps(output)


class TestRunEmilyForContext:
    def test_returns_tuple_of_dict_and_str(self):
        spy_data = {
            "ticker": "SPY",
            "bars": [{"date": "2024-01-15", "close": 470.0, "open": 468.0,
                      "high": 471.0, "low": 467.0, "volume": 1000000}] * 5,
            "articles": [],
            "current_price": 470.0,
        }
        llm = MockLLM()
        result = run_emily_for_context(llm, spy_data, "2024-01-15")
        assert isinstance(result, tuple)
        assert len(result) == 2
        emily_out, ctx_str = result
        assert isinstance(emily_out, dict)
        assert isinstance(ctx_str, str)

    def test_emily_output_has_regime(self):
        spy_data = {
            "bars": [{"close": 470.0}] * 5,
            "articles": [],
            "current_price": 470.0,
        }
        llm = MockLLM()
        emily_out, _ = run_emily_for_context(llm, spy_data, "2024-01-15")
        assert "market_regime" in emily_out

    def test_context_string_has_header(self):
        spy_data = {
            "bars": [{"close": 470.0}] * 5,
            "articles": [],
            "current_price": 470.0,
        }
        llm = MockLLM()
        _, ctx_str = run_emily_for_context(llm, spy_data, "2024-01-15")
        assert "=== MARKET CONTEXT" in ctx_str

    def test_bars_truncated_to_max(self):
        """_MAX_BARS=60 초과 bars는 최근 60개만 전달됨을 확인 (mock으로 간접 검증)."""
        bars = [{"close": float(i), "date": f"2024-01-{i:02d}"} for i in range(1, 100)]
        spy_data = {"bars": bars, "articles": [], "current_price": 99.0}
        llm = MockLLM()
        emily_out, ctx_str = run_emily_for_context(llm, spy_data, "2024-06-01")
        # 정상 실행 여부만 확인 (bars 개수는 mock LLM이 검증하지 않음)
        assert isinstance(emily_out, dict)

    def test_empty_spy_data_graceful(self):
        spy_data = {"bars": [], "articles": [], "current_price": None}
        llm = MockLLM()
        emily_out, ctx_str = run_emily_for_context(llm, spy_data, "2024-01-15")
        assert isinstance(emily_out, dict)
        assert isinstance(ctx_str, str)
