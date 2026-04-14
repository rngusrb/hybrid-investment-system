"""
simulation/backtester.py — Bob의 시뮬레이션 오케스트레이터 (run_loop용)

이미 fetch된 bars로 전략 Pool 백테스트 → 최적 전략 선택 → strategy_memory 저장.
추가 API 호출 없음 (SimulatedTradingEngine과 달리 bars를 직접 받음).

흐름:
  bars (fetch_data 결과) → returns 변환
  → 6개 전략 백테스트 (StrategyExecutor)
  → 지표 계산 (sharpe, sortino, mdd, return, win_rate)
  → 최적 전략 선택 (sharpe 기준)
  → results/strategy_memory.json 저장 (영속)
  → Portfolio Manager 프롬프트용 포맷 반환
"""
import json
from pathlib import Path
from typing import Optional

import numpy as np

from simulation.strategy_executor import StrategyExecutor
from evaluation.metrics import (
    compute_sharpe, compute_sortino,
    compute_max_drawdown, compute_total_return, compute_win_rate,
)

RESULTS_DIR       = Path(__file__).parent.parent / "results"
STRATEGY_MEM_PATH = RESULTS_DIR / "strategy_memory.json"

STRATEGY_TYPES = [
    "momentum",
    "mean_reversion",
    "directional",
    "hedged",
    "market_neutral",
    "defensive",
]

MIN_BARS = 30   # 최소 bar 수


# ─── bars → returns ──────────────────────────────────────────────────────────

def bars_to_returns(bars: list[dict]) -> list[float]:
    """
    OHLCV bars → 일별 수익률 리스트.
    bars는 date 순 정렬 가정. close 기준.
    lookahead 없음: i번째 return = close[i]/close[i-1] - 1.
    """
    closes = []
    for b in bars:
        c = b.get("close") if b.get("close") is not None else b.get("c")
        if c is not None:
            try:
                closes.append(float(c))
            except (ValueError, TypeError):
                pass

    if len(closes) < 2:
        return []

    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns.append(closes[i] / closes[i - 1] - 1.0)
        else:
            returns.append(0.0)
    return returns


# ─── 단일 전략 백테스트 ───────────────────────────────────────────────────────

def _run_one_strategy(
    returns: list[float],
    strategy_type: str,
    lookback: int = 20,
) -> dict:
    """단일 전략 → 성과 지표 dict."""
    executor = StrategyExecutor()
    positions = executor.compute_positions(returns, strategy_type, lookback=lookback)
    strat_returns, avg_turnover = executor.compute_strategy_returns(returns, positions)

    if len(strat_returns) < 10:
        return _empty_metrics(strategy_type)

    return {
        "strategy":  strategy_type,
        "return":    round(float(np.clip(compute_total_return(strat_returns), -0.99, 9.99)), 4),
        "sharpe":    round(float(np.clip(compute_sharpe(strat_returns), -5.0, 10.0)), 4),
        "sortino":   round(float(np.clip(compute_sortino(strat_returns), -5.0, 10.0)), 4),
        "mdd":       round(float(np.clip(compute_max_drawdown(strat_returns), 0.0, 0.99)), 4),
        "win_rate":  round(float(np.clip(compute_win_rate(strat_returns), 0.0, 1.0)), 4),
        "turnover":  round(float(np.clip(avg_turnover, 0.0, 2.0)), 4),
        "n_bars":    len(returns),
        "data_source": "real",
    }


def _empty_metrics(strategy_type: str) -> dict:
    return {
        "strategy": strategy_type, "return": 0.0, "sharpe": 0.0,
        "sortino": 0.0, "mdd": 0.0, "win_rate": 0.5,
        "turnover": 0.0, "n_bars": 0, "data_source": "insufficient_data",
    }


# ─── 전체 전략 Pool 백테스트 ─────────────────────────────────────────────────

