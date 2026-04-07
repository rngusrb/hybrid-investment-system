"""
Shared Ledger — 공식 output만 저장하는 공식 기록부.
raw chain-of-thought, 내부 추론 저장 금지.
"""
from typing import Optional, List, Dict
from datetime import datetime

# 저장 허용 output 타입
ALLOWED_ENTRY_TYPES = frozenset([
    "final_market_report",
    "technical_summary_packet",
    "candidate_strategy_summary",
    "risk_review_summary",
    "debate_resolution",
    "signal_conflict_resolution",
    "final_policy_decision",
    "execution_plan",
    "risk_override_record",
    "weekly_propagation_audit_summary",
])

# 저장 금지 타입
FORBIDDEN_ENTRY_TYPES = frozenset([
    "raw_chain_of_thought",
    "internal_sketch",
    "retrieval_raw_text",
    "intermediate_hypothesis",
    "debate_transcript",
    "llm_reasoning",
])


class SharedLedger:
    """
    공식 output 전용 기록소.
    허용 타입만 저장. 금지 타입 시도 시 ValueError.
    """

    def __init__(self):
        self._entries: List[dict] = []

    def record(self, entry_type: str, content: dict, date: str, agent: Optional[str] = None):
        """
        공식 output 저장.
        금지 타입이면 ValueError 발생.
        """
        if entry_type in FORBIDDEN_ENTRY_TYPES:
            raise ValueError(
                f"Cannot store '{entry_type}' in Shared Ledger. "
                f"Forbidden types: {FORBIDDEN_ENTRY_TYPES}. "
                "Only official outputs are stored here."
            )
        if entry_type not in ALLOWED_ENTRY_TYPES:
            raise ValueError(
                f"Unknown entry type '{entry_type}'. "
                f"Allowed types: {ALLOWED_ENTRY_TYPES}"
            )

        entry = {
            "entry_type": entry_type,
            "date": date,
            "agent": agent,
            "content": content,
            "recorded_at": datetime.utcnow().isoformat(),
        }
        self._entries.append(entry)

    def get_entries_by_type(self, entry_type: str) -> List[dict]:
        return [e for e in self._entries if e["entry_type"] == entry_type]

    def get_entries_by_date(self, date: str) -> List[dict]:
        return [e for e in self._entries if e["date"] == date]

    def get_latest(self, entry_type: str) -> Optional[dict]:
        entries = self.get_entries_by_type(entry_type)
        return entries[-1] if entries else None

    def get_all(self) -> List[dict]:
        return list(self._entries)
