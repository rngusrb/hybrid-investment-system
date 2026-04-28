"""tests/unit/test_backtester.py — simulation/backtester.py 단위 테스트 (API 호출 없음)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from simulation.backtester import (
    bars_to_returns,
    backtest_all,
    save_sim_result,
    load_sim_history,
    format_sim_for_prompt,
    _adjust_for_r_real,
    _adjust_for_regime,
    _adjust_for_risk_mode,
    STRATEGY_TYPES,
    MIN_BARS,
    REGIME_STRATEGY_PREFERENCE,
)


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_bars(n: int = 60, start_price: float = 100.0, drift: float = 0.001) -> list[dict]:
    """테스트용 OHLCV bars (단조 증가 가격)."""
    import random
    random.seed(42)
    bars = []
    price = start_price
    for i in range(n):
        price *= (1 + drift + random.gauss(0, 0.01))
        bars.append({
            "date":   f"2024-{(i//22)+1:02d}-{(i%22)+1:02d}",
            "open":   round(price * 0.99, 2),
            "high":   round(price * 1.01, 2),
            "low":    round(price * 0.98, 2),
            "close":  round(price, 2),
            "volume": 1_000_000,
        })
    return bars


# ─── bars_to_returns ─────────────────────────────────────────────────────────

class TestBarsToReturns:
    def test_basic_length(self):
        bars = make_bars(10)
        ret = bars_to_returns(bars)
        assert len(ret) == 9  # n-1

    def test_empty_bars(self):
        assert bars_to_returns([]) == []

    def test_single_bar(self):
        assert bars_to_returns([{"close": 100}]) == []

    def test_returns_finite(self):
        import math
        bars = make_bars(50)
        ret = bars_to_returns(bars)
        assert all(math.isfinite(r) for r in ret)

    def test_positive_drift(self):
        # drift=0.002면 대부분 양수 수익률
        bars = make_bars(50, drift=0.002)
        ret = bars_to_returns(bars)
        assert sum(1 for r in ret if r > 0) > len(ret) * 0.5

    def test_uses_close_field(self):
        bars = [{"close": 100}, {"close": 110}]
        ret = bars_to_returns(bars)
        assert abs(ret[0] - 0.1) < 1e-9

    def test_uses_c_field_fallback(self):
        bars = [{"c": 100}, {"c": 120}]
        ret = bars_to_returns(bars)
        assert abs(ret[0] - 0.2) < 1e-9

    def test_zero_price_skipped(self):
        bars = [{"close": 0}, {"close": 100}, {"close": 110}]
        ret = bars_to_returns(bars)
        # close[0]=0 → 첫 return 0.0 (division by zero 방어)
        assert ret[0] == 0.0


# ─── backtest_all ─────────────────────────────────────────────────────────────

class TestBacktestAll:
    def test_returns_required_fields(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        for field in ["ticker", "as_of", "results", "best", "selected_strategy", "data_source"]:
            assert field in result, f"필드 누락: {field}"

    def test_ticker_preserved(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="NVDA", as_of="2024-06-30")
        assert result["ticker"] == "NVDA"

    def test_all_strategies_tested(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        tested = {r["strategy"] for r in result["results"]}
        assert tested == set(STRATEGY_TYPES)

    def test_selected_is_in_results(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        strategies = [r["strategy"] for r in result["results"]]
        assert result["selected_strategy"] in strategies

    def test_best_has_highest_sharpe(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        max_sharpe = max(r["sharpe"] for r in result["results"])
        assert result["best"]["sharpe"] == max_sharpe

    def test_insufficient_bars_returns_defensive(self):
        bars = make_bars(10)   # MIN_BARS=30 미달
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert result["selected_strategy"] == "defensive"
        assert result["data_source"] == "insufficient_data"

    def test_metrics_in_valid_range(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        for r in result["results"]:
            assert -5.0 <= r["sharpe"] <= 10.0, f"sharpe 범위 초과: {r}"
            assert 0.0 <= r["mdd"] <= 0.99,     f"mdd 음수 금지: {r}"
            assert 0.0 <= r["win_rate"] <= 1.0, f"win_rate 범위: {r}"

    def test_data_source_real(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert result["data_source"] == "real"

    def test_results_sorted_by_sharpe_desc(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        sharpes = [r["sharpe"] for r in result["results"]]
        assert sharpes == sorted(sharpes, reverse=True)


# ─── save_sim_result / load_sim_history ──────────────────────────────────────

class TestSimMemory:
    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        sim = {"ticker": "AAPL", "as_of": "2024-01-05",
               "selected_strategy": "momentum", "best": {}, "results": [],
               "data_source": "real"}
        save_sim_result(sim)
        assert (tmp_path / "strategy_memory.json").exists()

    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        sim = {"ticker": "AAPL", "as_of": "2024-01-05",
               "selected_strategy": "momentum", "best": {"sharpe": 1.2},
               "results": [], "data_source": "real"}
        save_sim_result(sim)
        history = load_sim_history("AAPL", "2024-01-12")
        assert len(history) == 1
        assert history[0]["selected_strategy"] == "momentum"

    def test_load_point_in_time_safe(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        # 미래 데이터
        sim_future = {"ticker": "AAPL", "as_of": "2024-02-01",
                      "selected_strategy": "momentum", "best": {}, "results": [],
                      "data_source": "real"}
        save_sim_result(sim_future)
        history = load_sim_history("AAPL", "2024-01-05")
        assert len(history) == 0  # 미래 제외

    def test_load_filters_by_ticker(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        for ticker in ["AAPL", "NVDA"]:
            sim = {"ticker": ticker, "as_of": "2024-01-05",
                   "selected_strategy": "momentum", "best": {}, "results": [],
                   "data_source": "real"}
            save_sim_result(sim)
        history = load_sim_history("AAPL", "2024-01-12")
        assert all(h["ticker"] == "AAPL" for h in history)

    def test_load_sorted_newest_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            save_sim_result({"ticker": "AAPL", "as_of": d, "selected_strategy": "momentum",
                             "best": {}, "results": [], "data_source": "real"})
        history = load_sim_history("AAPL", "2024-01-26", n=3)
        assert history[0]["as_of"] == "2024-01-19"

    def test_overwrite_same_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.RESULTS_DIR", tmp_path)
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        save_sim_result({"ticker": "AAPL", "as_of": "2024-01-05",
                         "selected_strategy": "momentum", "best": {}, "results": [],
                         "data_source": "real"})
        save_sim_result({"ticker": "AAPL", "as_of": "2024-01-05",
                         "selected_strategy": "defensive", "best": {}, "results": [],
                         "data_source": "real"})
        history = load_sim_history("AAPL", "2024-01-12")
        assert history[0]["selected_strategy"] == "defensive"


# ─── format_sim_for_prompt ───────────────────────────────────────────────────

class TestFormatSimForPrompt:
    def _make_sim(self, ticker: str, strategy: str = "momentum", sharpe: float = 1.2) -> dict:
        best = {"strategy": strategy, "return": 0.05, "sharpe": sharpe,
                "sortino": 1.5, "mdd": 0.08, "win_rate": 0.55,
                "turnover": 0.3, "n_bars": 60, "data_source": "real"}
        return {
            "ticker": ticker, "as_of": "2024-06-30",
            "results": [best], "best": best,
            "selected_strategy": strategy, "data_source": "real",
        }

    def test_empty_returns_empty_string(self):
        assert format_sim_for_prompt({}) == ""

    def test_contains_ticker(self):
        text = format_sim_for_prompt({"AAPL": self._make_sim("AAPL")})
        assert "AAPL" in text

    def test_contains_strategy(self):
        text = format_sim_for_prompt({"AAPL": self._make_sim("AAPL", strategy="momentum")})
        assert "momentum" in text

    def test_contains_sharpe(self):
        text = format_sim_for_prompt({"AAPL": self._make_sim("AAPL", sharpe=1.23)})
        assert "1.23" in text

    def test_has_markers(self):
        text = format_sim_for_prompt({"AAPL": self._make_sim("AAPL")})
        assert "BOB SIMULATION" in text
        assert "END BOB SIMULATION" in text

    def test_insufficient_data_note(self):
        sim = {"ticker": "AAPL", "as_of": "2024-01-05", "results": [],
               "best": {"n_bars": 5, "strategy": "defensive"}, "data_source": "insufficient_data",
               "selected_strategy": "defensive", "note": "bars 부족 (5개 < 30)"}
        text = format_sim_for_prompt({"AAPL": sim})
        assert "부족" in text

    def test_multiple_tickers(self):
        sims = {
            "AAPL": self._make_sim("AAPL", "momentum"),
            "NVDA": self._make_sim("NVDA", "directional"),
        }
        text = format_sim_for_prompt(sims)
        assert "AAPL" in text and "NVDA" in text


# ─── TestAdjustForRReal ───────────────────────────────────────────────────────

class TestAdjustForRReal:
    """_adjust_for_r_real 단위 테스트 (strategy_memory mock 사용)."""

    def _make_ranked(self, strategies_sharpes: list[tuple]) -> list[dict]:
        """[(strategy, sharpe), ...] → ranked list."""
        return [
            {"strategy": s, "sharpe": sh, "mdd": 0.05, "return": 0.01,
             "win_rate": 0.55, "turnover": 0.2, "n_bars": 60}
            for s, sh in strategies_sharpes
        ]

    def test_no_history_no_adjustment(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        ranked = self._make_ranked([("momentum", 1.2), ("defensive", 0.8)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is False
        assert result[0]["strategy"] == "momentum"  # 순서 그대로

    def test_positive_r_real_bonus_applied(self, tmp_path, monkeypatch):
        """r_real >= 0.02: 이전 선택 전략 sharpe +10%."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        # 이전 기록: momentum 선택, r_real=+5%
        save_sim_result({
            "ticker": "AAPL", "as_of": "2024-06-20",
            "selected_strategy": "momentum",
            "r_real": 0.05,
            "best": {}, "results": [], "data_source": "real",
        })
        ranked = self._make_ranked([("momentum", 1.0), ("defensive", 0.95)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is True
        momentum_entry = next(r for r in result if r["strategy"] == "momentum")
        assert momentum_entry["sharpe"] == pytest.approx(1.0 * 1.10, rel=1e-4)

    def test_negative_r_real_penalty_applied(self, tmp_path, monkeypatch):
        """r_real < 0: 이전 선택 전략 sharpe -15%."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        save_sim_result({
            "ticker": "AAPL", "as_of": "2024-06-20",
            "selected_strategy": "momentum",
            "r_real": -0.03,
            "best": {}, "results": [], "data_source": "real",
        })
        ranked = self._make_ranked([("momentum", 1.2), ("defensive", 1.1)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is True
        momentum_entry = next(r for r in result if r["strategy"] == "momentum")
        assert momentum_entry["sharpe"] == pytest.approx(1.2 * 0.85, rel=1e-4)

    def test_negative_penalty_can_change_winner(self, tmp_path, monkeypatch):
        """패널티로 2위 전략이 1위로 올라올 수 있음."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        save_sim_result({
            "ticker": "AAPL", "as_of": "2024-06-20",
            "selected_strategy": "momentum",
            "r_real": -0.04,
            "best": {}, "results": [], "data_source": "real",
        })
        # momentum 1.0, defensive 0.9 → 패널티 후 momentum=0.85 < defensive=0.9
        ranked = self._make_ranked([("momentum", 1.0), ("defensive", 0.9)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is True
        assert result[0]["strategy"] == "defensive"  # 역전

    def test_neutral_r_real_no_adjustment(self, tmp_path, monkeypatch):
        """0 <= r_real < 0.02: 조정 없음."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        save_sim_result({
            "ticker": "AAPL", "as_of": "2024-06-20",
            "selected_strategy": "momentum",
            "r_real": 0.01,
            "best": {}, "results": [], "data_source": "real",
        })
        ranked = self._make_ranked([("momentum", 1.2), ("defensive", 0.8)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is False

    def test_no_r_real_in_history_no_adjustment(self, tmp_path, monkeypatch):
        """이전 기록에 r_real 없으면 조정 없음 (T+7 미경과)."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        save_sim_result({
            "ticker": "AAPL", "as_of": "2024-06-20",
            "selected_strategy": "momentum",
            # r_real 없음
            "best": {}, "results": [], "data_source": "real",
        })
        ranked = self._make_ranked([("momentum", 1.2), ("defensive", 0.8)])
        result, adjusted = _adjust_for_r_real(ranked, "AAPL", "2024-06-30")
        assert adjusted is False


