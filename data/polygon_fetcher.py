"""
data.polygon_fetcher - Polygon.io market data fetcher.
Retrieves OHLCV and news data via the polygon-api-client.
Enforces point-in-time constraint via as_of parameter to prevent lookahead bias.
"""

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from data.missing_protocol import DataQualityReport, MissingFlag, MissingReason


def _parse_date(date_str: str) -> date:
    """Parse ISO date string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class PolygonFetcher:
    """Market data fetcher backed by Polygon.io REST API.

    All public methods accept an ``as_of`` parameter that enforces point-in-time
    safety: any requested date range extending beyond ``as_of`` is capped and
    flagged with FUTURE_DATE_BLOCKED.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize fetcher.  If api_key is None the client stays None and
        every call returns empty data with API_FAILURE flags."""
        self._client = None
        if api_key:
            try:
                from polygon import RESTClient  # type: ignore
                self._client = RESTClient(api_key)
            except Exception:
                self._client = None

    # ------------------------------------------------------------------
    # Point-in-time enforcement
    # ------------------------------------------------------------------

    def _enforce_point_in_time(self, date_str: str, as_of: str) -> bool:
        """Return True if date_str is on or before as_of, else False."""
        try:
            target = _parse_date(date_str)
            cutoff = _parse_date(as_of)
            return target <= cutoff
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    def get_ohlcv(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        as_of: str,
        timespan: str = "day",
    ) -> Dict[str, Any]:
        """Fetch OHLCV bars for *ticker* between *from_date* and *to_date*,
        capped at *as_of*.

        Returns a dict with keys:
            "data"    – list of bar dicts (may be empty)
            "quality" – DataQualityReport
        """
        quality = DataQualityReport(as_of_date=as_of, ticker=ticker)

        # Cap to_date at as_of and flag future request
        effective_to = to_date
        if not self._enforce_point_in_time(to_date, as_of):
            effective_to = as_of
            quality.add_missing(
                MissingFlag(
                    field_name="to_date",
                    reason=MissingReason.FUTURE_DATE_BLOCKED,
                    description=f"Requested to_date {to_date} is after as_of {as_of}; capped to {as_of}",
                )
            )

        # No client → API failure
        if self._client is None:
            quality.add_missing(
                MissingFlag(
                    field_name="ohlcv",
                    reason=MissingReason.API_FAILURE,
                    description="Polygon client is not initialized (no API key)",
                )
            )
            return {"data": [], "quality": quality}

        # Fetch from Polygon
        try:
            aggs = list(
                self._client.list_aggs(
                    ticker=ticker,
                    multiplier=1,
                    timespan=timespan,
                    from_=from_date,
                    to=effective_to,
                    adjusted=True,
                    sort="asc",
                    limit=50000,
                )
            )
        except Exception as exc:
            quality.add_missing(
                MissingFlag(
                    field_name="ohlcv",
                    reason=MissingReason.API_FAILURE,
                    description=str(exc),
                )
            )
            return {"data": [], "quality": quality}

        bars: List[Dict[str, Any]] = []
        for agg in aggs:
            bar = {
                "date": datetime.utcfromtimestamp(agg.timestamp / 1000).strftime(
                    "%Y-%m-%d"
                )
                if agg.timestamp
                else None,
                "open": agg.open,
                "high": agg.high,
                "low": agg.low,
                "close": agg.close,
                "volume": agg.volume,
                "vwap": agg.vwap,
            }
            # Check for NaN values
            for col, val in bar.items():
                if col == "date":
                    continue
                if val is not None and math.isnan(float(val)):
                    quality.add_missing(
                        MissingFlag(
                            field_name=col,
                            reason=MissingReason.NAN_VALUE,
                            description=f"NaN detected in column '{col}' for bar on {bar.get('date')}",
                        )
                    )
            bars.append(bar)

        # Staleness check: latest bar vs as_of
        if bars:
            latest_date_str = bars[-1].get("date")
            if latest_date_str:
                latest = _parse_date(latest_date_str)
                cutoff = _parse_date(as_of)
                staleness = (cutoff - latest).days
                quality.freshness_days = staleness
                if staleness >= 5:
                    quality.is_stale = True
                    quality.add_missing(
                        MissingFlag(
                            field_name="ohlcv",
                            reason=MissingReason.STALE_DATA,
                            staleness_days=staleness,
                            description=f"Latest bar is {staleness} days before as_of {as_of}",
                        )
                    )

        return {"data": bars, "quality": quality}

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    def get_news(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        as_of: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Fetch news articles for *ticker* between *from_date* and *to_date*,
        capped at *as_of*.

        Returns a dict with keys:
            "articles"      – list of article dicts (may be empty)
            "quality"       – DataQualityReport
            "no_news_label" – "No material news" when articles is empty
        """
        quality = DataQualityReport(as_of_date=as_of, ticker=ticker)

        # Cap to_date at as_of
        effective_to = to_date
        if not self._enforce_point_in_time(to_date, as_of):
            effective_to = as_of
            quality.add_missing(
                MissingFlag(
                    field_name="to_date",
                    reason=MissingReason.FUTURE_DATE_BLOCKED,
                    description=f"Requested to_date {to_date} is after as_of {as_of}; capped to {as_of}",
                )
            )

        # No client → API failure; still return no_news_label
        if self._client is None:
            quality.add_missing(
                MissingFlag(
                    field_name="news",
                    reason=MissingReason.API_FAILURE,
                    description="Polygon client is not initialized (no API key)",
                )
            )
            quality.has_no_news = True
            return {
                "articles": [],
                "quality": quality,
                "no_news_label": quality.no_news_label,
            }

        # Fetch from Polygon
        try:
            raw_news = list(
                self._client.list_ticker_news(
                    ticker=ticker,
                    published_utc_gte=from_date,
                    published_utc_lte=effective_to,
                    limit=limit,
                )
            )
        except Exception as exc:
            quality.add_missing(
                MissingFlag(
                    field_name="news",
                    reason=MissingReason.API_FAILURE,
                    description=str(exc),
                )
            )
            quality.has_no_news = True
            return {
                "articles": [],
                "quality": quality,
                "no_news_label": quality.no_news_label,
            }

        articles = [
            {
                "id": getattr(item, "id", None),
                "published_utc": getattr(item, "published_utc", None),
                "title": getattr(item, "title", None),
                "description": getattr(item, "description", None),
                "article_url": getattr(item, "article_url", None),
                "publisher": {
                    "name": getattr(getattr(item, "publisher", None), "name", ""),
                },
            }
            for item in raw_news
        ]

        if not articles:
            quality.has_no_news = True
            quality.add_missing(
                MissingFlag(
                    field_name="news",
                    reason=MissingReason.NO_NEWS,
                    description="No news articles found for the requested period",
                )
            )
            return {
                "articles": [],
                "quality": quality,
                "no_news_label": quality.no_news_label,
            }

        return {
            "articles": articles,
            "quality": quality,
            "no_news_label": None,
        }
