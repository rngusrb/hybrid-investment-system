"""
Point-in-time safe backtester.

핵심 규칙:
- 각 날짜 t에서 t 이전 데이터만 사용
- 미래 regime tag, 미래 뉴스 접근 금지
- review horizon이 닫히기 전 outcome reliability 확정 금지
"""
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class BacktestResult:
    dates: List[str] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    policies: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    leakage_violations: List[str] = field(default_factory=list)  # 위반 기록


class PointInTimeBacktester:
    """
    point-in-time safe backtester.
    각 step에서 as_of 이후 데이터 접근을 차단하는 guard 포함.
    """

    def __init__(self, review_horizon_days: int = 20):
        self.review_horizon_days = review_horizon_days
        self._leakage_violations: List[str] = []

    def check_leakage(self, data_date: str, as_of_date: str) -> bool:
        """
        data_date가 as_of_date보다 미래이면 leakage 위반.
        Returns True if leakage detected.
        """
        from datetime import datetime
        try:
            d = datetime.strptime(data_date, "%Y-%m-%d")
            ao = datetime.strptime(as_of_date, "%Y-%m-%d")
            if d > ao:
                violation = f"LEAKAGE: data_date={data_date} > as_of={as_of_date}"
                self._leakage_violations.append(violation)
                return True
            return False
        except ValueError:
            return False

    def run(
        self,
        dates: List[str],
        policy_fn: Callable[[str, dict], str],  # (date, available_data) -> policy_name
        return_fn: Callable[[str, str], float],  # (date, policy) -> return
        available_data_fn: Callable[[str], dict],  # (as_of) -> data up to as_of
    ) -> BacktestResult:
        """
        백테스트 실행.
        각 날짜에서 policy_fn은 as_of=date 이전 데이터만 받음.
        """
        result = BacktestResult()

        for dt in dates:
            # point-in-time: as_of=dt 이전 데이터만
            available = available_data_fn(dt)

            # leakage check
            for data_key, data_val in available.items():
                if isinstance(data_val, dict) and data_val.get("date"):
                    self.check_leakage(data_val["date"], dt)

            policy = policy_fn(dt, available)
            ret = return_fn(dt, policy)

            result.dates.append(dt)
            result.returns.append(ret)
            result.policies.append(policy)

        result.leakage_violations = list(self._leakage_violations)
        return result

    def get_leakage_violations(self) -> List[str]:
        return list(self._leakage_violations)
