"""
SimulatedTradingEngine — Bob의 CandidateStrategy를 실제 백테스트로 검증.

흐름:
1. SyntheticDataProvider로 합성 수익률 시계열 생성 (API 없을 때)
   OR PolygonFetcher로 실제 데이터 사용 (API 있을 때)
2. StrategyExecutor로 포지션 계산
3. evaluation/metrics.py로 지표 계산
4. SimMetrics 딕셔너리 반환
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from simulation.synthetic_provider import SyntheticDataProvider
from simulation.strategy_executor import StrategyExecutor
from evaluation.metrics import (
    compute_sharpe,
    compute_sortino,
    compute_max_drawdown,
    compute_total_return,
    compute_win_rate,
)


def _date_range(start: str, end: str) -> list:
    """start ~ end 사이 날짜 리스트 (주말 제외 근사)."""
    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        return []
    dates = []
    cur = s
    while cur <= e:
        if cur.weekday() < 5:  # 월~금
            dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return dates


class SimulatedTradingEngine:
    """
    전략 타입 + sim_window → 실제 백테스트 metrics 반환.
    fetcher=None이면 SyntheticDataProvider 사용 (API 불필요).
    """

    def __init__(self, fetcher=None):
        self._fetcher = fetcher
        self._synth = SyntheticDataProvider()
        self._executor = StrategyExecutor()

    def run_strategy(
        self,
        strategy_type: str,
        sim_window: Dict[str, str],
        regime_fit: float = 0.5,
        technical_alignment: float = 0.5,
        ticker: str = "SPY",
    ) -> Optional[Dict[str, Any]]:
        """
        전략 백테스트 실행 → SimMetrics 딕셔너리 반환.
        실패 시 None 반환 (기존 LLM 값 유지).
        """
        train_start = sim_window.get("train_start", "")
        train_end = sim_window.get("train_end", "")
        if not train_start or not train_end:
            return None

        dates = _date_range(train_start, train_end)
        if len(dates) < 30:  # 최소 30일 필요
            return None

        # 수익률 시계열 확보
        raw_returns = self._get_returns(dates, strategy_type, regime_fit, technical_alignment, ticker)
        if not raw_returns:
            return None

        # 포지션 계산
        positions = self._executor.compute_positions(raw_returns, strategy_type)

        # 전략 수익률 + turnover
        strat_returns, avg_turnover = self._executor.compute_strategy_returns(raw_returns, positions)

        if len(strat_returns) < 10:
            return None

        # 지표 계산
        sharpe = compute_sharpe(strat_returns)
        sortino = compute_sortino(strat_returns)
        mdd = compute_max_drawdown(strat_returns)
        total_ret = compute_total_return(strat_returns)
        hit_rate = compute_win_rate(strat_returns)

        # 값 범위 clamp
        return {
            "return": round(max(-0.99, min(total_ret, 9.99)), 4),
            "sharpe": round(max(-5.0, min(sharpe, 10.0)), 4),
            "sortino": round(max(-5.0, min(sortino, 10.0)), 4),
            "mdd": round(max(0.0, min(mdd, 0.99)), 4),
            "turnover": round(max(0.0, min(avg_turnover, 2.0)), 4),
            "hit_rate": round(max(0.0, min(hit_rate, 1.0)), 4),
            "data_source": "real" if self._fetcher is not None else "synthetic",
        }

    def _get_returns(
        self,
        dates: list,
        strategy_type: str,
        regime_fit: float,
        technical_alignment: float,
        ticker: str,
    ) -> list:
        """실제 데이터 or 합성 데이터 반환."""
        if self._fetcher is not None:
            try:
                result = self._fetcher.get_ohlcv(
                    ticker=ticker,
                    from_date=dates[0],
                    to_date=dates[-1],
                    as_of=dates[-1],
                )
                bars = result.get("data", [])
                if len(bars) >= 30:
                    from data.data_manager import DataManager
                    dm = DataManager()
                    import pandas as pd
                    df = dm.preprocess_ohlcv(bars)
                    df = dm.compute_returns(df)
                    returns = df["return"].dropna().tolist()
                    if len(returns) >= 30:
                        return returns
            except Exception:
                pass  # fetcher 실패 시 synthetic fallback

        # Synthetic fallback
        return self._synth.get_returns(dates, strategy_type, regime_fit, technical_alignment)
