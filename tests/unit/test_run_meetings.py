"""tests/unit/test_run_meetings.py — meetings/run_meetings.py 단위 테스트 (LLM 호출 없음)."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from meetings.run_meetings import (
    run_mam,
    run_sdm,
    run_ram,
    run_all_meetings,
    format_meetings_for_prompt,
    RISK_ALERT_THRESHOLD,
    DEBATE_SKIP_CONFIDENCE,
)


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_stock_result(
    ticker: str,
    action: str = "BUY",
    consensus: str = "bullish",
    risk_level: str = "medium",
    action_changed: bool = False,
    risk_flags: list | None = None,
    tech_score: int = 6,
    fund_score: int = 6,
) -> dict:
    return {
        "ticker": ticker,
        "current_price": 150.0,
        "trader": {"action": action, "confidence": 0.7, "position_size_pct": 0.2},
        "risk_manager": {
            "final_action": action,
            "risk_level": risk_level,
            "action_changed": action_changed,
            "risk_flags": risk_flags or [],
        },
        "technical": {"technical_score": tech_score, "trend_direction": "up", "rsi": 55},
        "fundamental": {"fundamental_score": fund_score, "pe_ratio": 20},
        "researcher": {"consensus": consensus, "conviction": "high"},
    }


def make_sim_result(
    ticker: str,
    strategy: str = "momentum",
    sharpe: float = 1.2,
    mdd: float = 0.08,
    turnover: float = 0.2,
) -> dict:
    return {
        "ticker": ticker,
        "selected_strategy": strategy,
        "data_source": "real",
        "best": {
            "strategy": strategy,
            "sharpe": sharpe,
            "mdd": mdd,
            "turnover": turnover,
            "return": 0.05,
            "win_rate": 0.55,
            "n_bars": 60,
        },
    }


# ─── TestRunMAM ───────────────────────────────────────────────────────────────

class TestRunMAM:
    def test_required_fields(self):
        r = run_mam([], {}, "2024-06-30")
        for f in ["date", "market_regime", "market_bias", "bull_tickers",
                  "bear_tickers", "neutral_tickers", "signal_conflicts",
                  "debate_skipped", "consensus_score"]:
            assert f in r, f"필드 누락: {f}"

    def test_all_bull_regime_risk_on(self):
        results = [make_stock_result(t, "BUY", "bullish") for t in ["AAPL", "NVDA", "MSFT"]]
        r = run_mam(results, {}, "2024-06-30")
        assert r["market_regime"] == "risk_on"
        assert r["market_bias"] == "selective_long"
        assert sorted(r["bull_tickers"]) == ["AAPL", "MSFT", "NVDA"]

    def test_all_bear_regime_risk_off(self):
        results = [make_stock_result(t, "SELL", "bearish") for t in ["AAPL", "NVDA"]]
        r = run_mam(results, {}, "2024-06-30")
        assert r["market_regime"] == "risk_off"
        assert r["market_bias"] == "defensive"

    def test_mixed_regime(self):
        results = [
            make_stock_result("AAPL", "BUY", "bullish"),
            make_stock_result("NVDA", "SELL", "bearish"),
        ]
        r = run_mam(results, {}, "2024-06-30")
        assert r["market_regime"] == "mixed"
        assert r["market_bias"] == "neutral"

    def test_action_changed_creates_conflict(self):
        results = [make_stock_result("AAPL", "BUY", action_changed=True)]
        results[0]["risk_manager"]["final_action"] = "HOLD"
        r = run_mam(results, {}, "2024-06-30")
        assert len(r["signal_conflicts"]) >= 1
        conflict = r["signal_conflicts"][0]
        assert "AAPL" in conflict["ticker"]
        assert "risk_manager override" in conflict["resolution"]

    def test_tech_strong_fund_weak_conflict(self):
        results = [make_stock_result("AAPL", tech_score=8, fund_score=2)]
        r = run_mam(results, {}, "2024-06-30")
        assert any("tech_strong" in c["conflict"] for c in r["signal_conflicts"])

    def test_tech_weak_fund_strong_conflict(self):
        results = [make_stock_result("AAPL", tech_score=2, fund_score=8)]
        r = run_mam(results, {}, "2024-06-30")
        assert any("tech_weak" in c["conflict"] for c in r["signal_conflicts"])

    def test_debate_skipped_high_consensus(self):
        # 3 bull → consensus=1.0 ≥ 0.80 → skipped
        results = [make_stock_result(t, "BUY", "bullish") for t in ["A", "B", "C"]]
        r = run_mam(results, {}, "2024-06-30")
        assert r["debate_skipped"] is True

    def test_debate_not_skipped_low_consensus(self):
        # 50:50
        results = [
            make_stock_result("A", "BUY", "bullish"),
            make_stock_result("B", "SELL", "bearish"),
        ]
        r = run_mam(results, {}, "2024-06-30")
        assert r["debate_skipped"] is False

    def test_empty_stock_results(self):
        r = run_mam([], {}, "2024-06-30")
        assert r["market_regime"] == "mixed"
        assert r["bull_tickers"] == []

    def test_date_preserved(self):
        r = run_mam([], {}, "2024-12-31")
        assert r["date"] == "2024-12-31"


# ─── TestRunSDM ───────────────────────────────────────────────────────────────

class TestRunSDM:
    def test_required_fields(self):
        r = run_sdm([], {}, "2024-06-30")
        for f in ["date", "strategy_recommendations", "dominant_strategy",
                  "high_turnover_warnings", "low_sharpe_warnings",
                  "strategy_distribution"]:
            assert f in r, f"필드 누락: {f}"

    def test_strategy_recommendation_per_ticker(self):
        sim = {"AAPL": make_sim_result("AAPL"), "NVDA": make_sim_result("NVDA")}
        r = run_sdm([], sim, "2024-06-30")
        assert "AAPL" in r["strategy_recommendations"]
        assert "NVDA" in r["strategy_recommendations"]

    def test_high_turnover_warning(self):
        sim = {"AAPL": make_sim_result("AAPL", turnover=0.8)}
        r = run_sdm([], sim, "2024-06-30")
        assert "AAPL" in r["high_turnover_warnings"]
        hints = r["strategy_recommendations"]["AAPL"]["execution_hints"]
        assert any("staggered" in h for h in hints)

    def test_low_sharpe_warning(self):
        sim = {"NVDA": make_sim_result("NVDA", sharpe=0.1)}
        r = run_sdm([], sim, "2024-06-30")
        assert "NVDA" in r["low_sharpe_warnings"]
        hints = r["strategy_recommendations"]["NVDA"]["execution_hints"]
        assert any("reduce position" in h for h in hints)

    def test_high_mdd_hint(self):
        sim = {"TSLA": make_sim_result("TSLA", mdd=0.25)}
        r = run_sdm([], sim, "2024-06-30")
        hints = r["strategy_recommendations"]["TSLA"]["execution_hints"]
        assert any("stop-loss" in h for h in hints)

    def test_dominant_strategy(self):
        sim = {
            "A": make_sim_result("A", strategy="momentum"),
            "B": make_sim_result("B", strategy="momentum"),
            "C": make_sim_result("C", strategy="defensive"),
        }
        r = run_sdm([], sim, "2024-06-30")
        assert r["dominant_strategy"] == "momentum"

    def test_empty_sim_results(self):
        r = run_sdm([], {}, "2024-06-30")
        assert r["dominant_strategy"] == "defensive"
        assert r["strategy_recommendations"] == {}


# ─── TestRunRAM ───────────────────────────────────────────────────────────────

class TestRunRAM:
    def test_required_fields(self):
        r = run_ram([], "2024-06-30")
        for f in ["date", "triggered", "avg_risk_score", "max_risk_score",
                  "high_risk_tickers", "emergency_controls", "all_risk_flags"]:
            assert f in r, f"필드 누락: {f}"

    def test_not_triggered_low_risk(self):
        results = [make_stock_result("AAPL", risk_level="low")]
        r = run_ram(results, "2024-06-30")
        assert r["triggered"] is False
        assert r["emergency_controls"] == []

    def test_triggered_high_risk(self):
        results = [make_stock_result("AAPL", risk_level="high")]
        r = run_ram(results, "2024-06-30")
        assert r["triggered"] is True
        assert "AAPL" in r["high_risk_tickers"]
        assert len(r["emergency_controls"]) > 0

    def test_triggered_critical_risk(self):
        results = [make_stock_result("AAPL", risk_level="critical")]
        r = run_ram(results, "2024-06-30")
        assert r["triggered"] is True
        assert "immediate_de_risk" in r["emergency_controls"]

    def test_not_triggered_medium_risk(self):
        results = [make_stock_result("AAPL", risk_level="medium")]
        r = run_ram(results, "2024-06-30")
        assert r["triggered"] is False

    def test_risk_flags_collected(self):
        results = [
            make_stock_result("AAPL", risk_flags=["high_volatility", "gap_risk"]),
            make_stock_result("NVDA", risk_flags=["high_volatility"]),
        ]
        r = run_ram(results, "2024-06-30")
        assert "high_volatility" in r["all_risk_flags"]
        assert "gap_risk" in r["all_risk_flags"]

    def test_risk_flags_deduplicated(self):
        results = [
            make_stock_result("AAPL", risk_flags=["high_volatility"]),
            make_stock_result("NVDA", risk_flags=["high_volatility"]),
        ]
        r = run_ram(results, "2024-06-30")
        assert r["all_risk_flags"].count("high_volatility") == 1

    def test_avg_risk_score_computed(self):
        results = [
            make_stock_result("AAPL", risk_level="low"),    # 0.2
            make_stock_result("NVDA", risk_level="high"),   # 0.75
        ]
        r = run_ram(results, "2024-06-30")
        assert abs(r["avg_risk_score"] - 0.475) < 0.01

    def test_max_risk_score_is_highest(self):
        results = [
            make_stock_result("AAPL", risk_level="low"),
            make_stock_result("NVDA", risk_level="critical"),
        ]
        r = run_ram(results, "2024-06-30")
        assert r["max_risk_score"] == pytest.approx(0.95, abs=0.01)

    def test_empty_stock_results(self):
        r = run_ram([], "2024-06-30")
        assert r["triggered"] is False
        assert r["avg_risk_score"] == 0.0


# ─── TestRunAllMeetings ───────────────────────────────────────────────────────

class TestRunAllMeetings:
    def test_all_three_keys_present(self):
        results = [make_stock_result("AAPL")]
        sim = {"AAPL": make_sim_result("AAPL")}
        r = run_all_meetings(results, sim, "2024-06-30")
        for k in ["mam", "sdm", "ram", "ram_triggered"]:
            assert k in r, f"키 누락: {k}"

    def test_ram_triggered_flag_matches_ram(self):
        results = [make_stock_result("AAPL", risk_level="high")]
        sim = {}
        r = run_all_meetings(results, sim, "2024-06-30")
        assert r["ram_triggered"] == r["ram"]["triggered"]

    def test_ram_not_triggered_low_risk(self):
        results = [make_stock_result("AAPL", risk_level="low")]
        r = run_all_meetings(results, {}, "2024-06-30")
        assert r["ram_triggered"] is False


# ─── TestFormatMeetingsForPrompt ─────────────────────────────────────────────

class TestFormatMeetingsForPrompt:
    def _make_meetings(self, ram_triggered: bool = False) -> dict:
        results = [make_stock_result("AAPL", risk_level="high" if ram_triggered else "low")]
        sim = {"AAPL": make_sim_result("AAPL")}
        return run_all_meetings(results, sim, "2024-06-30")

    def test_empty_returns_empty_string(self):
        assert format_meetings_for_prompt({}) == ""

    def test_has_markers(self):
        text = format_meetings_for_prompt(self._make_meetings())
        assert "3 MEETINGS" in text
        assert "END 3 MEETINGS" in text

    def test_has_mam_section(self):
        text = format_meetings_for_prompt(self._make_meetings())
        assert "[MAM]" in text
        assert "Market Analysis" in text

    def test_has_sdm_section(self):
        text = format_meetings_for_prompt(self._make_meetings())
        assert "[SDM]" in text
        assert "Strategy Development" in text

    def test_has_ram_section(self):
        text = format_meetings_for_prompt(self._make_meetings())
        assert "[RAM]" in text
        assert "Risk Alert" in text

    def test_ram_alert_shown_when_triggered(self):
        text = format_meetings_for_prompt(self._make_meetings(ram_triggered=True))
        assert "경보 발동" in text or "AAPL" in text

    def test_ram_normal_shown_when_not_triggered(self):
        text = format_meetings_for_prompt(self._make_meetings(ram_triggered=False))
        assert "정상" in text

    def test_contains_ticker(self):
        meetings = self._make_meetings()
        text = format_meetings_for_prompt(meetings)
        assert "AAPL" in text

    def test_conflict_shown(self):
        results = [make_stock_result("TSLA", action_changed=True)]
        results[0]["risk_manager"]["final_action"] = "HOLD"
        sim = {}
        meetings = run_all_meetings(results, sim, "2024-06-30")
        text = format_meetings_for_prompt(meetings)
        assert "충돌" in text or "conflict" in text.lower()


# ─── TestRunMAMWithRReal ──────────────────────────────────────────────────────

class TestRunMAMWithRReal:
    def test_no_r_real_fields_none(self):
        r = run_mam([], {}, "2024-06-30")
        assert r["prior_r_real"] is None
        assert r["prior_performance"] is None

    def test_positive_large_r_real_prior_gain(self):
        r = run_mam([], {}, "2024-06-30", r_real=0.036)
        assert r["prior_r_real"] == pytest.approx(0.036)
        assert r["prior_performance"] == "prior_gain"

    def test_positive_small_r_real_prior_neutral(self):
        r = run_mam([], {}, "2024-06-30", r_real=0.005)
        assert r["prior_performance"] == "prior_neutral"

    def test_zero_r_real_prior_neutral(self):
        r = run_mam([], {}, "2024-06-30", r_real=0.0)
        assert r["prior_performance"] == "prior_neutral"

    def test_negative_r_real_prior_loss(self):
        r = run_mam([], {}, "2024-06-30", r_real=-0.021)
        assert r["prior_performance"] == "prior_loss"

    def test_boundary_exactly_002_prior_gain(self):
        r = run_mam([], {}, "2024-06-30", r_real=0.02)
        assert r["prior_performance"] == "prior_gain"


class TestRunAllMeetingsWithRReal:
    def test_r_real_propagates_to_mam(self):
        results = [make_stock_result("AAPL")]
        r = run_all_meetings(results, {}, "2024-06-30", r_real=0.05)
        assert r["mam"]["prior_r_real"] == pytest.approx(0.05)
        assert r["mam"]["prior_performance"] == "prior_gain"

    def test_r_real_none_by_default(self):
        results = [make_stock_result("AAPL")]
        r = run_all_meetings(results, {}, "2024-06-30")
        assert r["mam"]["prior_r_real"] is None

    def test_negative_r_real_loss_label(self):
        results = [make_stock_result("AAPL")]
        r = run_all_meetings(results, {}, "2024-06-30", r_real=-0.015)
        assert r["mam"]["prior_performance"] == "prior_loss"


class TestFormatMeetingsRReal:
    def _meetings_with_r_real(self, r_real: float | None) -> dict:
        results = [make_stock_result("AAPL")]
        return run_all_meetings(results, {}, "2024-06-30", r_real=r_real)

    def test_positive_r_real_shown_in_prompt(self):
        text = format_meetings_for_prompt(self._meetings_with_r_real(0.036))
        assert "+3.6%" in text or "3.6" in text

    def test_negative_r_real_shown_in_prompt(self):
        text = format_meetings_for_prompt(self._meetings_with_r_real(-0.021))
        assert "-2.1%" in text or "2.1" in text

    def test_no_r_real_no_prior_line(self):
        text = format_meetings_for_prompt(self._meetings_with_r_real(None))
        assert "이전 주기 실제수익률" not in text

    def test_prior_gain_label_in_prompt(self):
        text = format_meetings_for_prompt(self._meetings_with_r_real(0.05))
        assert "이전 전략 효과적" in text

    def test_prior_loss_label_in_prompt(self):
        text = format_meetings_for_prompt(self._meetings_with_r_real(-0.03))
        assert "손실" in text


# ─── TestLLMDebate ────────────────────────────────────────────────────────────

class MockLLM:
    """LLM 호출 mock — 고정 JSON 반환."""
    def __init__(self, response: str):
        self._response = response

    def chat(self, messages, system=""):
        return self._response


class TestRunMAMLLMDebate:
    def _mixed_results(self):
        """50:50 mixed → debate_skipped=False."""
        return [
            make_stock_result("AAPL", "BUY", "bullish"),
            make_stock_result("NVDA", "SELL", "bearish"),
        ]

    def test_llm_none_backward_compat(self):
        """llm=None이면 기존 heuristic resolution 사용."""
        r = run_mam(self._mixed_results(), {}, "2024-06-30", llm=None)
        assert r["llm_debate_used"] is False
        assert r["resolution"] != {}

    def test_debate_skipped_llm_not_called(self):
        """debate_skipped=True → llm 있어도 호출 안 됨."""
        results = [make_stock_result(t, "BUY", "bullish") for t in ["A", "B", "C"]]
        called = []

        class TrackingLLM:
            def chat(self, messages, system=""):
                called.append(True)
                return '{"consensus": "bullish", "recommended_bias": "risk_on", "confidence": 0.9, "key_risks": [], "debate_summary": "test"}'

        r = run_mam(results, {}, "2024-06-30", llm=TrackingLLM())
        assert r["debate_skipped"] is True
        assert len(called) == 0
        assert r["llm_debate_used"] is False

    def test_llm_debate_result_used_when_successful(self):
        """llm 성공 시 resolution이 LLM 결과로 교체됨."""
        llm = MockLLM(
            '{"consensus": "bearish", "recommended_bias": "risk_off", '
            '"confidence": 0.72, "key_risks": ["macro risk"], "debate_summary": "bears win"}'
        )
        r = run_mam(self._mixed_results(), {}, "2024-06-30", llm=llm)
        assert r["llm_debate_used"] is True
        assert r["resolution"]["consensus"] == "bearish"
        assert r["resolution"]["recommended_bias"] == "risk_off"
        assert r["resolution"].get("llm_debate") is True

    def test_llm_failure_fallback_to_heuristic(self):
        """llm 실패(빈 응답) → heuristic fallback."""
        llm = MockLLM("no json here")
        r = run_mam(self._mixed_results(), {}, "2024-06-30", llm=llm)
        assert r["llm_debate_used"] is False
        assert r["resolution"] != {}  # heuristic resolution 반환됨

    def test_llm_missing_required_fields_fallback(self):
        """llm 응답에 필수 필드 없으면 fallback."""
        llm = MockLLM('{"confidence": 0.5}')  # consensus/recommended_bias 없음
        r = run_mam(self._mixed_results(), {}, "2024-06-30", llm=llm)
        assert r["llm_debate_used"] is False

    def test_run_all_meetings_passes_llm(self):
        """run_all_meetings llm 파라미터가 run_mam으로 전달됨."""
        called = []

        class TrackingLLM:
            def chat(self, messages, system=""):
                called.append(True)
                return '{"consensus": "neutral", "recommended_bias": "neutral", "confidence": 0.6, "key_risks": [], "debate_summary": "test"}'

        r = run_all_meetings(self._mixed_results(), {}, "2024-06-30", llm=TrackingLLM())
        assert r["mam"]["llm_debate_used"] is True
        assert len(called) == 1

    def test_run_all_meetings_llm_none_default(self):
        """llm=None이 기본값 — 기존 테스트 하위 호환."""
        r = run_all_meetings(self._mixed_results(), {}, "2024-06-30")
        assert r["mam"]["llm_debate_used"] is False
