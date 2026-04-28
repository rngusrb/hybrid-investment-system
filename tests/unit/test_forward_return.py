"""
tests/unit/test_forward_return.py
TASK-011: 증시 휴장일 T0 fallback — fetch_forward_return T0 공휴일 처리 검증.
"""
import pytest
from unittest.mock import MagicMock


def _make_fetcher(t0_bars, t1_bars, fallback_bars=None):
    """Mock fetcher — t0/t1/fallback 순서대로 반환."""
    fetcher = MagicMock()
    call_results = []
    if fallback_bars is not None:
        # t0 returns empty, fallback returns fallback_bars, t1 returns t1_bars
        call_results = [
            {"data": t0_bars},
            {"data": fallback_bars},
            {"data": t1_bars},
        ]
    else:
        call_results = [
            {"data": t0_bars},
            {"data": t1_bars},
        ]
    fetcher.get_ohlcv.side_effect = call_results
    return fetcher


class TestFetchForwardReturn:
    """fetch_forward_return 기본 동작 검증."""

    def test_normal_t0_t1_returns_float(self):
        """T0/T1 모두 데이터 있을 때 수익률 float 반환."""
        from utils.forward_return import fetch_forward_return

        fetcher = _make_fetcher(
            t0_bars=[{"date": "2024-01-15", "close": 100.0}],
            t1_bars=[{"date": "2024-01-16", "close": 102.0}],
        )
        r = fetch_forward_return(fetcher, "SPY", "2024-01-15")
        assert r is not None
        assert abs(r - 0.02) < 1e-6

    def test_t1_missing_returns_none(self):
        """T+1 데이터 없으면 None 반환."""
        from utils.forward_return import fetch_forward_return

        fetcher = _make_fetcher(
            t0_bars=[{"date": "2024-01-15", "close": 100.0}],
            t1_bars=[],
        )
        r = fetch_forward_return(fetcher, "SPY", "2024-01-15")
        assert r is None

    def test_fetcher_none_returns_none(self):
        """fetcher=None이면 즉시 None."""
        from utils.forward_return import fetch_forward_return

        r = fetch_forward_return(None, "SPY", "2024-01-15")
        assert r is None


class TestT0HolidayFallback:
    """TASK-011: T0 공휴일 fallback 검증."""

    def test_t0_empty_uses_previous_close(self):
        """T0 bars 없으면 fallback fetch → 이전 거래일 close로 수익률 계산."""
        from utils.forward_return import fetch_forward_return

        # T0 empty (공휴일), fallback has previous day close=200, T1 has 202
        fetcher = _make_fetcher(
            t0_bars=[],
            t1_bars=[{"date": "2024-04-01", "close": 202.0}],
            fallback_bars=[
                {"date": "2024-03-28", "close": 200.0},
            ],
        )
        r = fetch_forward_return(fetcher, "SPY", "2024-03-29")
        assert r is not None
        assert abs(r - 0.01) < 1e-6  # (202 - 200) / 200 = 0.01

    def test_t0_empty_no_fallback_returns_none(self):
        """T0 empty + fallback도 empty → None 반환."""
        from utils.forward_return import fetch_forward_return

        fetcher = _make_fetcher(
            t0_bars=[],
            t1_bars=[{"date": "2024-04-01", "close": 202.0}],
            fallback_bars=[],
        )
        r = fetch_forward_return(fetcher, "SPY", "2024-03-29")
        assert r is None

    def test_t0_empty_fallback_exception_returns_none(self):
        """T0 empty + fallback fetch 예외 → None (Silent Failure)."""
        from utils.forward_return import fetch_forward_return

        fetcher = MagicMock()
        # First call (t0) returns empty, second call (fallback) raises
        fetcher.get_ohlcv.side_effect = [
            {"data": []},
            Exception("network error"),
        ]
        r = fetch_forward_return(fetcher, "SPY", "2024-03-29")
        assert r is None

    def test_t0_normal_does_not_trigger_fallback(self):
        """T0 정상 데이터 있을 때 fallback 호출 안 함 (get_ohlcv 2번만)."""
        from utils.forward_return import fetch_forward_return

        fetcher = _make_fetcher(
            t0_bars=[{"date": "2024-01-15", "close": 100.0}],
            t1_bars=[{"date": "2024-01-16", "close": 101.0}],
        )
        fetch_forward_return(fetcher, "SPY", "2024-01-15")
        assert fetcher.get_ohlcv.call_count == 2  # t0 + t1, no fallback
