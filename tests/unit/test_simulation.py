"""
tests/unit/test_simulation.py
Unit tests for simulation/ module:
  - SyntheticDataProvider
  - StrategyExecutor
  - SimulatedTradingEngine
"""
import math
import pytest

from simulation.synthetic_provider import SyntheticDataProvider
from simulation.strategy_executor import StrategyExecutor
from simulation.trading_engine import SimulatedTradingEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_STRATEGY_TYPES = [
    "momentum",
    "mean_reversion",
    "directional",
    "hedged",
    "market_neutral",
    "defensive",
]


def _make_dates(n: int, start: str = "2024-01-02") -> list:
    """Generate n weekday date strings starting from start."""
    from datetime import datetime, timedelta
    dates = []
    cur = datetime.strptime(start, "%Y-%m-%d")
    while len(dates) < n:
        if cur.weekday() < 5:
            dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# SyntheticDataProvider
# ---------------------------------------------------------------------------

class TestSyntheticDataProvider:

    def setup_method(self):
        self.provider = SyntheticDataProvider()

    def test_returns_correct_length(self):
        dates = _make_dates(50)
        returns = self.provider.get_returns(dates, "momentum", 0.7, 0.6)
        assert len(returns) == 50

    def test_returns_single_date(self):
        dates = _make_dates(1)
        returns = self.provider.get_returns(dates, "momentum", 0.5, 0.5)
        assert len(returns) == 1

    def test_same_seed_reproducible(self):
        dates = _make_dates(100)
        r1 = self.provider.get_returns(dates, "momentum", 0.7, 0.6)
        r2 = self.provider.get_returns(dates, "momentum", 0.7, 0.6)
        assert r1 == r2

    def test_different_strategy_different_results(self):
        dates = _make_dates(100)
        r_mom = self.provider.get_returns(dates, "momentum", 0.7, 0.6)
        r_def = self.provider.get_returns(dates, "defensive", 0.7, 0.6)
        assert r_mom != r_def

    def test_all_strategy_types_no_error(self):
        dates = _make_dates(60)
        for stype in ALL_STRATEGY_TYPES:
            result = self.provider.get_returns(dates, stype, 0.5, 0.5)
            assert isinstance(result, list)
            assert len(result) == 60

    def test_returns_are_floats(self):
        dates = _make_dates(30)
        returns = self.provider.get_returns(dates, "momentum", 0.5, 0.5)
        assert all(isinstance(r, float) for r in returns)

    def test_higher_quality_higher_drift(self):
        """Higher regime_fit + technical_alignment should yield higher mean returns."""
        dates = _make_dates(252)
        r_high = self.provider.get_returns(dates, "momentum", 1.0, 1.0)
        r_low = self.provider.get_returns(dates, "momentum", 0.0, 0.0)
        # With enough samples, higher quality should have higher mean
        import statistics
        mean_high = statistics.mean(r_high)
        mean_low = statistics.mean(r_low)
        # High quality drift = 0.0008, low = 0.0 — high should dominate on avg
        assert mean_high > mean_low

    def test_momentum_higher_vol_than_defensive(self):
        """Momentum vol_multiplier=1.2 vs defensive=0.4 — momentum should be more volatile."""
        import statistics
        dates = _make_dates(252)
        r_mom = self.provider.get_returns(dates, "momentum", 0.5, 0.5)
        r_def = self.provider.get_returns(dates, "defensive", 0.5, 0.5)
        assert statistics.stdev(r_mom) > statistics.stdev(r_def)

    def test_empty_dates_list_handled(self):
        """Empty dates list → returns empty list (no crash)."""
        provider = SyntheticDataProvider()
        result = provider.get_returns([], "momentum", 0.5, 0.5)
        assert result == []

    def test_unknown_strategy_type_does_not_crash(self):
        dates = _make_dates(30)
        result = self.provider.get_returns(dates, "unknown_type", 0.5, 0.5)
        assert isinstance(result, list)
        assert len(result) == 30


