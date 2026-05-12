"""tests/unit/test_run_eval.py — E-006 평가 파이프라인 테스트"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from evaluation.baselines import (
    compute_macd_signal,
    compute_sma_signal,
    compute_baseline_returns,
)
from scripts.run_eval import (
    extract_aapl_price,
    extract_aapl_bars,
    compute_metrics_for,
    load_portfolio_results,
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────

def _make_bars(n: int, start_price: float = 100.0, trend: float = 0.01) -> list[dict]:
    """n개 bars 생성 (단조 증가/감소)."""
    bars = []
    price = start_price
    for i in range(n):
        bars.append({"close": round(price, 2), "open": price, "high": price, "low": price})
        price *= (1 + trend)
    return bars


def _make_portfolio_data(
    date: str,
    r_real: float | None,
    aapl_price: float = 180.0,
    n_bars: int = 30,
) -> dict:
    return {
        "date": date,
        "r_real": r_real,
        "stock_results": [
            {
                "ticker": "AAPL",
                "current_price": aapl_price,
                "bars": _make_bars(n_bars),
            }
        ],
    }


# ── compute_macd_signal ────────────────────────────────────────────────────

class TestComputeMacdSignal:
    def test_returns_0_or_1(self):
        bars = _make_bars(50, trend=0.005)
        result = compute_macd_signal(bars)
        assert result in (0, 1)

    def test_insufficient_bars_returns_1(self):
        bars = _make_bars(10)
        assert compute_macd_signal(bars) == 1

    def test_exactly_26_bars(self):
        bars = _make_bars(26)
        assert compute_macd_signal(bars) in (0, 1)

    def test_uptrend_tends_to_long(self):
        """강한 상승 트렌드 → MACD > Signal → 1."""
        bars = _make_bars(60, start_price=100.0, trend=0.02)
        result = compute_macd_signal(bars)
        assert result == 1

    def test_downtrend_returns_valid(self):
        """하락 트렌드에서도 0 또는 1 반환 (MACD는 가속도 지표라 방향 단정 불가)."""
        bars = _make_bars(60, start_price=200.0, trend=-0.02)
        assert compute_macd_signal(bars) in (0, 1)

    def test_empty_bars_returns_1(self):
        assert compute_macd_signal([]) == 1

    def test_missing_close_skipped(self):
        """close 없는 bar는 무시."""
        bars = [{"open": 100}] * 5 + _make_bars(30)
        result = compute_macd_signal(bars)
        assert result in (0, 1)


# ── compute_sma_signal ─────────────────────────────────────────────────────

class TestComputeSmaSignal:
    def test_returns_0_or_1(self):
        bars = _make_bars(30)
        result = compute_sma_signal(bars)
        assert result in (0, 1)

    def test_insufficient_bars_returns_1(self):
        bars = _make_bars(10)
        assert compute_sma_signal(bars, period=20) == 1

    def test_price_above_sma_returns_1(self):
        """현재가가 SMA보다 높으면 1."""
        bars = _make_bars(30, start_price=100.0, trend=0.05)  # 강한 상승
        assert compute_sma_signal(bars) == 1

    def test_price_below_sma_returns_0(self):
        """현재가가 SMA보다 낮으면 0."""
        bars = _make_bars(30, start_price=200.0, trend=-0.05)  # 강한 하락
        assert compute_sma_signal(bars) == 0

    def test_custom_period(self):
        bars = _make_bars(50)
        result = compute_sma_signal(bars, period=10)
        assert result in (0, 1)

    def test_empty_bars_returns_1(self):
        assert compute_sma_signal([]) == 1

    def test_exactly_period_bars(self):
        """정확히 period개 bars → 기본값 1 (< period 조건 미충족 = 충족 → 계산)."""
        bars = _make_bars(20, trend=0.01)
        result = compute_sma_signal(bars, period=20)
        assert result in (0, 1)


# ── compute_baseline_returns ───────────────────────────────────────────────

class TestComputeBaselineReturns:
    def _run(self, n: int = 5) -> dict:
        dates  = [f"2024-01-{i:02d}" for i in range(1, n + 1)]
        prices = [100.0 + i for i in range(n)]
        bars   = {d: _make_bars(30) for d in dates}
        return compute_baseline_returns(dates, prices, bars)

    def test_returns_three_keys(self):
        result = self._run()
        assert set(result.keys()) == {"buy_and_hold", "macd", "sma"}

    def test_length_is_n_minus_1(self):
        n = 6
        result = self._run(n)
        assert len(result["buy_and_hold"]) == n - 1
        assert len(result["macd"])          == n - 1
        assert len(result["sma"])           == n - 1

    def test_bnh_positive_for_rising_prices(self):
        dates  = ["2024-01-01", "2024-01-02", "2024-01-03"]
        prices = [100.0, 110.0, 120.0]
        bars   = {d: _make_bars(30) for d in dates}
        result = compute_baseline_returns(dates, prices, bars)
        assert all(r > 0 for r in result["buy_and_hold"])

    def test_bnh_negative_for_falling_prices(self):
        dates  = ["2024-01-01", "2024-01-02"]
        prices = [100.0, 90.0]
        bars   = {d: _make_bars(30) for d in dates}
        result = compute_baseline_returns(dates, prices, bars)
        assert result["buy_and_hold"][0] < 0

    def test_macd_flat_position_returns_zero(self):
        """MACD signal=0으로 강제 → 해당 기간 수익 = 0."""
        dates  = ["2024-01-01", "2024-01-02"]
        prices = [100.0, 120.0]
        bars   = {"2024-01-01": _make_bars(60)}
        with patch("evaluation.baselines.compute_macd_signal", return_value=0):
            result = compute_baseline_returns(dates, prices, bars)
        assert result["macd"][0] == 0.0

    def test_sma_long_position_matches_bnh(self):
        """SMA signal=1 → 해당 기간 수익 = BnH 수익."""
        dates  = ["2024-01-01", "2024-01-02"]
        prices = [100.0, 110.0]
        # 강한 상승 bars → SMA signal = 1
        bars   = {"2024-01-01": _make_bars(30, trend=0.05)}
        result = compute_baseline_returns(dates, prices, bars)
        assert abs(result["sma"][0] - result["buy_and_hold"][0]) < 1e-9

    def test_missing_price_returns_zero(self):
        dates  = ["2024-01-01", "2024-01-02"]
        prices = [None, 110.0]
        bars   = {d: [] for d in dates}
        result = compute_baseline_returns(dates, prices, bars)
        assert result["buy_and_hold"][0] == 0.0

    def test_single_date_returns_empty(self):
        result = compute_baseline_returns(["2024-01-01"], [100.0], {})
        assert result["buy_and_hold"] == []

    def test_missing_bars_date_falls_back_to_default(self):
        """bars_by_date에 없는 날짜 → 빈 bars → 기본값 1 (long)."""
        dates  = ["2024-01-01", "2024-01-02"]
        prices = [100.0, 95.0]
        bars   = {}  # bars 없음
        result = compute_baseline_returns(dates, prices, bars)
        # 기본값 long → BnH return 그대로
        assert result["macd"][0] == pytest.approx(result["buy_and_hold"][0])


# ── extract_aapl_price / bars ──────────────────────────────────────────────

class TestExtractAaplData:
    def test_extract_price_found(self):
        data = _make_portfolio_data("2024-01-05", 0.05, aapl_price=182.5)
        assert extract_aapl_price(data) == 182.5

    def test_extract_price_no_aapl(self):
        data = {"stock_results": [{"ticker": "NVDA", "current_price": 600.0, "bars": []}]}
        assert extract_aapl_price(data) is None

    def test_extract_price_missing_key(self):
        assert extract_aapl_price({}) is None

    def test_extract_bars_found(self):
        bars = _make_bars(10)
        data = {"stock_results": [{"ticker": "AAPL", "current_price": 180.0, "bars": bars}]}
        assert extract_aapl_bars(data) == bars

    def test_extract_bars_no_aapl(self):
        data = {"stock_results": [{"ticker": "NVDA", "bars": []}]}
        assert extract_aapl_bars(data) == []


# ── compute_metrics_for ────────────────────────────────────────────────────

class TestComputeMetricsFor:
    def test_returns_required_keys(self):
        returns = [0.01, 0.02, -0.01, 0.03]
        result = compute_metrics_for(returns, "Test", periods_per_year=52)
        for key in ("label", "n_periods", "cumulative_return", "annualized_return",
                    "sharpe_ratio", "max_drawdown"):
            assert key in result

    def test_label_preserved(self):
        result = compute_metrics_for([0.01], "My Label")
        assert result["label"] == "My Label"

    def test_n_periods_correct(self):
        returns = [0.01, 0.02, 0.03]
        result = compute_metrics_for(returns, "X")
        assert result["n_periods"] == 3

    def test_empty_returns(self):
        result = compute_metrics_for([], "X")
        assert result["n_periods"] == 0

    def test_all_positive_mdd_zero_or_small(self):
        """단조 증가 수익률 → MDD 거의 0."""
        returns = [0.01] * 10
        result = compute_metrics_for(returns, "X")
        assert result["max_drawdown"] < 0.01

    def test_positive_returns_positive_cr(self):
        returns = [0.02, 0.03, 0.01]
        result = compute_metrics_for(returns, "X")
        assert result["cumulative_return"] > 0


# ── load_portfolio_results (파일시스템 mock) ──────────────────────────────

class TestLoadPortfolioResults:
    def test_filters_none_r_real(self, tmp_path):
        (tmp_path / "2024-01-05").mkdir()
        (tmp_path / "2024-01-05" / "portfolio.json").write_text(
            json.dumps({"date": "2024-01-05", "r_real": None})
        )
        (tmp_path / "2024-01-12").mkdir()
        (tmp_path / "2024-01-12" / "portfolio.json").write_text(
            json.dumps({"date": "2024-01-12", "r_real": 0.03})
        )
        with patch("scripts.run_eval.RESULTS_DIR", tmp_path):
            results = load_portfolio_results()
        assert len(results) == 1
        assert results[0]["date"] == "2024-01-12"

    def test_date_filter_start(self, tmp_path):
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            (tmp_path / d).mkdir()
            (tmp_path / d / "portfolio.json").write_text(
                json.dumps({"date": d, "r_real": 0.01})
            )
        with patch("scripts.run_eval.RESULTS_DIR", tmp_path):
            results = load_portfolio_results(start="2024-01-12")
        assert all(r["date"] >= "2024-01-12" for r in results)

    def test_date_filter_end(self, tmp_path):
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            (tmp_path / d).mkdir()
            (tmp_path / d / "portfolio.json").write_text(
                json.dumps({"date": d, "r_real": 0.01})
            )
        with patch("scripts.run_eval.RESULTS_DIR", tmp_path):
            results = load_portfolio_results(end="2024-01-12")
        assert all(r["date"] <= "2024-01-12" for r in results)

    def test_empty_dir(self, tmp_path):
        with patch("scripts.run_eval.RESULTS_DIR", tmp_path):
            results = load_portfolio_results()
        assert results == []