def backtest_all(
    bars: list[dict],
    ticker: str,
    as_of: str,
    lookback: int = 20,
) -> dict:
    """
    모든 전략 타입 백테스트 → 최적 전략 선택.

    반환:
        {
          "ticker": ..., "as_of": ...,
          "results": [{strategy, return, sharpe, ...}, ...],
          "best": {strategy, return, sharpe, ...},
          "selected_strategy": str,
          "data_source": "real" | "insufficient_data",
        }
    """
    returns = bars_to_returns(bars)

    if len(returns) < MIN_BARS:
        return {
            "ticker": ticker, "as_of": as_of,
            "results": [], "best": _empty_metrics("defensive"),
            "selected_strategy": "defensive",
            "data_source": "insufficient_data",
            "note": f"bars 부족 ({len(returns)}개 < {MIN_BARS})",
        }

    results = [
        _run_one_strategy(returns, st, lookback=lookback)
        for st in STRATEGY_TYPES
    ]

    # sharpe 기준 정렬, 동률이면 mdd 낮은 것
    ranked = sorted(
        results,
        key=lambda r: (r["sharpe"], -r["mdd"]),
        reverse=True,
    )
    best = ranked[0]

    return {
        "ticker":            ticker,
        "as_of":             as_of,
        "results":           ranked,
        "best":              best,
        "selected_strategy": best["strategy"],
        "data_source":       best.get("data_source", "real"),
    }


# ─── strategy_memory 영속 저장/로드 ──────────────────────────────────────────

def save_sim_result(sim: dict) -> None:
    """results/strategy_memory.json 에 ticker+date 기준으로 저장."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if STRATEGY_MEM_PATH.exists():
        mem = json.loads(STRATEGY_MEM_PATH.read_text())
    else:
        mem = {}

    key = f"{sim['ticker']}_{sim['as_of']}"
    mem[key] = sim
    STRATEGY_MEM_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False))


def load_sim_history(ticker: str, as_of: str, n: int = 4) -> list[dict]:
    """
    as_of 이전 ticker의 시뮬 결과를 최신순 최대 n개 반환.
    point-in-time 안전.
    """
    if not STRATEGY_MEM_PATH.exists():
        return []

    mem = json.loads(STRATEGY_MEM_PATH.read_text())
    records = [
        v for k, v in mem.items()
        if v.get("ticker") == ticker and v.get("as_of", "") < as_of
    ]
    return sorted(records, key=lambda r: r["as_of"], reverse=True)[:n]


# ─── Portfolio Manager 프롬프트 포맷 ─────────────────────────────────────────

def format_sim_for_prompt(sim_results: dict[str, dict]) -> str:
    """
    {ticker: sim_result, ...} → Portfolio Manager 프롬프트 삽입용 텍스트.
    sim_results가 비어있으면 빈 문자열.
    """
    if not sim_results:
        return ""

    lines = ["=== BOB SIMULATION (전략 백테스트) ===", ""]
    for ticker, sim in sim_results.items():
        best = sim.get("best", {})
        strategy = sim.get("selected_strategy", "?")
        src = sim.get("data_source", "?")
        note = sim.get("note", "")

        lines.append(f"[{ticker}]  선택 전략: {strategy}  (data: {src})")
        if best and best.get("n_bars", 0) >= MIN_BARS:
            lines.append(
                f"  수익률 {best['return']*100:.1f}%  "
                f"Sharpe {best['sharpe']:.2f}  "
                f"MDD {best['mdd']*100:.1f}%  "
                f"Win {best['win_rate']*100:.0f}%"
            )

            # 과거 이력 streak
            history = load_sim_history(ticker, sim["as_of"], n=3)
            if history:
                prev_strategies = [h["selected_strategy"] for h in history]
                if all(s == strategy for s in prev_strategies):
                    lines.append(f"  ※ {len(prev_strategies)+1}주 연속 {strategy} 선택")

        if note:
            lines.append(f"  ⚠️  {note}")

        # 전략별 순위 간략히
        results = sim.get("results", [])
        if len(results) > 1:
            ranking = "  전략 순위: " + " > ".join(
                f"{r['strategy']}({r['sharpe']:.2f})" for r in results[:3]
            )
            lines.append(ranking)
        lines.append("")

    lines.append("=== END BOB SIMULATION ===")
    return "\n".join(lines)