class TestBacktestAllRRealAdjusted:
    """backtest_all에 r_real_adjusted 필드 추가 검증."""

    def test_r_real_adjusted_field_present(self):
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert "r_real_adjusted" in result

    def test_r_real_adjusted_false_without_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert result["r_real_adjusted"] is False


# ─── _adjust_for_regime 테스트 (TASK-006) ───────────────────────────────────

def make_ranked(strategies: list[str], base_sharpe: float = 1.0) -> list[dict]:
    """테스트용 ranked 전략 목록."""
    return [
        {"strategy": s, "sharpe": base_sharpe, "mdd": 0.1,
         "return": 0.1, "win_rate": 0.5, "data_source": "real"}
        for s in strategies
    ]


class TestAdjustForRegime:
    def test_risk_on_boosts_momentum(self):
        ranked = make_ranked(["momentum", "defensive", "mean_reversion"])
        emily = {"market_regime": "risk_on", "reversal_risk": 0.2}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is True
        momentum_row = next(r for r in result if r["strategy"] == "momentum")
        assert momentum_row["sharpe"] > 1.0

    def test_risk_off_boosts_defensive(self):
        ranked = make_ranked(["defensive", "momentum", "directional"])
        emily = {"market_regime": "risk_off", "reversal_risk": 0.2}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is True
        defensive_row = next(r for r in result if r["strategy"] == "defensive")
        assert defensive_row["sharpe"] > 1.0

    def test_mixed_regime_no_adjustment(self):
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "mixed", "reversal_risk": 0.2}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is False
        # sharpe 값 변경 없음
        for r in result:
            assert r["sharpe"] == 1.0

    def test_reversal_risk_above_06_boosts_defensive(self):
        ranked = make_ranked(["momentum", "defensive", "mean_reversion"])
        emily = {"market_regime": "mixed", "reversal_risk": 0.75}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is True
        defensive_row = next(r for r in result if r["strategy"] == "defensive")
        assert defensive_row["sharpe"] > 1.0

    def test_reversal_risk_below_06_no_extra_boost(self):
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "mixed", "reversal_risk": 0.4}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is False

    def test_result_reranked_after_adjustment(self):
        """risk_off에서 defensive가 momentum보다 높은 Sharpe를 갖도록 재정렬."""
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "risk_off", "reversal_risk": 0.2}
        result, _ = _adjust_for_regime(ranked, emily)
        # defensive가 1.15 보너스, momentum은 1.0 → defensive가 1등
        assert result[0]["strategy"] == "defensive"

    def test_factor_bounded_max_20pct(self):
        """Sharpe 보정이 최대 20% 이내."""
        ranked = make_ranked(["defensive"])
        emily = {"market_regime": "risk_off", "reversal_risk": 0.9}
        result, _ = _adjust_for_regime(ranked, emily)
        defensive = next(r for r in result if r["strategy"] == "defensive")
        assert defensive["sharpe"] <= 1.0 * 1.20 + 1e-6

    def test_unknown_regime_no_adjustment(self):
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "unknown_regime", "reversal_risk": 0.1}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is False

    def test_missing_reversal_risk_graceful(self):
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "risk_on"}
        result, adjusted = _adjust_for_regime(ranked, emily)
        # risk_on prefs가 있으므로 adjusted=True
        assert adjusted is True

    def test_technical_signal_state_nested_reversal_risk(self):
        """emily_output 전체 구조에서 technical_signal_state.reversal_risk 읽기."""
        ranked = make_ranked(["momentum", "defensive"])
        emily = {
            "market_regime": "mixed",
            "technical_signal_state": {"reversal_risk": 0.8},
        }
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is True  # reversal_risk > 0.6 → defensive boost

    def test_transition_regime_no_adjustment(self):
        ranked = make_ranked(["momentum", "defensive"])
        emily = {"market_regime": "transition", "reversal_risk": 0.2}
        result, adjusted = _adjust_for_regime(ranked, emily)
        assert adjusted is False

    def test_backtest_all_no_emily_backward_compat(self, tmp_path, monkeypatch):
        """emily_context=None이면 기존 동작과 완전히 동일."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert result["regime_adjusted"] is False
        assert "selected_strategy" in result

    def test_backtest_all_with_emily_context(self, tmp_path, monkeypatch):
        """emily_context 전달 시 regime_adjusted 필드 존재."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        bars = make_bars(60)
        emily = {"market_regime": "risk_off", "reversal_risk": 0.3}
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30", emily_context=emily)
        assert "regime_adjusted" in result
        assert result["regime_adjusted"] is True


