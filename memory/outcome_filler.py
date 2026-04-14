"""
memory/outcome_filler.py — 과거 포트폴리오 결과에 실제 수익률(r_real) 채우기

results/YYYY-MM-DD/portfolio.json 중 r_real이 없는 항목에 대해
Polygon 데이터로 실제 가중 포트폴리오 수익률을 계산하여 기록한다.

r_real이 채워지면 results/strategy_memory.json에도 반영 (Work 3):
  - {ticker}_{date} 키에 r_real, outcome_reliability, performance_score 업데이트

point-in-time 안전 규칙:
  - decision_date + 7일 <= run_date 인 경우에만 평가 (T+7 확정 후)
  - 이미 r_real이 있으면 스킵
"""
from __future__ import annotations

import json
import logging
from datetime import date as _date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent.parent / "results"
STRATEGY_MEM_PATH = RESULTS_DIR / "strategy_memory.json"

from utils.forward_return import fetch_forward_return  # noqa: E402 — 모듈 레벨 import (monkeypatch 가능)


# ─── strategy_memory.json 업데이트 ───────────────────────────────────────────

def _update_strategy_memory(decision_date: str, r_real: float, tickers: list[str]) -> None:
    """
    r_real이 채워진 날짜에 대해 results/strategy_memory.json의
    {ticker}_{date} 항목에 r_real, outcome_reliability, performance_score를 기록.

    outcome_reliability 기준 (validity_scorer.py와 동일한 임계값 사용):
      r_real >= 0.02 → 1.0  (수익률 2% 이상)
      r_real >= 0    → 0.85 (소폭 양성)
      r_real <  0    → 0.65 (손실)
    """
    if not STRATEGY_MEM_PATH.exists():
        return
    try:
        mem = json.loads(STRATEGY_MEM_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"strategy_memory.json 읽기 실패: {e}")
        return

    if r_real >= 0.02:
        outcome_rel = 1.0
    elif r_real >= 0:
        outcome_rel = 0.85
    else:
        outcome_rel = 0.65

    changed = False
    for ticker in tickers:
        key = f"{ticker}_{decision_date}"
        if key in mem:
            entry = mem[key]
            entry["r_real"] = r_real
            entry["performance_score"] = r_real
            entry["outcome_reliability"] = outcome_rel
            entry["r_real_source"] = "polygon_weighted"
            changed = True
            logger.debug(f"strategy_memory 업데이트: {key} r_real={r_real:.4f}")

    if changed:
        try:
            STRATEGY_MEM_PATH.write_text(
                json.dumps(mem, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"strategy_memory.json 쓰기 실패: {e}")


# ─── 단일 포트폴리오 수익률 계산 ──────────────────────────────────────────────

def compute_portfolio_r_real(
    fetcher,
    allocations: list,
    decision_date: str,
) -> Optional[float]:
    """
    포트폴리오 배분 목록에서 T→T+7 가중 수익률 계산.

    Args:
        fetcher: PolygonFetcher 인스턴스
        allocations: [{"ticker": str, "weight": float, "action": str}, ...]
        decision_date: 결정일 (YYYY-MM-DD)

    Returns:
        가중 수익률 float 또는 None (계산 불가 시)
    """

    weighted_sum = 0.0
    total_weight = 0.0

    for alloc in allocations:
        ticker = alloc.get("ticker", "")
        weight = alloc.get("weight", 0.0)
        action = alloc.get("action", "")

        # 스킵 조건
        if weight <= 0:
            continue
        if action == "SELL":
            continue
        if ticker == "CASH" or not ticker:
            continue

        r = fetch_forward_return(
            fetcher,
            ticker=ticker,
            execution_date=decision_date,
            lookforward_days=10,
        )
        if r is None:
            logger.debug(f"forward_return None for {ticker} on {decision_date} — 스킵")
            continue

        weighted_sum += weight * r
        total_weight += weight

    if total_weight == 0.0:
        return None

    return weighted_sum / total_weight


# ─── 미완 결과 일괄 채우기 ──────────────────────────────────────────────────

def fill_pending_outcomes(
    run_date: str,
    fetcher=None,
) -> dict[str, float]:
    """
    run_date 기준으로 r_real이 없는 과거 portfolio.json에 수익률을 채운다.

    Rules:
      - decision_date + 7 <= run_date 인 경우에만 평가 (point-in-time 안전)
      - r_real이 이미 있으면 스킵
      - compute_portfolio_r_real()로 가중 수익률 계산 후 파일에 저장

    Args:
        run_date: 현재 실행일 (YYYY-MM-DD)
        fetcher: PolygonFetcher 인스턴스. None이면 자동 생성.

    Returns:
        {date: r_real} — 새로 채워진 항목만 반환
    """
    if fetcher is None:
        try:
            import os
            from data.polygon_fetcher import PolygonFetcher
            fetcher = PolygonFetcher(api_key=os.environ.get("POLYGON_API_KEY"))
        except Exception as e:
            logger.warning(f"PolygonFetcher 초기화 실패: {e}")
            return {}

    if not RESULTS_DIR.exists():
        return {}

    run_dt = _date.fromisoformat(run_date)
    cutoff = run_dt - timedelta(days=7)  # decision_date + 7 <= run_date

    filled: dict[str, float] = {}

    # results/ 아래 YYYY-MM-DD 형식 디렉토리 순회
    date_dirs = sorted(
        d for d in RESULTS_DIR.iterdir()
        if d.is_dir() and (d / "portfolio.json").exists()
    )

    for d in date_dirs:
        decision_date_str = d.name

        # point-in-time 안전: decision_date가 (run_date - 7일) 이하여야 함
        try:
            decision_dt = _date.fromisoformat(decision_date_str)
        except ValueError:
            continue

        if decision_dt > cutoff:
            # 아직 T+7이 확정되지 않음
            continue

        portfolio_path = d / "portfolio.json"
        try:
            portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"portfolio.json 읽기 실패 ({d.name}): {e}")
            continue

        # 이미 r_real이 있으면 스킵
        if portfolio.get("r_real") is not None:
            continue

        # 배분 목록 가져오기
        allocs = portfolio.get("portfolio", {}).get("allocations", [])
        if not allocs:
            continue

        r_real = compute_portfolio_r_real(fetcher, allocs, decision_date_str)
        if r_real is None:
            continue

        # 파일에 기록
        portfolio["r_real"] = r_real
        portfolio["r_real_source"] = "polygon_weighted"
        portfolio["r_real_eval_date"] = run_date

        try:
            portfolio_path.write_text(
                json.dumps(portfolio, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            filled[decision_date_str] = r_real
            logger.info(f"r_real 기록: {decision_date_str} → {r_real:.4f}")
        except Exception as e:
            logger.warning(f"portfolio.json 쓰기 실패 ({d.name}): {e}")
            continue

        # Work 3: strategy_memory.json에도 반영
        tickers = portfolio.get("tickers", [])
        if tickers:
            _update_strategy_memory(decision_date_str, r_real, tickers)

    return filled
