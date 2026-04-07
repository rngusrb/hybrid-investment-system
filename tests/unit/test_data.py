"""
tests/unit/test_data.py - Unit tests for Phase 4: Data Layer.

All tests run without real Polygon API calls (client=None or mocked).
"""

import math
import pytest
import pandas as pd
import numpy as np

from data.missing_protocol import (
    DataQualityReport,
    MissingFlag,
    MissingReason,
)
from data.polygon_fetcher import PolygonFetcher
from data.data_manager import DataManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AS_OF = "2024-01-15"
FROM_DATE = "2024-01-01"
TO_DATE = "2024-01-15"
FUTURE_TO_DATE = "2024-12-31"


def _make_bars(n: int = 10, nan_col: str = None) -> list:
    """Generate n simple OHLCV bars."""
    bars = []
    for i in range(n):
        date_str = f"2024-01-{i+1:02d}"
        close = 100.0 + i
        bar = {
            "date": date_str,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        }
        if nan_col and i == 5:
            bar[nan_col] = float("nan")
        bars.append(bar)
    return bars


# ---------------------------------------------------------------------------
# 1. MissingFlag 생성 및 필드 확인
# ---------------------------------------------------------------------------

class TestMissingFlag:
    def test_create_basic(self):
        flag = MissingFlag(
            field_name="close",
            reason=MissingReason.NAN_VALUE,
            original_value=None,
            staleness_days=None,
            description="test",
        )
        assert flag.field_name == "close"
        assert flag.reason == MissingReason.NAN_VALUE
        assert flag.description == "test"

    def test_defaults(self):
        flag = MissingFlag(field_name="open", reason=MissingReason.API_FAILURE)
        assert flag.original_value is None
        assert flag.staleness_days is None
        assert flag.description == ""


# ---------------------------------------------------------------------------
# 2. DataQualityReport.add_missing() 후 confidence_shrinkage 증가 확인
# ---------------------------------------------------------------------------

class TestDataQualityReport:
    def test_add_missing_increases_shrinkage(self):
        report = DataQualityReport(as_of_date=AS_OF)
        assert report.confidence_shrinkage == 0.0

        report.add_missing(MissingFlag(field_name="close", reason=MissingReason.NAN_VALUE))
        assert report.confidence_shrinkage > 0.0

    # 3. adjusted_confidence가 shrinkage에 반비례
    def test_adjusted_confidence_inverse(self):
        report = DataQualityReport(as_of_date=AS_OF)
        assert report.adjusted_confidence == 1.0  # no shrinkage

        report.add_missing(MissingFlag(field_name="close", reason=MissingReason.NAN_VALUE))
        assert report.adjusted_confidence < 1.0
        assert report.adjusted_confidence == pytest.approx(1.0 - report.confidence_shrinkage, abs=1e-9)

    # 4. FUTURE_DATE_BLOCKED → shrinkage >= 0.5
    def test_future_date_blocked_shrinkage(self):
        report = DataQualityReport(as_of_date=AS_OF)
        report.add_missing(
            MissingFlag(field_name="to_date", reason=MissingReason.FUTURE_DATE_BLOCKED)
        )
        assert report.confidence_shrinkage >= 0.5

    # 5. 여러 missing flag 누적 → shrinkage max 0.9
    def test_shrinkage_capped_at_0_9(self):
        report = DataQualityReport(as_of_date=AS_OF)
        for _ in range(20):
            report.add_missing(
                MissingFlag(field_name="x", reason=MissingReason.API_FAILURE)
            )
        assert report.confidence_shrinkage <= 0.9
        assert report.confidence_shrinkage == pytest.approx(0.9)

    def test_adjusted_confidence_floor(self):
        report = DataQualityReport(as_of_date=AS_OF)
        for _ in range(20):
            report.add_missing(
                MissingFlag(field_name="x", reason=MissingReason.FUTURE_DATE_BLOCKED)
            )
        assert report.adjusted_confidence >= 0.1


# ---------------------------------------------------------------------------
# 6. PolygonFetcher._enforce_point_in_time()
# ---------------------------------------------------------------------------

class TestPolygonFetcherPointInTime:
    def setup_method(self):
        self.fetcher = PolygonFetcher(api_key=None)

    def test_future_date_returns_false(self):
        result = self.fetcher._enforce_point_in_time("2025-01-01", "2024-01-15")
        assert result is False

    def test_past_date_returns_true(self):
        result = self.fetcher._enforce_point_in_time("2024-01-01", "2024-01-15")
        assert result is True

    def test_same_date_returns_true(self):
        result = self.fetcher._enforce_point_in_time("2024-01-15", "2024-01-15")
        assert result is True