# ─── TestAdjustForRiskMode ────────────────────────────────────────────────────

class TestAdjustForRiskMode:
    def test_defensive_penalizes_momentum(self):
        ranked = make_ranked(["momentum", "defensive", "directional"])
        result, adjusted = _adjust_for_risk_mode(ranked, "defensive")
        assert adjusted is True
        momentum_row = next(r for r in result if r["strategy"] == "momentum")
        assert momentum_row["sharpe"] == pytest.approx(1.0 * 0.80, abs=1e-4)

    def test_defensive_penalizes_directional(self):
        ranked = make_ranked(["momentum", "directional", "defensive"])
        result, adjusted = _adjust_for_risk_mode(ranked, "defensive")
        directional_row = next(r for r in result if r["strategy"] == "directional")
        assert directional_row["sharpe"] == pytest.approx(1.0 * 0.85, abs=1e-4)

    def test_defensive_does_not_change_other_strategies(self):
        ranked = make_ranked(["defensive", "mean_reversion", "hedged"])
        result, _ = _adjust_for_risk_mode(ranked, "defensive")
        for r in result:
            if r["strategy"] not in ("momentum", "directional"):
                assert r["sharpe"] == pytest.approx(1.0, abs=1e-4)

    def test_defensive_reranks_result(self):
        """defensive 모드에서 momentum이 패널티 받아 defensive가 1등으로 올라옴."""
        ranked = make_ranked(["momentum", "defensive"])
        result, _ = _adjust_for_risk_mode(ranked, "defensive")
        # momentum(0.80) < defensive(1.0) → defensive가 1등
        assert result[0]["strategy"] == "defensive"

    def test_normal_mode_no_adjustment(self):
        ranked = make_ranked(["momentum", "directional", "defensive"])
        result, adjusted = _adjust_for_risk_mode(ranked, "normal")
        assert adjusted is False
        for r in result:
            assert r["sharpe"] == pytest.approx(1.0, abs=1e-4)

    def test_unknown_risk_mode_no_adjustment(self):
        ranked = make_ranked(["momentum", "defensive"])
        result, adjusted = _adjust_for_risk_mode(ranked, "unknown_mode")
        assert adjusted is False

    def test_backtest_all_defensive_mode(self, tmp_path, monkeypatch):
        """backtest_all(risk_mode='defensive') 시 risk_mode_adjusted 필드 반환."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30", risk_mode="defensive")
        assert result["risk_mode_adjusted"] is True
        assert result["risk_mode"] == "defensive"

    def test_backtest_all_normal_mode_default(self, tmp_path, monkeypatch):
        """risk_mode 기본값 'normal' → risk_mode_adjusted=False."""
        monkeypatch.setattr("simulation.backtester.STRATEGY_MEM_PATH",
                            tmp_path / "strategy_memory.json")
        bars = make_bars(60)
        result = backtest_all(bars, ticker="AAPL", as_of="2024-06-30")
        assert result["risk_mode_adjusted"] is False
        assert result["risk_mode"] == "normal"