# ---------------------------------------------------------------------------
# StrategyExecutor
# ---------------------------------------------------------------------------

class TestStrategyExecutorComputePositions:

    def setup_method(self):
        self.executor = StrategyExecutor()
        self.provider = SyntheticDataProvider()
        self.dates = _make_dates(100)

    def _get_returns(self, stype="momentum"):
        return self.provider.get_returns(self.dates, stype, 0.5, 0.5)

    def test_positions_same_length_as_returns(self):
        returns = self._get_returns()
        positions = self.executor.compute_positions(returns, "momentum")
        assert len(positions) == len(returns)

    def test_all_strategy_types_return_correct_length(self):
        returns = self._get_returns()
        for stype in ALL_STRATEGY_TYPES:
            pos = self.executor.compute_positions(returns, stype)
            assert len(pos) == len(returns), f"Failed for {stype}"

    def test_first_lookback_positions_zero(self):
        returns = self._get_returns()
        positions = self.executor.compute_positions(returns, "momentum", lookback=20)
        assert all(p == 0.0 for p in positions[:20])

    def test_positions_within_valid_range(self):
        returns = self._get_returns()
        for stype in ALL_STRATEGY_TYPES:
            pos = self.executor.compute_positions(returns, stype)
            assert all(-1.0 <= p <= 1.0 for p in pos), f"Out of range for {stype}"

    def test_short_series_returns_all_zeros(self):
        """Series shorter than lookback → all zeros."""
        short_returns = [0.01] * 15
        positions = self.executor.compute_positions(short_returns, "momentum", lookback=20)
        assert all(p == 0.0 for p in positions)

    def test_short_series_equal_to_lookback_returns_zeros(self):
        """Series exactly equal to lookback → all zeros."""
        returns = [0.01] * 20
        positions = self.executor.compute_positions(returns, "momentum", lookback=20)
        assert all(p == 0.0 for p in positions)

    def test_unknown_strategy_fallback_to_momentum(self):
        """Unknown strategy type falls back to momentum — should not crash."""
        returns = self._get_returns()
        pos = self.executor.compute_positions(returns, "xyz_unknown")
        assert len(pos) == len(returns)

    def test_defensive_positions_constant(self):
        """Defensive strategy always returns 0.15."""
        returns = self._get_returns("defensive")
        pos = self.executor.compute_positions(returns, "defensive")
        assert all(p == 0.15 for p in pos)

    def test_market_neutral_positions_minimal(self):
        """Market-neutral positions after lookback should be 0.1."""
        returns = self._get_returns("market_neutral")
        pos = self.executor.compute_positions(returns, "market_neutral", lookback=20)
        assert all(p == 0.1 for p in pos[20:])


class TestStrategyExecutorComputeStrategyReturns:

    def setup_method(self):
        self.executor = StrategyExecutor()

    def test_returns_tuple(self):
        raw = [0.01, -0.02, 0.015, -0.005, 0.02]
        positions = [1.0, 1.0, -0.5, 0.0, 1.0]
        result = self.executor.compute_strategy_returns(raw, positions)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_strat_returns_length(self):
        raw = [0.01] * 50
        positions = [1.0] * 50
        strat_rets, _ = self.executor.compute_strategy_returns(raw, positions)
        assert len(strat_rets) == len(raw) - 1

    def test_turnover_non_negative(self):
        raw = [0.01] * 50
        positions = [1.0 if i % 3 == 0 else -0.5 for i in range(50)]
        _, turnover = self.executor.compute_strategy_returns(raw, positions)
        assert turnover >= 0.0

    def test_turnover_is_float(self):
        raw = [0.01] * 30
        positions = [0.5] * 30
        _, turnover = self.executor.compute_strategy_returns(raw, positions)
        assert isinstance(turnover, float)

    def test_zero_positions_zero_returns(self):
        raw = [0.01, 0.02, 0.03, -0.01]
        positions = [0.0, 0.0, 0.0, 0.0]
        strat_rets, turnover = self.executor.compute_strategy_returns(raw, positions)
        assert all(r == 0.0 for r in strat_rets)
        assert turnover == 0.0

    def test_strategy_return_calculation(self):
        """strat_return[t] = position[t-1] * raw_return[t]"""
        raw = [0.0, 0.10, 0.20]
        positions = [1.0, 0.5, 0.0]
        strat_rets, _ = self.executor.compute_strategy_returns(raw, positions)
        # strat_rets[0] = positions[0] * raw[1] = 1.0 * 0.10 = 0.10
        assert abs(strat_rets[0] - 0.10) < 1e-9
        # strat_rets[1] = positions[1] * raw[2] = 0.5 * 0.20 = 0.10
        assert abs(strat_rets[1] - 0.10) < 1e-9


