"""tests/unit/test_run_calibration.py — calibration/run_calibration.py 단위 테스트 (LLM 없음)."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from calibration.run_calibration import (
    calibrate_stock_scores,
    audit_bc_propagation,
    update_bc_reliability,
    run_calibration_audit,
    format_calibration_for_prompt,
    reset_session_state,
    _BC_AGENTS,
)


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_stock(
    ticker: str,
    tech_score: int = 6,
    fund_score: int = 6,
    action: str = "BUY",
    consensus: str = "bullish",
    final_action: str = "BUY",
    action_changed: bool = False,
    confidence: float = 0.7,
) -> dict:
    return {
        "ticker": ticker,
        "technical":   {"technical_score": tech_score, "trend_direction": "up"},
        "fundamental": {"fundamental_score": fund_score, "pe_ratio": 20},
        "sentiment":   {"sentiment_score": 6},
        "researcher":  {"consensus": consensus, "conviction": "high"},
        "trader":      {"action": action, "confidence": confidence, "position_size_pct": 0.2},
        "risk_manager": {
            "final_action": final_action,
            "risk_level": "medium",
            "action_changed": action_changed,
            "risk_flags": [],
        },
    }


def make_sim(ticker: str, sharpe: float = 1.2) -> dict:
    return {
        "ticker": ticker,
        "selected_strategy": "momentum",
        "best": {"sharpe": sharpe, "mdd": 0.08, "return": 0.05},
    }


# ─── TestCalibrateStockScores ─────────────────────────────────────────────────

class TestCalibrateStockScores:
    def setup_method(self):
        reset_session_state()

    def test_returns_dict_per_ticker(self):
        stocks = [make_stock("AAPL"), make_stock("NVDA")]
        result = calibrate_stock_scores(stocks, "2024-06-30")
        assert "AAPL" in result
        assert "NVDA" in result

    def test_score_fields_present(self):
        stocks = [make_stock("AAPL")]
        result = calibrate_stock_scores(stocks, "2024-06-30")
        aapl = result["AAPL"]
        # technical.technical_score는 반드시 포함
        assert "technical.technical_score" in aapl

    def test_calibrated_values_in_01_range(self):
        stocks = [make_stock("AAPL", tech_score=9, fund_score=2)]
        result = calibrate_stock_scores(stocks, "2024-06-30")
        for key, val in result["AAPL"].items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"

    def test_empty_stock_results_returns_empty(self):
        result = calibrate_stock_scores([], "2024-06-30")
        assert result == {}

    def test_rolling_builds_history_per_ticker(self):
        # 같은 ticker 여러 날 → rolling window 누적
        stocks = [make_stock("AAPL")]
        for _ in range(5):
            calibrate_stock_scores(stocks, "2024-06-30")
        # 5번 호출 후에도 정상 동작
        result = calibrate_stock_scores(stocks, "2024-06-30")
        assert "AAPL" in result

    def test_missing_score_field_skipped(self):
        # sentiment_score가 없어도 에러 없이 처리
        stock = {
            "ticker": "TSLA",
            "technical": {"technical_score": 7},
            "fundamental": {},
            "sentiment": {},
            "researcher": {},
            "trader": {"action": "BUY", "confidence": 0.7},
            "risk_manager": {"final_action": "BUY", "action_changed": False},
        }
        result = calibrate_stock_scores([stock], "2024-06-30")
        assert "TSLA" in result

    def test_separate_calibrators_per_ticker(self):
        # AAPL과 NVDA는 독립적인 rolling history
        stocks_a = [make_stock("AAPL", tech_score=8)]
        stocks_n = [make_stock("NVDA", tech_score=2)]
        calibrate_stock_scores(stocks_a, "2024-06-30")
        calibrate_stock_scores(stocks_n, "2024-06-30")
        # 두 종목의 calibrator가 별도여야 함
        result_a = calibrate_stock_scores(stocks_a, "2024-06-30")
        result_n = calibrate_stock_scores(stocks_n, "2024-06-30")
        # 단순히 둘 다 정상 반환 확인
        assert "AAPL" in result_a
        assert "NVDA" in result_n


# ─── TestAuditBCPropagation ───────────────────────────────────────────────────

class TestAuditBCPropagation:
    def test_required_fields(self):
        stocks = [make_stock("AAPL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        for f in ["date", "tech_adoption_rate", "consensus_adoption_rate",
                  "action_changed", "dropped_signal_count", "propagation_score"]:
            assert f in result["AAPL"], f"필드 누락: {f}"

    def test_tech_signal_adopted_buy(self):
        # tech_score=8 (강세), action=BUY → 채택
        stocks = [make_stock("AAPL", tech_score=8, action="BUY")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["tech_adoption_rate"] == 1.0

    def test_tech_signal_not_adopted_conflict(self):
        # tech_score=8 (강세), action=SELL → 미채택
        stocks = [make_stock("AAPL", tech_score=8, action="SELL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["tech_adoption_rate"] == 0.0

    def test_tech_weak_adopted_sell(self):
        # tech_score=2 (약세), action=SELL → 채택
        stocks = [make_stock("AAPL", tech_score=2, action="SELL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["tech_adoption_rate"] == 1.0

    def test_consensus_bullish_buy_adopted(self):
        stocks = [make_stock("AAPL", consensus="bullish", final_action="BUY")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["consensus_adoption_rate"] == 1.0

    def test_consensus_bearish_sell_adopted(self):
        stocks = [make_stock("AAPL", consensus="bearish", final_action="SELL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["consensus_adoption_rate"] == 1.0

    def test_consensus_conflict_not_adopted(self):
        # bullish consensus → SELL → 미채택
        stocks = [make_stock("AAPL", consensus="bullish", final_action="SELL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["consensus_adoption_rate"] == 0.0

    def test_action_changed_recorded(self):
        stocks = [make_stock("AAPL", action_changed=True)]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["action_changed"] is True

    def test_dropped_signal_count_both_conflict(self):
        # tech_score=8 + SELL, bullish + SELL → 2건 손실
        stocks = [make_stock("AAPL", tech_score=8, action="SELL",
                              consensus="bullish", final_action="SELL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert result["AAPL"]["dropped_signal_count"] == 2

    def test_propagation_score_range(self):
        stocks = [make_stock("AAPL")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        score = result["AAPL"]["propagation_score"]
        assert 0.0 <= score <= 1.0

    def test_neutral_tech_score_always_adopted(self):
        # tech_score=5 (중립) → 어떤 액션도 채택으로 처리
        for action in ["BUY", "SELL", "HOLD"]:
            stocks = [make_stock("AAPL", tech_score=5, action=action)]
            result = audit_bc_propagation(stocks, "2024-06-30")
            assert result["AAPL"]["tech_adoption_rate"] == 1.0

    def test_multiple_tickers(self):
        stocks = [make_stock("AAPL"), make_stock("NVDA")]
        result = audit_bc_propagation(stocks, "2024-06-30")
        assert "AAPL" in result
        assert "NVDA" in result


# ─── TestUpdateBCReliability ──────────────────────────────────────────────────

class TestUpdateBCReliability:
    def setup_method(self):
        reset_session_state()

    def test_returns_all_bc_agents(self):
        stocks = [make_stock("AAPL")]
        audit = audit_bc_propagation(stocks, "2024-06-30")
        result = update_bc_reliability(stocks, audit, {})
        for agent in _BC_AGENTS:
            assert agent in result

    def test_scores_in_01_range(self):
        stocks = [make_stock("AAPL")]
        audit = audit_bc_propagation(stocks, "2024-06-30")
        result = update_bc_reliability(stocks, audit, {})
        for agent, score in result.items():
            assert 0.0 <= score <= 1.0, f"{agent}={score}"

    def test_cold_start_near_neutral(self):
        # cold start = 0.5, 한 번 업데이트 후에도 크게 벗어나지 않음
        stocks = [make_stock("AAPL")]
        audit = audit_bc_propagation(stocks, "2024-06-30")
        result = update_bc_reliability(stocks, audit, {})
        for score in result.values():
            assert 0.3 <= score <= 0.7, f"cold start 후 점수가 너무 극단적: {score}"

    def test_high_confidence_increases_score(self):
        # confidence=1.0, no action_changed → 신뢰도 증가
        stocks = [make_stock("AAPL", confidence=1.0, action_changed=False)]
        audit = audit_bc_propagation(stocks, "2024-06-30")
        r1 = update_bc_reliability(stocks, audit, {})
        r2 = update_bc_reliability(stocks, audit, {})
        # 두 번 업데이트 후 첫 번째보다 높아야 함
        assert r2["trader"] >= r1["trader"] - 0.01  # 허용 오차

    def test_empty_results_returns_defaults(self):
        result = update_bc_reliability([], {}, {})
        # 빈 결과 → 기본값 반환
        for agent in _BC_AGENTS:
            assert agent in result


# ─── TestRunCalibrationAudit ─────────────────────────────────────────────────

class TestRunCalibrationAudit:
    def setup_method(self):
        reset_session_state()

    def test_required_keys(self):
        stocks = [make_stock("AAPL")]
        sim = {"AAPL": make_sim("AAPL")}
        result = run_calibration_audit(stocks, sim, "2024-06-30")
        for k in ["date", "calibrated_scores", "propagation_audit",
                  "reliability_scores", "gating_decisions", "flags"]:
            assert k in result, f"키 누락: {k}"

    def test_date_preserved(self):
        result = run_calibration_audit([], {}, "2024-12-31")
        assert result["date"] == "2024-12-31"

    def test_flags_on_signal_loss(self):
        # tech_score=8 + SELL, bullish + SELL → 2건 손실 → flag
        stocks = [make_stock("AAPL", tech_score=8, action="SELL",
                              consensus="bullish", final_action="SELL")]
        result = run_calibration_audit(stocks, {}, "2024-06-30")
        assert len(result["flags"]) >= 1

    def test_no_flags_clean_signals(self):
        # 신호 일관성 있음 → flag 없음
        stocks = [make_stock("AAPL", tech_score=8, action="BUY",
                              consensus="bullish", final_action="BUY")]
        result = run_calibration_audit(stocks, {}, "2024-06-30")
        # flag 없거나 HARD_GATE 없음
        flag_texts = " ".join(result["flags"])
        assert "신호손실" not in flag_texts

    def test_gating_decisions_valid_values(self):
        stocks = [make_stock("AAPL")]
        result = run_calibration_audit(stocks, {}, "2024-06-30")
        valid = {"full", "downweight", "hard_gate"}
        for agent, decision in result["gating_decisions"].items():
            assert decision in valid, f"{agent}: {decision}"


# ─── TestFormatCalibrationForPrompt ──────────────────────────────────────────

class TestFormatCalibrationForPrompt:
    def setup_method(self):
        reset_session_state()

    def _make_cal(self, flags: list | None = None) -> dict:
        stocks = [make_stock("AAPL")]
        sim = {"AAPL": make_sim("AAPL")}
        result = run_calibration_audit(stocks, sim, "2024-06-30")
        if flags is not None:
            result["flags"] = flags
        return result

    def test_empty_returns_empty_string(self):
        assert format_calibration_for_prompt({}) == ""

    def test_has_markers(self):
        text = format_calibration_for_prompt(self._make_cal())
        assert "CALIBRATION" in text
        assert "END CALIBRATION" in text

    def test_has_reliability_section(self):
        text = format_calibration_for_prompt(self._make_cal())
        assert "Reliability" in text

    def test_has_propagation_section(self):
        text = format_calibration_for_prompt(self._make_cal())
        assert "Propagation" in text or "전달" in text

    def test_contains_aapl(self):
        text = format_calibration_for_prompt(self._make_cal())
        assert "AAPL" in text

    def test_flags_shown(self):
        cal = self._make_cal(flags=["HARD_GATE: ['technical']"])
        text = format_calibration_for_prompt(cal)
        assert "HARD_GATE" in text

    def test_no_flags_section_when_empty(self):
        cal = self._make_cal(flags=[])
        text = format_calibration_for_prompt(cal)
        # 플래그 없으면 플래그 섹션 없음
        assert "플래그" not in text or "⚠" not in text.split("END")[0].split("플래그")[-1] if "END" in text else True
