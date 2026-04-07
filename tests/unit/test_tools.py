"""
tests/unit/test_tools.py
Unit tests for tools/ module:
  - TechnicalAnalyzer (technical.py)
  - RiskAnalyzer      (risk.py)
  - SentimentAnalyzer (sentiment.py)
"""
import math
import pytest
import numpy as np

from tools.technical import TechnicalAnalyzer
from tools.risk import RiskAnalyzer
from tools.sentiment import SentimentAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_prices(start: float = 100.0, step: float = 1.0, n: int = 50) -> list:
    """Monotonically increasing price series."""
    return [start + i * step for i in range(n)]


def _rng_prices(seed: int = 42, n: int = 100) -> list:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0005, 0.012, n)
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices


# ---------------------------------------------------------------------------
# TechnicalAnalyzer
# ---------------------------------------------------------------------------

class TestComputeRSI:

    def setup_method(self):
        self.ta = TechnicalAnalyzer()

    def test_rsi_in_range_0_100(self):
        closes = _rng_prices(seed=0, n=60)
        rsi = self.ta.compute_rsi(closes, period=14)
        assert 0.0 <= rsi <= 100.0

    def test_rsi_returns_float(self):
        closes = _rng_prices(seed=1, n=60)
        rsi = self.ta.compute_rsi(closes, period=14)
        assert isinstance(rsi, float)

    def test_rsi_short_series_returns_50(self):
        """Fewer than period+1 data points → 50.0 fallback."""
        closes = [100.0] * 10
        rsi = self.ta.compute_rsi(closes, period=14)
        assert rsi == 50.0

    def test_rsi_all_up_days_near_100(self):
        """Perfectly rising series → RSI near 100."""
        closes = _linear_prices(n=30)
        rsi = self.ta.compute_rsi(closes, period=14)
        assert rsi >= 90.0

    def test_rsi_all_down_days_near_0(self):
        """Perfectly falling series → RSI near 0."""
        closes = list(reversed(_linear_prices(n=30)))
        rsi = self.ta.compute_rsi(closes, period=14)
        assert rsi <= 10.0


