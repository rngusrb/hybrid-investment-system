"""
SyntheticDataProvider — API 없을 때 합성 수익률 시계열 생성.
전략 품질(regime_fit, technical_alignment)에 따라 드리프트를 조정해
현실적인 성과 분포를 만든다.
"""
import hashlib
import numpy as np
from typing import List


class SyntheticDataProvider:
    """
    regime_fit + technical_alignment 기반 합성 수익률 생성.
    동일 파라미터면 항상 같은 시계열 반환 (재현성 보장).
    """

    BASE_VOL = 0.012  # 일간 변동성 ~1.2%

    def get_returns(
        self,
        dates: List[str],
        strategy_type: str,
        regime_fit: float,
        technical_alignment: float,
    ) -> List[float]:
        """
        합성 일간 수익률 반환.
        드리프트 = regime_fit * technical_alignment * 0.0008 (연 약 20% 상한)
        """
        seed = self._make_seed(strategy_type, dates[0] if dates else "2024-01-01")
        rng = np.random.default_rng(seed)

        quality = (regime_fit + technical_alignment) / 2.0
        drift = quality * 0.0008  # 일간 드리프트

        # 전략 타입별 변동성 조정
        vol_multiplier = {
            "momentum": 1.2,
            "mean_reversion": 0.9,
            "directional": 1.1,
            "hedged": 0.7,
            "market_neutral": 0.5,
            "defensive": 0.4,
        }.get(strategy_type, 1.0)

        vol = self.BASE_VOL * vol_multiplier
        returns = rng.normal(drift, vol, len(dates)).tolist()
        return returns

    def _make_seed(self, strategy_type: str, start_date: str) -> int:
        raw = f"{strategy_type}_{start_date}"
        return int(hashlib.md5(raw.encode()).hexdigest(), 16) % (2**31)