# ---------------------------------------------------------------------------
# 7. get_ohlcv() — client None → API_FAILURE flag + 빈 data
# ---------------------------------------------------------------------------

class TestPolygonFetcherOHLCV:
    def setup_method(self):
        self.fetcher = PolygonFetcher(api_key=None)

    def test_no_client_api_failure_flag(self):
        result = self.fetcher.get_ohlcv(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=TO_DATE,
            as_of=AS_OF,
        )
        assert result["data"] == []
        reasons = [f.reason for f in result["quality"].missing_flags]
        assert MissingReason.API_FAILURE in reasons

    # 9. to_date > as_of → FUTURE_DATE_BLOCKED flag
    def test_future_to_date_flagged(self):
        result = self.fetcher.get_ohlcv(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=FUTURE_TO_DATE,
            as_of=AS_OF,
        )
        reasons = [f.reason for f in result["quality"].missing_flags]
        assert MissingReason.FUTURE_DATE_BLOCKED in reasons

    def test_future_to_date_and_api_failure(self):
        """When client is None and to_date is future, both flags present."""
        result = self.fetcher.get_ohlcv(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=FUTURE_TO_DATE,
            as_of=AS_OF,
        )
        reasons = [f.reason for f in result["quality"].missing_flags]
        assert MissingReason.FUTURE_DATE_BLOCKED in reasons
        assert MissingReason.API_FAILURE in reasons


# ---------------------------------------------------------------------------
# 8. get_news() — client None → no_news_label="No material news"
# ---------------------------------------------------------------------------

class TestPolygonFetcherNews:
    def setup_method(self):
        self.fetcher = PolygonFetcher(api_key=None)

    def test_no_client_no_news_label(self):
        result = self.fetcher.get_news(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=TO_DATE,
            as_of=AS_OF,
        )
        assert result["articles"] == []
        assert result["no_news_label"] == "No material news"

    def test_no_client_api_failure_flag(self):
        result = self.fetcher.get_news(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=TO_DATE,
            as_of=AS_OF,
        )
        reasons = [f.reason for f in result["quality"].missing_flags]
        assert MissingReason.API_FAILURE in reasons

    # 10. to_date > as_of → cap 처리
    def test_future_to_date_capped(self):
        result = self.fetcher.get_news(
            ticker="AAPL",
            from_date=FROM_DATE,
            to_date=FUTURE_TO_DATE,
            as_of=AS_OF,
        )
        reasons = [f.reason for f in result["quality"].missing_flags]
        assert MissingReason.FUTURE_DATE_BLOCKED in reasons
        # no_news_label still present because client is None
        assert result["no_news_label"] == "No material news"


# ---------------------------------------------------------------------------
# DataManager tests
# ---------------------------------------------------------------------------

class TestDataManagerPreprocess:
    def setup_method(self):
        self.dm = DataManager()

    # 11. 빈 data → INSUFFICIENT_HISTORY flag
    def test_empty_data_insufficient_history(self):
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv([], quality=quality)
        assert df.empty
        reasons = [f.reason for f in quality.missing_flags]
        assert MissingReason.INSUFFICIENT_HISTORY in reasons

    # 12. NaN 포함 data → NAN_VALUE flag
    def test_nan_data_flag(self):
        bars = _make_bars(n=10, nan_col="close")
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv(bars, quality=quality)
        reasons = [f.reason for f in quality.missing_flags]
        assert MissingReason.NAN_VALUE in reasons
        # NaN should have been forward-filled — no NaN remaining
        assert not df["close"].isna().any()


class TestDataManagerReturns:
    def setup_method(self):
        self.dm = DataManager()

    # 13. compute_returns() → return, log_return 컬럼
    def test_compute_returns_columns(self):
        bars = _make_bars(n=10)
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv(bars, quality=quality)
        df = self.dm.compute_returns(df)
        assert "return" in df.columns
        assert "log_return" in df.columns

    def test_compute_returns_values(self):
        bars = _make_bars(n=5)
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv(bars, quality=quality)
        df = self.dm.compute_returns(df)
        # first row should be NaN (no prior close)
        assert pd.isna(df["return"].iloc[0])
        # second row: (101 - 100) / 100 = 0.01
        assert df["return"].iloc[1] == pytest.approx(0.01, abs=1e-9)


