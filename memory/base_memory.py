"""Base memory interface — 모든 memory 계층의 공통 인터페이스."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseMemory(ABC):
    """
    memory 계층 공통 인터페이스.
    point-in-time safety: as_of 파라미터가 있는 메서드는 미래 데이터를 반환하면 안 됨.
    """

    @abstractmethod
    def store(self, key: str, value: dict, date: str, tags: Optional[List[str]] = None) -> None:
        """데이터 저장."""
        ...

    @abstractmethod
    def retrieve(self, query: dict, as_of: str, top_k: int = 5) -> List[dict]:
        """
        query와 유사한 case top-k 반환.
        as_of 이후 데이터는 절대 반환 안 함 (point-in-time).
        """
        ...

    @abstractmethod
    def get_by_date(self, date: str) -> Optional[dict]:
        """특정 날짜 데이터 조회."""
        ...

    def _enforce_point_in_time(self, record_date: str, as_of: str) -> bool:
        """record_date가 as_of보다 미래이면 False."""
        try:
            rd = datetime.strptime(record_date, "%Y-%m-%d")
            ao = datetime.strptime(as_of, "%Y-%m-%d")
            return rd <= ao
        except ValueError:
            return False