class TestComputeMACD:

    def setup_method(self):
        self.ta = TechnicalAnalyzer()

    def test_macd_returns_required_keys(self):
        closes = _rng_prices(seed=2, n=60)
        result = self.ta.compute_macd(closes)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_values_are_floats(self):
        closes = _rng_prices(seed=3, n=60)
        result = self.ta.compute_macd(closes)
        for k, v in result.items():
            assert isinstance(v, float), f"{k} is not float"

    def test_macd_short_series_returns_zeros(self):
        """Fewer than slow+signal points → all zeros."""
        closes = [100.0] * 10
        result = self.ta.compute_macd(closes)
        assert result == {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def test_macd_histogram_equals_macd_minus_signal(self):
        closes = _rng_prices(seed=4, n=60)
        result = self.ta.compute_macd(closes)
        assert abs(result["histogram"] - (result["macd"] - result["signal"])) < 1e-4


class TestComputeBollingerBands:

    def setup_method(self):
        self.ta = TechnicalAnalyzer()

    def test_bollinger_returns_required_keys(self):
        closes = _rng_prices(seed=5, n=50)
        result = self.ta.compute_bollinger_bands(closes)
        for key in ("upper", "middle", "lower", "bandwidth", "pct_b"):
            assert key in result

    def test_upper_gt_middle_gt_lower(self):
        closes = _rng_prices(seed=6, n=50)
        result = self.ta.compute_bollinger_bands(closes)
        assert result["upper"] > result["middle"] > result["lower"]

    def test_bandwidth_non_negative(self):
        closes = _rng_prices(seed=7, n=50)
        result = self.ta.compute_bollinger_bands(closes)
        assert result["bandwidth"] >= 0.0

    def test_pct_b_in_zero_one(self):
        closes = _rng_prices(seed=8, n=50)
        result = self.ta.compute_bollinger_bands(closes)
        assert 0.0 <= result["pct_b"] <= 1.0

    def test_short_series_returns_equal_bands(self):
        """Fewer than window points → upper == middle == lower."""
        closes = [150.0] * 5
        result = self.ta.compute_bollinger_bands(closes, window=20)
        assert result["upper"] == result["middle"] == result["lower"]


class TestComputeSMA:

    def setup_method(self):
        self.ta = TechnicalAnalyzer()

    def test_sma_returns_float_with_enough_data(self):
        closes = _linear_prices(n=30)
        sma = self.ta.compute_sma(closes, window=20)
        assert isinstance(sma, float)

    def test_sma_correct_value(self):
        closes = list(range(1, 11))  # [1, 2, ..., 10]
        sma = self.ta.compute_sma(closes, window=5)
        assert sma == pytest.approx(8.0)  # mean of [6,7,8,9,10]

    def test_sma_short_series_returns_none(self):
        closes = [100.0] * 5
        sma = self.ta.compute_sma(closes, window=10)
        assert sma is None

    def test_sma_window_equals_length(self):
        closes = [2.0, 4.0, 6.0, 8.0, 10.0]
        sma = self.ta.compute_sma(closes, window=5)
        assert sma == pytest.approx(6.0)


class TestComputeMomentumSignal:

    def setup_method(self):
        self.ta = TechnicalAnalyzer()

    def test_signal_is_one_of_valid_values(self):
        closes = _rng_prices(seed=9, n=60)
        result = self.ta.compute_momentum_signal(closes)
        assert result["signal"] in ("buy", "sell", "hold")

    def test_signal_returns_rsi(self):
        closes = _rng_prices(seed=10, n=60)
        result = self.ta.compute_momentum_signal(closes)
        assert "rsi" in result
        assert 0.0 <= result["rsi"] <= 100.0

    def test_signal_strength_in_zero_one(self):
        closes = _rng_prices(seed=11, n=60)
        result = self.ta.compute_momentum_signal(closes)
        assert 0.0 <= result["strength"] <= 1.0

    def test_oversold_series_may_produce_buy(self):
        """A strongly falling series with a bounce should trigger buy signal."""
        # Start with long downtrend then one bounce day
        closes = list(reversed(_linear_prices(start=150.0, step=1.0, n=40))) + [115.0]
        result = self.ta.compute_momentum_signal(closes)
        # RSI should be low; signal is buy or hold
        assert result["signal"] in ("buy", "hold")


# ---------------------------------------------------------------------------
# RiskAnalyzer
# ---------------------------------------------------------------------------

class TestComputeVaR:

    def setup_method(self):
        self.ra = RiskAnalyzer()

    def test_var_returns_non_negative(self):
        rng = np.random.default_rng(0)
        returns = rng.normal(-0.001, 0.012, 200).tolist()
        var = self.ra.compute_var(returns)
        assert var >= 0.0

    def test_var_returns_float(self):
        returns = list(np.random.default_rng(1).normal(0, 0.01, 100))
        var = self.ra.compute_var(returns)
        assert isinstance(var, float)

    def test_var_short_series_returns_zero(self):
        returns = [0.01] * 5
        var = self.ra.compute_var(returns)
        assert var == 0.0

    def test_var_parametric_method(self):
        rng = np.random.default_rng(2)
        returns = rng.normal(0.0, 0.015, 200).tolist()
        var = self.ra.compute_var(returns, confidence=0.95, method="parametric")
        assert var >= 0.0

    def test_var_higher_confidence_higher_var(self):
        rng = np.random.default_rng(3)
        returns = rng.normal(0.0, 0.015, 300).tolist()
        var95 = self.ra.compute_var(returns, confidence=0.95)
        var99 = self.ra.compute_var(returns, confidence=0.99)
        assert var99 >= var95


class TestComputePortfolioBeta:

    def setup_method(self):
        self.ra = RiskAnalyzer()

    def test_beta_returns_float(self):
        rng = np.random.default_rng(4)
        p = rng.normal(0, 0.01, 50).tolist()
        b = rng.normal(0, 0.01, 50).tolist()
        beta = self.ra.compute_portfolio_beta(p, b)
        assert isinstance(beta, float)

    def test_beta_identical_series_near_one(self):
        rng = np.random.default_rng(5)
        returns = rng.normal(0.001, 0.012, 100).tolist()
        beta = self.ra.compute_portfolio_beta(returns, returns)
        assert abs(beta - 1.0) < 0.01

    def test_beta_short_series_returns_one(self):
        p = [0.01] * 5
        b = [0.01] * 5
        beta = self.ra.compute_portfolio_beta(p, b)
        assert beta == 1.0

    def test_beta_clipped_to_range(self):
        """Beta should never exceed [-5, 5]."""
        rng = np.random.default_rng(6)
        p = rng.normal(0, 0.05, 100).tolist()
        b = rng.normal(0, 0.001, 100).tolist()
        beta = self.ra.compute_portfolio_beta(p, b)
        assert -5.0 <= beta <= 5.0


class TestComputeSectorConcentration:

    def setup_method(self):
        self.ra = RiskAnalyzer()

    def test_concentration_in_zero_one(self):
        weights = {"tech": 0.4, "finance": 0.3, "energy": 0.3}
        c = self.ra.compute_sector_concentration(weights)
        assert 0.0 <= c <= 1.0

    def test_single_sector_returns_valid_float(self):
        """Single sector: min_hhi == 1.0, formula returns 0.0 (degenerate case)."""
        weights = {"tech": 1.0}
        c = self.ra.compute_sector_concentration(weights)
        assert isinstance(c, float)
        assert 0.0 <= c <= 1.0

    def test_uniform_sectors_near_zero(self):
        """Equal-weight sectors → HHI at minimum → concentration near 0."""
        weights = {f"sector_{i}": 1.0 for i in range(10)}
        c = self.ra.compute_sector_concentration(weights)
        assert c < 0.1

    def test_empty_dict_returns_zero(self):
        c = self.ra.compute_sector_concentration({})
        assert c == 0.0

    def test_returns_float(self):
        weights = {"a": 0.5, "b": 0.5}
        c = self.ra.compute_sector_concentration(weights)
        assert isinstance(c, float)


class TestRunStressTest:

    def setup_method(self):
        self.ra = RiskAnalyzer()

    def test_stress_returns_severity_key(self):
        returns = list(np.random.default_rng(7).normal(0, 0.012, 100))
        result = self.ra.run_stress_test(returns)
        assert "severity" in result

    def test_stress_returns_worst_case_key(self):
        returns = list(np.random.default_rng(8).normal(0, 0.012, 100))
        result = self.ra.run_stress_test(returns)
        assert "worst_case_drawdown" in result

    def test_stress_short_series_graceful(self):
        returns = [0.01] * 5
        result = self.ra.run_stress_test(returns)
        assert "severity" in result
        assert "worst_case_drawdown" in result

    def test_stress_severity_in_range(self):
        returns = list(np.random.default_rng(9).normal(0, 0.012, 100))
        result = self.ra.run_stress_test(returns)
        assert 0.0 <= result["severity"] <= 1.0

    def test_stress_worst_case_non_negative(self):
        returns = list(np.random.default_rng(10).normal(0, 0.012, 100))
        result = self.ra.run_stress_test(returns)
        assert result["worst_case_drawdown"] >= 0.0

    def test_stress_custom_scenarios(self):
        returns = list(np.random.default_rng(11).normal(0, 0.012, 100))
        scenarios = {"big_crash": -0.30, "mild_drop": -0.05}
        result = self.ra.run_stress_test(returns, shock_scenarios=scenarios)
        assert "severity" in result
        assert "scenario_losses" in result


# ---------------------------------------------------------------------------
# SentimentAnalyzer
# ---------------------------------------------------------------------------

class TestComputeSentimentScore:

    def setup_method(self):
        self.sa = SentimentAnalyzer()

    def test_score_in_range(self):
        texts = ["strong growth momentum rally", "bullish buy opportunity"]
        score = self.sa.compute_sentiment_score(texts)
        assert -1.0 <= score <= 1.0

    def test_positive_texts_positive_score(self):
        texts = [
            "strong growth rally profit momentum",
            "bullish buy upgrade record revenue",
        ]
        score = self.sa.compute_sentiment_score(texts)
        assert score > 0.0

    def test_negative_texts_negative_score(self):
        texts = [
            "weak decline loss bearish selloff",
            "recession crash crisis downturn default",
        ]
        score = self.sa.compute_sentiment_score(texts)
        assert score < 0.0

    def test_empty_list_returns_zero(self):
        score = self.sa.compute_sentiment_score([])
        assert score == 0.0

    def test_neutral_text_returns_zero(self):
        texts = ["the company filed a report today about operations"]
        score = self.sa.compute_sentiment_score(texts)
        assert score == 0.0

    def test_returns_float(self):
        score = self.sa.compute_sentiment_score(["good growth"])
        assert isinstance(score, float)


class TestComputeMarketUncertainty:

    def setup_method(self):
        self.sa = SentimentAnalyzer()

    def test_uncertainty_in_range(self):
        texts = ["uncertain volatile risk concern"]
        score = self.sa.compute_market_uncertainty(texts)
        assert 0.0 <= score <= 1.0

    def test_empty_list_returns_default(self):
        """Empty list → 0.3 default."""
        score = self.sa.compute_market_uncertainty([])
        assert score == 0.3

    def test_high_uncertainty_words_higher_score(self):
        high = ["uncertain unclear volatile risk concern warning caution doubt fear"]
        low = ["the company reported quarterly earnings"]
        score_high = self.sa.compute_market_uncertainty(high)
        score_low = self.sa.compute_market_uncertainty(low)
        assert score_high > score_low

    def test_returns_float(self):
        score = self.sa.compute_market_uncertainty(["some text"])
        assert isinstance(score, float)


class TestAnalyzeBatch:

    def setup_method(self):
        self.sa = SentimentAnalyzer()

    def test_returns_dict(self):
        result = self.sa.analyze_batch(["growth rally bullish"])
        assert isinstance(result, dict)

    def test_has_sentiment_score_key(self):
        result = self.sa.analyze_batch(["growth rally"])
        assert "sentiment_score" in result

    def test_has_uncertainty_key(self):
        result = self.sa.analyze_batch(["uncertain risk"])
        assert "uncertainty" in result

    def test_has_text_count_key(self):
        texts = ["a", "b", "c"]
        result = self.sa.analyze_batch(texts)
        assert "text_count" in result
        assert result["text_count"] == 3

    def test_empty_batch_text_count_zero(self):
        result = self.sa.analyze_batch([])
        assert result["text_count"] == 0

    def test_batch_sentiment_matches_individual(self):
        texts = ["strong growth profit rally"]
        batch_score = self.sa.analyze_batch(texts)["sentiment_score"]
        individual_score = self.sa.compute_sentiment_score(texts)
        assert batch_score == individual_score
