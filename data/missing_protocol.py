"""
data.missing_protocol - Missing data handling protocol.
Defines MissingFlag and DataQualityReport for tracking data gaps,
with confidence shrinkage that propagates to upstream agents.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class MissingReason(Enum):
    NAN_VALUE = "nan_value"
    STALE_DATA = "stale_data"
    NO_NEWS = "no_news"
    API_FAILURE = "api_failure"
    FUTURE_DATE_BLOCKED = "future_date_blocked"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass
class MissingFlag:
    field_name: str
    reason: MissingReason
    original_value: Optional[float] = None
    staleness_days: Optional[int] = None
    description: str = ""


@dataclass
class DataQualityReport:
    as_of_date: str
    ticker: Optional[str] = None
    missing_flags: List[MissingFlag] = field(default_factory=list)
    confidence_shrinkage: float = 0.0
    has_no_news: bool = False
    no_news_label: str = "No material news"
    is_stale: bool = False
    freshness_days: Optional[int] = None

    def add_missing(self, flag: MissingFlag):
        self.missing_flags.append(flag)
        self._recalculate_shrinkage()

    def _recalculate_shrinkage(self):
        weights = {
            MissingReason.NAN_VALUE: 0.05,
            MissingReason.STALE_DATA: 0.10,
            MissingReason.NO_NEWS: 0.02,
            MissingReason.API_FAILURE: 0.15,
            MissingReason.FUTURE_DATE_BLOCKED: 0.50,
            MissingReason.INSUFFICIENT_HISTORY: 0.08,
        }
        total = sum(weights.get(f.reason, 0.05) for f in self.missing_flags)
        self.confidence_shrinkage = min(total, 0.9)

    @property
    def adjusted_confidence(self) -> float:
        return max(0.1, 1.0 - self.confidence_shrinkage)
