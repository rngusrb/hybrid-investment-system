"""Base Meeting — 모든 meeting의 공통 로직."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from ledger.shared_ledger import SharedLedger


class BaseMeeting(ABC):
    def __init__(self, ledger: SharedLedger, config: dict = None):
        self.ledger = ledger
        self.config = config or {}

    @abstractmethod
    def run(self, state: dict) -> dict:
        """meeting 실행. 업데이트된 state 반환."""
        ...

    def _record_to_ledger(self, entry_type: str, content: dict, date: str, agent: str = None):
        """공식 output을 shared ledger에 기록."""
        self.ledger.record(entry_type=entry_type, content=content, date=date, agent=agent)

    def _log_skip(self, state: dict, node_name: str, reason: str) -> dict:
        updated = dict(state)
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": node_name, "reason": reason, "date": state.get("current_date")
        }]
        return updated
