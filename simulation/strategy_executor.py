"""
StrategyExecutor — CandidateStrategy.type을 매매 시그널로 변환.

지원 전략 타입:
- momentum: N일 수익률 모멘텀 롱
- mean_reversion: 단기 과매도 반등
- directional: 드리프트 방향 추종
- hedged: 롱/쇼트 혼합 (낮은 net exposure)
- market_neutral: 노출 최소화
- defensive: 대부분 현금, 소량 롱
"""
from typing import List, Tuple
import numpy as np


class StrategyExecutor:
    """returns 시계열을 받아 strategy_type별 포지션을 계산한다."""

    def compute_positions(
        self,
        returns: List[float],
        strategy_type: str,
        lookback: int = 20,
    ) -> List[float]:
        """
        포지션 크기 시계열 반환 (-1 ~ +1).
        첫 lookback 기간은 0 (포지션 미결정).
        """
        n = len(returns)
        positions = [0.0] * n

        if n <= lookback:
            return positions

        if strategy_type == "momentum":
            positions = self._momentum(returns, lookback)
        elif strategy_type == "mean_reversion":
            positions = self._mean_reversion(returns, lookback)
        elif strategy_type == "directional":
            positions = self._directional(returns, lookback)
        elif strategy_type == "hedged":
            positions = self._hedged(returns, lookback)
        elif strategy_type == "market_neutral":
            positions = self._market_neutral(returns, lookback)
        elif strategy_type == "defensive":
            positions = self._defensive(returns)
        else:
            positions = self._momentum(returns, lookback)  # fallback

        return positions

    def compute_strategy_returns(
        self,
        raw_returns: List[float],
        positions: List[float],
    ) -> Tuple[List[float], float]:
        """
        포지션 적용 수익률 + 평균 turnover 계산.
        strategy_return[t] = position[t-1] * raw_return[t]
        """
        strat_returns = []
        turnovers = []

        prev_pos = 0.0
        for i in range(1, len(raw_returns)):
            pos = positions[i - 1]
            strat_returns.append(pos * raw_returns[i])
            turnovers.append(abs(pos - prev_pos))
            prev_pos = pos

        avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0
        return strat_returns, avg_turnover

    # ── 개별 전략 로직 ──────────────────────────────────────────────

    def _momentum(self, returns: List[float], lookback: int) -> List[float]:
        """lookback 기간 누적 수익률 양수면 롱, 음수면 숏."""
        positions = [0.0] * len(returns)
        for i in range(lookback, len(returns)):
            cum = sum(returns[i - lookback:i])
            positions[i] = 1.0 if cum > 0 else -0.5
        return positions

    def _mean_reversion(self, returns: List[float], lookback: int) -> List[float]:
        """최근 수익률이 과하게 음수면 롱 진입."""
        positions = [0.0] * len(returns)
        for i in range(lookback, len(returns)):
            recent = returns[i - lookback : i - 1]  # exclude the last bar
            if not recent:
                continue
            z = (returns[i - 1] - np.mean(recent)) / (np.std(recent) + 1e-8)
            if z < -1.5:
                positions[i] = 1.0
            elif z > 1.5:
                positions[i] = -0.3
            else:
                positions[i] = 0.2
        return positions

    def _directional(self, returns: List[float], lookback: int) -> List[float]:
        """장기 드리프트 방향 추종."""
        positions = [0.0] * len(returns)
        for i in range(lookback, len(returns)):
            trend = np.mean(returns[i - lookback:i])
            positions[i] = 0.8 if trend > 0 else -0.3
        return positions

    def _hedged(self, returns: List[float], lookback: int) -> List[float]:
        """낮은 net exposure 유지."""
        positions = [0.0] * len(returns)
        for i in range(lookback, len(returns)):
            trend = np.mean(returns[i - lookback:i])
            positions[i] = 0.5 if trend > 0 else -0.2
        return positions

    def _market_neutral(self, returns: List[float], lookback: int) -> List[float]:
        """포지션 최소화."""
        positions = [0.0] * len(returns)
        for i in range(lookback, len(returns)):
            positions[i] = 0.1
        return positions

    def _defensive(self, returns: List[float]) -> List[float]:
        """대부분 현금."""
        return [0.15] * len(returns)
