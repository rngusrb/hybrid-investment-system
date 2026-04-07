"""
Agent Reliability Tracking & Conditional Gating.

핵심:
- cold start: 0.5 (neutral)
- update: 5가지 기준으로 rolling update
- conditional gating: regime별로 어떤 agent 신뢰할지 결정
- floor 이하: hard gating 또는 downweighting
- Otto 연결: reliability_penalty 계산 → OttoAgent.compute_utility()에 전달
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum
import math


class GatingDecision(Enum):
    FULL = "full"              # 정상 신뢰
    DOWNWEIGHT = "downweight"  # 가중치 축소
    HARD_GATE = "hard_gate"    # 출력 무시


@dataclass
class ReliabilityState:
    """agent별 reliability 상태."""
    agent_name: str
    score: float = 0.5     # cold start: 0.5 neutral
    update_count: int = 0
    decay_factor: float = 0.9
    floor: float = 0.35
    history: List[float] = field(default_factory=list)

    def update(
        self,
        decision_usefulness: float,               # 0~1: 이 agent output이 final decision에 얼마나 유용했는가
        contradiction_penalty: float = 0.0,       # 0~1: 다른 agent와 모순이 얼마나 많았는가
        propagation_adoption_rate: float = 0.5,   # 0~1: signal이 실제로 상위에 채택된 비율
        outcome_alignment: float = 0.5,           # 0~1: 실제 결과와 예측이 얼마나 맞았는가
        noise_penalty: float = 0.0,               # 0~1: empty/stale/noisy output 비율
    ):
        """reliability score 업데이트 — weighted average of 5 dimensions."""
        # weighted combination
        new_score = (
            0.30 * decision_usefulness
            + 0.20 * (1.0 - contradiction_penalty)
            + 0.20 * propagation_adoption_rate
            + 0.20 * outcome_alignment
            + 0.10 * (1.0 - noise_penalty)
        )
        # exponential moving average with decay
        self.score = self.decay_factor * self.score + (1.0 - self.decay_factor) * new_score
        self.score = max(0.0, min(1.0, self.score))  # [0, 1] clamp
        self.update_count += 1
        self.history.append(self.score)

    def get_gating_decision(self) -> GatingDecision:
        """current score 기준 gating 결정."""
        if self.score < self.floor:
            return GatingDecision.HARD_GATE
        elif self.score < self.floor + 0.1:
            return GatingDecision.DOWNWEIGHT
        else:
            return GatingDecision.FULL

    def get_weight_multiplier(self) -> float:
        """
        reliability 기반 가중치 배수.
        FULL: 1.0, DOWNWEIGHT: score/0.5, HARD_GATE: 0.0
        """
        decision = self.get_gating_decision()
        if decision == GatingDecision.HARD_GATE:
            return 0.0
        elif decision == GatingDecision.DOWNWEIGHT:
            return self.score / 0.5  # 0.5 기준으로 정규화
        else:
            return 1.0


class AgentReliabilityManager:
    """
    전체 agent의 reliability 상태 관리 + Otto 연결.

    regime별 conditional gating:
    - risk_off_macro_shock: macro, news, technical 채널 신뢰
    - stable_trend_market: technical, sector_rotation 신뢰
    - earnings_season: quantitative, news, qualitative 신뢰
    """

    CONDITIONAL_GATING = {
        "risk_off_macro_shock": ["macro", "news", "technical"],
        "stable_trend_market": ["technical", "sector_rotation"],
        "earnings_season": ["quantitative", "news", "qualitative"],
        "default": ["emily", "bob", "dave"],
    }

    def __init__(self, agent_names: List[str], config: dict = None):
        config = config or {}
        cold_start = config.get("cold_start", 0.5)
        floor = config.get("floor", 0.35)
        decay = config.get("decay_factor", 0.9)

        self.states: Dict[str, ReliabilityState] = {
            name: ReliabilityState(
                agent_name=name,
                score=cold_start,
                floor=floor,
                decay_factor=decay,
            )
            for name in agent_names
        }

    def update_agent(self, agent_name: str, **kwargs):
        """특정 agent reliability 업데이트."""
        if agent_name in self.states:
            self.states[agent_name].update(**kwargs)

    def get_reliability_summary(self) -> Dict[str, float]:
        """agent별 현재 reliability score dict 반환."""
        return {name: state.score for name, state in self.states.items()}

    def get_gating_decisions(self) -> Dict[str, GatingDecision]:
        """agent별 현재 gating 결정 반환."""
        return {name: state.get_gating_decision() for name, state in self.states.items()}

    def get_weight_multipliers(self) -> Dict[str, float]:
        """agent별 가중치 배수 반환."""
        return {name: state.get_weight_multiplier() for name, state in self.states.items()}

    def compute_reliability_penalty(
        self,
        selected_strategy_source: str = "bob",
        market_analysis_source: str = "emily",
        risk_source: str = "dave",
    ) -> float:
        """
        Otto의 Utility 계산에 사용할 AgentReliabilityPenalty.

        신뢰도 낮은 source에 과도하게 의존한 경우 penalty 부과.
        penalty = 1 - weighted_avg_reliability
        """
        sources = [selected_strategy_source, market_analysis_source, risk_source]
        reliability_vals = [
            self.states[s].score if s in self.states else 0.5
            for s in sources
        ]
        avg_reliability = sum(reliability_vals) / len(reliability_vals)
        return max(0.0, 1.0 - avg_reliability)  # 평균 신뢰도 낮을수록 penalty 높음

    def get_active_agents_for_regime(self, regime: str) -> List[str]:
        """
        regime별 활성화해야 할 agent 목록 반환.
        conditional gating 적용.
        HARD_GATE 상태인 agent는 제외.
        """
        preferred = self.CONDITIONAL_GATING.get(regime, self.CONDITIONAL_GATING["default"])
        # HARD_GATE가 아닌 agent만 수집
        active = []
        for name, state in self.states.items():
            if state.get_gating_decision() != GatingDecision.HARD_GATE:
                active.append(name)
        # preferred 목록 우선 정렬
        active.sort(key=lambda n: (0 if n in preferred else 1))
        return active

    def apply_reliability_to_otto_packet(self, otto_packet: dict) -> dict:
        """
        Otto policy packet에 reliability summary를 삽입.
        이 함수를 통해 reliability가 실제로 Otto의 input에 반영됨.
        """
        updated = dict(otto_packet)
        updated["agent_reliability_summary"] = self.get_reliability_summary()
        return updated
