"""Decision Journal — policy decisions, actual outcomes, override history 저장/조회."""
from typing import Optional, List, Dict
from memory.base_memory import BaseMemory


class DecisionJournal(BaseMemory):
    def __init__(self):
        self._store: Dict[str, dict] = {}  # date → record

    def store(self, key: str, value: dict, date: str, tags=None):
        self._store[date] = {"key": key, "value": value, "date": date, "tags": tags or []}

    def retrieve(self, query: dict, as_of: str, top_k: int = 5) -> List[dict]:
        """as_of 이전 데이터만 최신순으로 반환."""
        valid = [r for r in self._store.values() if self._enforce_point_in_time(r["date"], as_of)]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]

    def get_by_date(self, date: str) -> Optional[dict]:
        return self._store.get(date)

    def get_overrides(self, as_of: str, top_k: int = 5) -> List[dict]:
        """override 태그가 있는 결정만 필터링."""
        valid = [
            r for r in self._store.values()
            if self._enforce_point_in_time(r["date"], as_of)
            and "override" in r.get("tags", [])
        ]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]

    def get_policy_decisions(self, as_of: str, top_k: int = 10) -> List[dict]:
        """policy_decision 태그가 있는 기록만 필터링."""
        valid = [
            r for r in self._store.values()
            if self._enforce_point_in_time(r["date"], as_of)
            and "policy_decision" in r.get("tags", [])
        ]
        valid.sort(key=lambda r: r["date"], reverse=True)
        return valid[:top_k]
