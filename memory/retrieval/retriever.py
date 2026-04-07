"""
Retriever — top-k retrieval with validity scoring and timestamp guard.

핵심 원칙:
- as_of 이후 데이터 절대 참조 금지 (timestamp guard)
- validity score floor 이하 case 폐기
- top-k=5~10으로 제한
- retrieved_case_summary 형식으로 재구성 (raw text 아님)
"""
from typing import List, Optional, Dict
from memory.base_memory import BaseMemory
from memory.retrieval.validity_scorer import compute_validity_score


class Retriever:
    def __init__(
        self,
        memory: BaseMemory,
        floor: float = 0.4,
        top_k: int = 7,
    ):
        self.memory = memory
        self.floor = floor
        self.top_k = min(top_k, 10)  # 최대 10

    def retrieve(
        self,
        query: dict,
        as_of: str,
        current_regime: str = "mixed",
        top_k: Optional[int] = None,
    ) -> List[dict]:
        """
        as_of 이전 데이터 중 validity score 상위 top-k 반환.
        validity score floor 이하 case 자동 폐기.
        반환 형식: retrieved_case_summary (raw text 아님).
        """
        k = min(top_k or self.top_k, 10)

        # memory에서 as_of 이전 candidate 가져오기
        candidates = self.memory.retrieve(query, as_of, top_k=50)  # 넉넉하게 가져온 후 필터

        # validity scoring + 필터
        scored = []
        for case in candidates:
            score = compute_validity_score(
                query=query,
                case=case,
                as_of=as_of,
                current_regime=current_regime,
                floor=self.floor,
            )
            if score is not None:  # floor 이상만 통과
                scored.append((score, case))

        # score 내림차순 정렬
        scored.sort(key=lambda x: x[0], reverse=True)

        # top-k 선택 + retrieved_case_summary 형식으로 변환
        results = []
        for score, case in scored[:k]:
            summary = self._to_case_summary(case, score, as_of)
            results.append(summary)

        return results

    def _to_case_summary(self, case: dict, validity_score: float, as_of: str) -> dict:
        """
        case를 retrieved_case_summary 형식으로 변환.
        raw text 전문이 아닌 구조화된 요약만 포함.
        """
        value = case.get("value", {})
        return {
            "case_date": case.get("date", ""),
            "as_of": as_of,
            "validity_score": validity_score,
            "regime": case.get("regime") or value.get("market_regime", "unknown"),
            "selected_policy": value.get("selected_policy"),
            "outcome_horizon": value.get("outcome_horizon"),
            "success_failure_rationale": value.get("rationale", ""),
            "tags": case.get("tags", []),
        }
