"""Strategy Memory — strategy templates, sim outcomes, approval reasons 저장/조회."""
from typing import Optional, List, Dict
from memory.base_memory import BaseMemory


class StrategyMemory(BaseMemory):
    def __init__(self):
        self._store: Dict[str, dict] = {}  # key → record

    def store(self, key: str, value: dict, date: str, tags=None):
        self._store[key] = {"key": key, "value": value, "date": date, "tags": tags or []}

    def retrieve(self, query: dict, as_of: str, top_k: int = 5) -> List[dict]:
        """as_of 이전 데이터만 최신순으로 반환."""
        valid = [r for r in self._store.values() if self._enforce_point_in_time(r["date"], as_of)]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]

    def get_by_date(self, date: str) -> Optional[dict]:
        """특정 날짜의 가장 최근 record 반환."""
        matches = [r for r in self._store.values() if r.get("date") == date]
        return matches[-1] if matches else None

    def get_approved_strategies(self, as_of: str, top_k: int = 5) -> List[dict]:
        """approved 태그가 있는 전략만 필터링."""
        valid = [
            r for r in self._store.values()
            if self._enforce_point_in_time(r["date"], as_of)
            and "approved" in r.get("tags", [])
        ]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]

    def get_sim_outcomes(self, as_of: str, top_k: int = 5) -> List[dict]:
        """sim_outcome 태그가 있는 기록만 필터링."""
        valid = [
            r for r in self._store.values()
            if self._enforce_point_in_time(r["date"], as_of)
            and "sim_outcome" in r.get("tags", [])
        ]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]