class TestDataManagerVol:
    def setup_method(self):
        self.dm = DataManager()

    # 14. compute_realized_vol() → realized_vol 컬럼
    def test_realized_vol_column(self):
        bars = _make_bars(n=30)
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv(bars, quality=quality)
        df = self.dm.compute_returns(df)
        df = self.dm.compute_realized_vol(df, window=10)
        assert "realized_vol" in df.columns
        assert not df["realized_vol"].isna().all()

    def test_realized_vol_non_negative(self):
        bars = _make_bars(n=30)
        quality = DataQualityReport(as_of_date=AS_OF)
        df = self.dm.preprocess_ohlcv(bars, quality=quality)
        df = self.dm.compute_returns(df)
        df = self.dm.compute_realized_vol(df, window=10)
        assert (df["realized_vol"].dropna() >= 0).all()


class TestDataManagerSector:
    def setup_method(self):
        self.dm = DataManager()

    # 15. 알려진 ticker → 올바른 sector
    def test_known_ticker_aapl(self):
        assert self.dm.get_sector("AAPL") == "technology"

    def test_known_ticker_msft(self):
        assert self.dm.get_sector("MSFT") == "technology"

    def test_known_ticker_amzn(self):
        assert self.dm.get_sector("AMZN") == "consumer_discretionary"

    # 16. 알 수 없는 ticker → "unknown"
    def test_unknown_ticker(self):
        assert self.dm.get_sector("ZZZZ") == "unknown"

    def test_case_insensitive(self):
        assert self.dm.get_sector("aapl") == "technology"


class TestDataManagerNormalize:
    def setup_method(self):
        self.dm = DataManager()

    # 17. minmax → [0, 1] 범위
    def test_minmax_range(self):
        scores = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}
        result = self.dm.normalize_scores(scores, method="minmax")
        assert min(result.values()) == pytest.approx(0.0)
        assert max(result.values()) == pytest.approx(1.0)
        for v in result.values():
            assert 0.0 <= v <= 1.0

    # 18. 동일 값 → 모두 0.5
    def test_minmax_all_same(self):
        scores = {"A": 5.0, "B": 5.0, "C": 5.0}
        result = self.dm.normalize_scores(scores, method="minmax")
        for v in result.values():
            assert v == pytest.approx(0.5)

    def test_zscore_normalization(self):
        scores = {"A": 1.0, "B": 2.0, "C": 3.0}
        result = self.dm.normalize_scores(scores, method="zscore")
        values = list(result.values())
        assert pytest.approx(np.mean(values), abs=1e-9) == 0.0

    def test_empty_scores(self):
        result = self.dm.normalize_scores({}, method="minmax")
        assert result == {}


class TestDataManagerFreshness:
    def setup_method(self):
        self.dm = DataManager()

    def _make_df_with_latest(self, latest_date: str, n: int = 5) -> pd.DataFrame:
        """Make a DataFrame whose last date is latest_date."""
        from datetime import datetime, timedelta
        base = datetime.strptime(latest_date, "%Y-%m-%d")
        rows = []
        for i in range(n):
            d = base - timedelta(days=n - 1 - i)
            rows.append({
                "date": pd.Timestamp(d),
                "close": 100.0 + i,
            })
        return pd.DataFrame(rows)

    # 19. stale data 감지 + quality report 업데이트
    def test_stale_data_detected(self):
        # Latest bar is 10 days before as_of
        df = self._make_df_with_latest("2024-01-05")
        quality = DataQualityReport(as_of_date=AS_OF)
        result = self.dm.check_freshness(df, as_of=AS_OF, max_staleness_days=5, quality=quality)
        assert result is False
        assert quality.is_stale is True
        reasons = [f.reason for f in quality.missing_flags]
        assert MissingReason.STALE_DATA in reasons

    # 20. 신선한 data → True 반환
    def test_fresh_data_returns_true(self):
        # Latest bar is same as as_of → staleness = 0
        df = self._make_df_with_latest(AS_OF)
        quality = DataQualityReport(as_of_date=AS_OF)
        result = self.dm.check_freshness(df, as_of=AS_OF, max_staleness_days=5, quality=quality)
        assert result is True
        assert quality.is_stale is False

    def test_empty_df_returns_false(self):
        df = pd.DataFrame(columns=["date", "close"])
        result = self.dm.check_freshness(df, as_of=AS_OF)
        assert result is False

    def test_freshness_boundary(self):
        # Exactly at boundary (staleness == max_staleness_days) → True
        df = self._make_df_with_latest("2024-01-10")  # 5 days before 2024-01-15
        result = self.dm.check_freshness(df, as_of=AS_OF, max_staleness_days=5)
        assert result is True
