"""tests/unit/test_portfolio_pipeline.py — portfolio_pipeline.py 단위 테스트 (LLM 호출 없음).

검증 대상:
  1. run_portfolio_manager()가 r_real 있는 memory_context를 user 메시지에 포함하는지
  2. 파싱 실패 시 logger.warning 발생하는지
  3. 프롬프트 시스템에 Historical Performance Context 섹션이 있는지
"""
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from scripts.portfolio_pipeline import run_portfolio_manager


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_stock_result(ticker: str = "AAPL", action: str = "BUY") -> dict:
    return {
        "ticker": ticker,
        "current_price": 150.0,
        "bars": [],
        "fundamental": {"fundamental_score": 7, "intrinsic_value_signal": "undervalued", "pe_ratio": 25},
        "sentiment": {},
        "news": {},
        "technical": {"technical_score": 6, "trend_direction": "upward", "rsi": 55},
        "researcher": {"consensus": "bullish", "conviction": "high", "risk_reward_ratio": 2.5},
        "trader": {"action": action, "confidence": 0.8, "position_size_pct": 0.2},
        "risk_manager": {
            "final_action": action,
            "risk_level": "low",
            "action_changed": False,
            "final_position_size_pct": 0.2,
            "cash_reserve_pct": 0.1,
            "hedge_type": "none",
            "risk_flags": [],
        },
    }


def make_valid_portfolio_output(tickers: list[str]) -> dict:
    """PortfolioManagerOutput 검증을 통과하는 최소 JSON."""
    return {
        "date": "2024-03-22",
        "tickers_analyzed": tickers,
        "allocations": [
            {"ticker": t, "weight": 0.3, "action": "BUY", "rationale": "strong signal"}
            for t in tickers
        ],
        "total_equity_pct": 0.3 * len(tickers),
        "cash_pct": round(1.0 - 0.3 * len(tickers), 2),
        "hedge_pct": 0.0,
        "hedge_instrument": "none",
        "portfolio_risk_level": "moderate",
        "concentration_risk": False,
        "diversification_score": 0.75,
        "rebalance_urgency": "this_week",
        "entry_style": "immediate",
        "market_outlook": "Positive signals overall.",
        "key_risks": ["macro uncertainty"],
        "reasoning": [
            "Signal analysis complete.",
            "이전 주기 실제수익률 +3.6% 참조: AAPL 포지션 유지 확신",
        ],
    }


# ─── 시스템 프롬프트 정적 검사 ────────────────────────────────────────────────

class TestSystemPromptContent:
    """prompts/portfolio_manager_system.md에 필수 섹션이 있는지 검증."""

    def setup_method(self):
        self.prompt = (ROOT / "prompts/portfolio_manager_system.md").read_text(encoding="utf-8")

    def test_historical_performance_section_exists(self):
        assert "## Historical Performance Context" in self.prompt

    def test_r_real_instruction_exists(self):
        assert "r_real" in self.prompt or "실제수익률" in self.prompt

    def test_reasoning_obligation_exists(self):
        """reasoning 필드 의무 언급이 있는지."""
        assert "reasoning" in self.prompt

    def test_negative_return_instruction_exists(self):
        """손실 시 배분 축소 지침이 있는지."""
        assert "20~30%" in self.prompt or "축소" in self.prompt

    def test_streak_instruction_exists(self):
        assert "연속" in self.prompt

    def test_action_changed_instruction_exists(self):
        assert "action_changed" in self.prompt


# ─── memory_context 주입 검증 ────────────────────────────────────────────────