# ---------------------------------------------------------------------------
# SimulatedTradingEngine
# ---------------------------------------------------------------------------

VALID_SIM_WINDOW = {"train_start": "2023-01-02", "train_end": "2024-01-01"}
EXPECTED_KEYS = {"sharpe", "sortino", "mdd", "turnover", "hit_rate", "return", "data_source"}


class TestSimulatedTradingEngine:

    def setup_method(self):
        self.engine = SimulatedTradingEngine(fetcher=None)

    def test_run_strategy_returns_dict(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert isinstance(result, dict)

    def test_run_strategy_has_expected_keys(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        assert set(result.keys()) == EXPECTED_KEYS

    def test_all_strategy_types_return_valid_dict(self):
        for stype in ALL_STRATEGY_TYPES:
            result = self.engine.run_strategy(stype, VALID_SIM_WINDOW)
            assert result is not None, f"Got None for {stype}"
            assert set(result.keys()) == EXPECTED_KEYS

    def test_all_values_are_finite(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        for k, v in result.items():
            if isinstance(v, str):
                continue  # data_source 등 문자열 필드 skip
            assert math.isfinite(v), f"{k}={v} is not finite"

    def test_mdd_non_negative(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        assert result["mdd"] >= 0.0

    def test_mdd_at_most_one(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        assert result["mdd"] <= 1.0

    def test_hit_rate_in_zero_one(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        assert 0.0 <= result["hit_rate"] <= 1.0

    def test_turnover_non_negative(self):
        result = self.engine.run_strategy("momentum", VALID_SIM_WINDOW)
        assert result is not None
        assert result["turnover"] >= 0.0

    def test_missing_train_start_returns_none(self):
        result = self.engine.run_strategy("momentum", {"train_end": "2024-01-01"})
        assert result is None

    def test_missing_train_end_returns_none(self):
        result = self.engine.run_strategy("momentum", {"train_start": "2023-01-02"})
        assert result is None

    def test_empty_sim_window_returns_none(self):
        result = self.engine.run_strategy("momentum", {})
        assert result is None

    def test_very_short_window_returns_none(self):
        """Window shorter than 30 days should return None."""
        result = self.engine.run_strategy(
            "momentum",
            {"train_start": "2024-01-02", "train_end": "2024-01-15"},
        )
        assert result is None

    def test_unknown_strategy_type_returns_dict(self):
        """Unknown strategy type should fall back and still return a valid dict."""
        result = self.engine.run_strategy("unknown_type", VALID_SIM_WINDOW)
        assert result is not None
        assert set(result.keys()) == EXPECTED_KEYS

    def test_high_quality_params(self):
        result = self.engine.run_strategy(
            "momentum", VALID_SIM_WINDOW, regime_fit=1.0, technical_alignment=1.0
        )
        assert result is not None
        assert math.isfinite(result["sharpe"])

    def test_low_quality_params(self):
        result = self.engine.run_strategy(
            "defensive", VALID_SIM_WINDOW, regime_fit=0.0, technical_alignment=0.0
        )
        assert result is not None
        assert math.isfinite(result["return"])
