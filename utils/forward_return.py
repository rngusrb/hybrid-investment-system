"""
utils.forward_return — Polygon 기반 실제 T+1 수익률 계산.

전략 실행일(T)의 close → 다음 거래일(T+1)의 close 간 수익률을 계산.
Polygon API 호출 실패 또는 T+1 데이터 미확인 시 None 반환 (fallback: r_sim 사용).

사용 방법:
    r_real = fetch_forward_return(fetcher, ticker="SPY", execution_date="2024-01-19")
    if r_real is None:
        r_real = r_sim  # fallback
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_DATE_FMT = "%Y-%m-%d"


def _parse(d: str) -> date:
    return datetime.strptime(d, _DATE_FMT).date()


def _fmt(d: date) -> str:
    return d.strftime(_DATE_FMT)


def fetch_forward_return(
    fetcher,
    ticker: str,
    execution_date: str,
    lookforward_days: int = 5,
) -> Optional[float]:
    """
    execution_date(T) close → 다음 거래일 close 기준 실제 수익률 반환.

    Args:
        fetcher: PolygonFetcher 인스턴스 (None이면 즉시 None 반환)
        ticker: 종목 코드 (e.g. "SPY")
        execution_date: 전략 실행일 (YYYY-MM-DD)
        lookforward_days: T+1 거래일을 찾기 위한 최대 달력 일수 (주말/공휴일 건너뜀)

    Returns:
        실제 수익률 float (e.g. 0.012 = +1.2%) 또는 None
    """
    if fetcher is None:
        return None

    try:
        exec_date = _parse(execution_date)
        # T+1 ~ T+lookforward_days 범위에서 첫 번째 거래일 close 취득
        t1_start = _fmt(exec_date + timedelta(days=1))
        t1_end = _fmt(exec_date + timedelta(days=lookforward_days))
        # as_of를 t1_end로 설정 — 미래 데이터 접근 허용 (이미 과거 날짜인 경우)
        today = date.today()
        if _parse(t1_end) > today:
            # T+1이 아직 미래 — real return 불확정
            return None

        # T 당일 close 취득
        t0_result = fetcher.get_ohlcv(
            ticker=ticker,
            from_date=execution_date,
            to_date=execution_date,
            as_of=execution_date,
        )
        t0_bars = t0_result.get("data", [])
        if not t0_bars:
            return None
        close_t0 = t0_bars[-1].get("close")
        if close_t0 is None or close_t0 == 0:
            return None

        # T+1 close 취득
        t1_result = fetcher.get_ohlcv(
            ticker=ticker,
            from_date=t1_start,
            to_date=t1_end,
            as_of=t1_end,
        )
        t1_bars = t1_result.get("data", [])
        if not t1_bars:
            return None
        close_t1 = t1_bars[0].get("close")  # 가장 이른 거래일
        if close_t1 is None:
            return None

        r_real = (float(close_t1) - float(close_t0)) / float(close_t0)
        return round(r_real, 6)

    except Exception as exc:
        logger.warning(f"forward_return fetch failed for {ticker} on {execution_date}: {exc}")
        return None