class TestMemoryContextInjection:
    """run_portfolio_manager()가 memory_context를 user 메시지에 올바르게 주입하는지."""

    def _make_llm(self, output_dict: dict) -> MagicMock:
        llm = MagicMock()
        llm.chat.return_value = json.dumps(output_dict)
        return llm

    def test_memory_context_appears_in_user_message(self):
        """memory_context가 LLM에 전달되는 user 메시지에 포함되는지."""
        tickers = ["AAPL"]
        memory_ctx = "=== MEMORY CONTEXT (이전 주기: 2024-03-15) ===\n  실제수익률: +3.6% (검증됨)\n=== END MEMORY CONTEXT ==="
        llm = self._make_llm(make_valid_portfolio_output(tickers))

        run_portfolio_manager(llm, "2024-03-22", [make_stock_result("AAPL")],
                              memory_context=memory_ctx)

        call_kwargs = llm.chat.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = messages[0]["content"]
        assert "실제수익률" in user_content
        assert "MEMORY CONTEXT" in user_content

    def test_empty_memory_context_no_empty_section(self):
        """memory_context가 빈 문자열이면 user 메시지에 'MEMORY CONTEXT' 없어야 함."""
        tickers = ["AAPL"]
        llm = self._make_llm(make_valid_portfolio_output(tickers))

        run_portfolio_manager(llm, "2024-03-22", [make_stock_result("AAPL")],
                              memory_context="")

        call_kwargs = llm.chat.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = messages[0]["content"]
        assert "MEMORY CONTEXT" not in user_content

    def test_r_real_positive_in_memory_context(self):
        """양수 r_real이 memory_context에 있으면 그 값이 user 메시지에 노출된다."""
        tickers = ["NVDA"]
        memory_ctx = "=== MEMORY CONTEXT ===\n  실제수익률: +5.2% (검증됨)\n=== END MEMORY CONTEXT ==="
        llm = self._make_llm(make_valid_portfolio_output(tickers))

        run_portfolio_manager(llm, "2024-03-22", [make_stock_result("NVDA")],
                              memory_context=memory_ctx)

        call_kwargs = llm.chat.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = messages[0]["content"]
        assert "+5.2%" in user_content

    def test_negative_r_real_in_memory_context(self):
        """음수 r_real도 user 메시지에 노출된다."""
        tickers = ["TSLA"]
        memory_ctx = "=== MEMORY CONTEXT ===\n  실제수익률: -2.1% (검증됨)\n=== END MEMORY CONTEXT ==="
        llm = self._make_llm(make_valid_portfolio_output(tickers))

        run_portfolio_manager(llm, "2024-03-22", [make_stock_result("TSLA")],
                              memory_context=memory_ctx)

        call_kwargs = llm.chat.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = messages[0]["content"]
        assert "-2.1%" in user_content


# ─── 파싱 실패 로깅 검증 ─────────────────────────────────────────────────────

class TestParsingFailureLogging:
    """파싱 실패 시 logger.warning이 호출되는지."""

    def test_no_json_in_response_triggers_warning(self, caplog):
        """LLM이 JSON 없는 텍스트를 반환하면 warning 로그가 찍혀야 한다."""
        llm = MagicMock()
        llm.chat.return_value = "Sorry, I cannot process this request."

        with caplog.at_level(logging.WARNING, logger="scripts.portfolio_pipeline"):
            result = run_portfolio_manager(llm, "2024-03-22", [make_stock_result("AAPL")])

        assert result == {}
        # 3번 시도이므로 warning 3회
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 3

    def test_invalid_json_syntax_triggers_warning(self, caplog):
        """JSON 파싱은 되지만 invalid syntax면 warning."""
        llm = MagicMock()
        # { } 있지만 invalid JSON (중괄호 있어서 match는 되나 json.loads 실패)
        llm.chat.return_value = '{"broken": True_not_valid}'

        with caplog.at_level(logging.WARNING, logger="scripts.portfolio_pipeline"):
            result = run_portfolio_manager(llm, "2024-03-22", [make_stock_result("AAPL")])

        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 1

    def test_successful_parse_no_warning(self, caplog):
        """정상 파싱 시 warning 없어야 한다."""
        tickers = ["AAPL"]
        llm = MagicMock()
        llm.chat.return_value = json.dumps(make_valid_portfolio_output(tickers))

        with caplog.at_level(logging.WARNING, logger="scripts.portfolio_pipeline"):
            result = run_portfolio_manager(llm, "2024-03-22", [make_stock_result("AAPL")])

        assert result != {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 0


# ─── 멀티 컨텍스트 주입 검증 ─────────────────────────────────────────────────

class TestMultiContextInjection:
    """memory + sim + meetings + calibration 컨텍스트 동시 주입 검증."""

    def test_all_contexts_present_in_user_message(self):
        tickers = ["AAPL"]
        llm = MagicMock()
        llm.chat.return_value = json.dumps(make_valid_portfolio_output(tickers))

        run_portfolio_manager(
            llm, "2024-03-22", [make_stock_result("AAPL")],
            memory_context="MEMORY_MARKER",
            sim_context="SIM_MARKER",
            meetings_context="MEETINGS_MARKER",
            calibration_context="CAL_MARKER",
        )

        call_kwargs = llm.chat.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][0]
        user_content = messages[0]["content"]
        assert "MEMORY_MARKER" in user_content
        assert "SIM_MARKER" in user_content
        assert "MEETINGS_MARKER" in user_content
        assert "CAL_MARKER" in user_content
