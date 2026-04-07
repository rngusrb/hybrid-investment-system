"""
data.data_manager - Central data preprocessing and normalization manager.
Coordinates OHLCV preprocessing, return computation, realized volatility,
sector mapping, score normalization, and freshness checking.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import numpy as np

from data.missing_protocol import DataQualityReport, MissingFlag, MissingReason


# GICS-based sector mapping for major tickers
SECTOR_MAP: Dict[str, str] = {
    # Technology
    "AAPL": "technology",
    "MSFT": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "INTC": "technology",
    "ORCL": "technology",
    "CRM": "technology",
    "ADBE": "technology",
    # Communication Services
    "GOOGL": "communication_services",
    "GOOG": "communication_services",
    "META": "communication_services",
    "NFLX": "communication_services",
    # Consumer Discretionary
    "AMZN": "consumer_discretionary",
    "TSLA": "consumer_discretionary",
    "NKE": "consumer_discretionary",
    # Financials
    "JPM": "financials",
    "BAC": "financials",
    "GS": "financials",
    "MS": "financials",
    # Healthcare
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
}


def _parse_date(date_str: str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class DataManager:
    """Coordinates data preprocessing, normalization, and enrichment."""

    def __init__(self, fetcher: Any = None, cache_dir: str = ".cache") -> None:
        self.fetcher = fetcher
        self.cache_dir = cache_dir

    # ------------------------------------------------------------------
    # OHLCV preprocessing
    # ------------------------------------------------------------------

    def preprocess_ohlcv(
        self,
        raw_data: List[Dict[str, Any]],
        quality: Optional[DataQualityReport] = None,
    ) -> pd.DataFrame:
        """Convert raw OHLCV bar list to a cleaned DataFrame.

        - Empty input → INSUFFICIENT_HISTORY flag added to quality.
        - NaN values → forward-filled; NAN_VALUE flag added per affected column.

        Returns a DataFrame with columns: date, open, high, low, close, volume.
        """
        if quality is None:
            quality = DataQualityReport(as_of_date="unknown")

        if not raw_data:
            quality.add_missing(
                MissingFlag(
                    field_name="ohlcv",
                    reason=MissingReason.INSUFFICIENT_HISTORY,
                    description="No OHLCV bars provided; insufficient history",
                )
            )
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume"]
            )

        df = pd.DataFrame(raw_data)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

        numeric_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]

        # Detect NaN before ffill and flag
        for col in numeric_cols:
            nan_mask = df[col].isna() | df[col].apply(
                lambda v: math.isnan(float(v)) if v is not None else True
            )
            if nan_mask.any():
                quality.add_missing(
                    MissingFlag(
                        field_name=col,
                        reason=MissingReason.NAN_VALUE,
                        description=f"NaN values found in column '{col}'; forward-filled",
                    )
                )

        # Forward-fill NaN
        df[numeric_cols] = df[numeric_cols].ffill()

        return df

    # ------------------------------------------------------------------
    # Returns
    # ------------------------------------------------------------------

    def compute_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 'return' (simple daily return) and 'log_return' columns to df."""
        df = df.copy()
        if "close" not in df.columns or df.empty:
            df["return"] = pd.Series(dtype=float)
            df["log_return"] = pd.Series(dtype=float)
            return df

        df["return"] = df["close"].pct_change()
        df["log_return"] = np.log(df["close"] / df["close"].shift(1))
        return df

    # ------------------------------------------------------------------
    # Realized volatility
    # ------------------------------------------------------------------

    def compute_realized_vol(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """Add 'realized_vol' column: rolling std of log_return * sqrt(252)."""
        df = df.copy()
        if "log_return" not in df.columns:
            df = self.compute_returns(df)

        df["realized_vol"] = (
            df["log_return"].rolling(window=window, min_periods=1).std()
            * math.sqrt(252)
        )
        return df

    # ------------------------------------------------------------------
    # Sector mapping
    # ------------------------------------------------------------------

    def get_sector(self, ticker: str) -> str:
        """Return GICS sector for ticker, or 'unknown' if not in map."""
        return SECTOR_MAP.get(ticker.upper(), "unknown")

    # ------------------------------------------------------------------
    # Score normalization
    # ------------------------------------------------------------------

    def normalize_scores(
        self,
        scores: Dict[str, float],
        method: str = "minmax",
    ) -> Dict[str, float]:
        """Normalize a dict of {key: score} values.

        method='minmax': scale to [0, 1]; if all values are identical → 0.5.
        method='zscore': standardize to zero mean / unit std; if std=0 → 0.0.
        """
        if not scores:
            return {}

        keys = list(scores.keys())
        values = np.array([scores[k] for k in keys], dtype=float)

        if method == "minmax":
            v_min, v_max = values.min(), values.max()
            if v_max == v_min:
                normalized = np.full_like(values, 0.5)
            else:
                normalized = (values - v_min) / (v_max - v_min)
        elif method == "zscore":
            mean = values.mean()
            std = values.std()
            if std == 0:
                normalized = np.zeros_like(values)
            else:
                normalized = (values - mean) / std
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        return {k: float(v) for k, v in zip(keys, normalized)}

    # ------------------------------------------------------------------
    # Freshness check
    # ------------------------------------------------------------------

    def check_freshness(
        self,
        df: pd.DataFrame,
        as_of: str,
        max_staleness_days: int = 5,
        quality: Optional[DataQualityReport] = None,
    ) -> bool:
        """Return True if latest data in df is within max_staleness_days of as_of.

        If stale, adds STALE_DATA flag to quality report and sets is_stale=True.
        Returns False when df is empty or data is too old.
        """
        if df.empty or "date" not in df.columns:
            return False

        as_of_date = _parse_date(as_of)

        # Get latest date in df
        latest_series = df["date"].dropna()
        if latest_series.empty:
            return False

        latest_val = latest_series.max()
        if hasattr(latest_val, "date"):
            latest_date = latest_val.date()
        else:
            latest_date = _parse_date(str(latest_val)[:10])

        staleness = (as_of_date - latest_date).days

        if quality is not None:
            quality.freshness_days = staleness

        if staleness > max_staleness_days:
            if quality is not None:
                quality.is_stale = True
                quality.add_missing(
                    MissingFlag(
                        field_name="ohlcv",
                        reason=MissingReason.STALE_DATA,
                        staleness_days=staleness,
                        description=(
                            f"Latest data is {staleness} days before as_of {as_of}; "
                            f"exceeds max_staleness_days={max_staleness_days}"
                        ),
                    )
                )
            return False

        return True
