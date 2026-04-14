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
    STRATEGY_TYPES,
    MIN_BARS,
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
