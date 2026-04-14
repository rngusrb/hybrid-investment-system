"""
scripts/run_loop.py — 날짜 범위 반복 실행 루프

각 주기마다 포트폴리오 파이프라인(B/C)을 실행하고 결과를 저장한다.
저장된 결과는 Phase 2(메모리)에서 다음 주기에 주입된다.

사용법:
    python scripts/run_loop.py AAPL NVDA TSLA --start 2024-01-01 --end 2024-03-31
    python scripts/run_loop.py AAPL --start 2024-01-01 --end 2024-06-30 --freq daily
    python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-06-30 --resume
    python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-06-30 --dry-run
"""
import argparse
import json
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / "results"
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()


# ─── 날짜 생성 ─────────────────────────────────────────────────────────────

def generate_dates(start: str, end: str, freq: str = "weekly") -> list[str]:
    """
    start ~ end 범위에서 실행 날짜 목록 생성.
    freq="weekly" → 매주 금요일
    freq="daily"  → 월~금 (주말 제외)
    """
    d_start = date.fromisoformat(start)
    d_end   = date.fromisoformat(end)

    dates = []
    cur = d_start

    if freq == "weekly":
        # 시작일을 포함하는 주의 금요일로 이동
        days_to_friday = (4 - cur.weekday()) % 7
        cur = cur + timedelta(days=days_to_friday)
        while cur <= d_end:
            dates.append(cur.isoformat())
            cur += timedelta(weeks=1)
    elif freq == "daily":
        while cur <= d_end:
            if cur.weekday() < 5:  # 월(0)~금(4)
                dates.append(cur.isoformat())
            cur += timedelta(days=1)
    else:
        raise ValueError(f"freq는 'weekly' 또는 'daily'만 지원: {freq}")

    return dates


# ─── 결과 저장/로드 ─────────────────────────────────────────────────────────

def result_path(run_date: str) -> Path:
    return RESULTS_DIR / run_date / "portfolio.json"


def save_result(run_date: str, data: dict) -> Path:
    path = result_path(run_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_result(run_date: str) -> dict | None:
    path = result_path(run_date)
    if path.exists():
        return json.loads(path.read_text())
    return None


def list_saved_dates() -> list[str]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(
        d.name for d in RESULTS_DIR.iterdir()
        if d.is_dir() and (d / "portfolio.json").exists()
    )


# ─── 단일 주기 실행 ─────────────────────────────────────────────────────────

def run_one_cycle(run_date: str, tickers: list[str], llm, llm_decision) -> dict:
    """
    한 날짜에 대해 전체 파이프라인(B+C) 실행.
    memory/run_memory.py 에서 이전 주기 컨텍스트를 자동 로드해 Portfolio Manager에 주입.
    """
    from memory.outcome_filler import fill_pending_outcomes
    filled = fill_pending_outcomes(run_date)
    if filled:
        print(f"    [r_real] {len(filled)}개 결과 업데이트: {list(filled.keys())}")

    from scripts.portfolio_pipeline import run_single_stock, run_portfolio_manager
    from memory.run_memory import get_context_prompt, find_prev_dates

    # 이전 주기 컨텍스트 로드 (results/ 기반)
    memory_context = get_context_prompt(run_date, lookback=3)
    prev_dates = find_prev_dates(run_date, n=1)
    prev_date  = prev_dates[0] if prev_dates else None

    if memory_context:
        print(f"    [Memory] 이전 주기 {prev_date} 컨텍스트 로드됨")
    else:
        print(f"    [Memory] 이전 주기 없음 (첫 실행)")

    from simulation.backtester import backtest_all, save_sim_result, format_sim_for_prompt
    from meetings.run_meetings import run_all_meetings, format_meetings_for_prompt
    from calibration.run_calibration import run_calibration_audit, format_calibration_for_prompt

    stock_results = []
    errors = []

    for ticker in tickers:
        try:
            result = run_single_stock(ticker, run_date, llm, llm_decision)
            stock_results.append(result)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})
            print(f"    [{ticker}] ❌ {str(e)[:80]}")

    # Bob 시뮬레이션 — 각 종목 bars로 전략 Pool 백테스트
    sim_results = {}
    for r in stock_results:
        ticker = r["ticker"]
        bars   = r.get("bars", [])
        try:
            sim = backtest_all(bars, ticker=ticker, as_of=run_date)
            save_sim_result(sim)
            sim_results[ticker] = sim
            strat = sim["selected_strategy"]
            sharpe = sim["best"].get("sharpe", 0)
            print(f"    [Bob/{ticker}] {strat}  Sharpe={sharpe:.2f}")
        except Exception as e:
            errors.append({"ticker": f"sim_{ticker}", "error": str(e)})
            print(f"    [Bob/{ticker}] ❌ {str(e)[:80]}")

    sim_context = format_sim_for_prompt(sim_results)

    # 3 Meetings (MAM/SDM/RAM)
    meetings = {}
    meetings_context = ""
    try:
        meetings = run_all_meetings(stock_results, sim_results, run_date)
        meetings_context = format_meetings_for_prompt(meetings)
        ram = meetings.get("ram", {})
        if meetings.get("ram_triggered"):
            print(f"    [RAM] ⚠️  리스크 경보: {ram.get('high_risk_tickers')}  "
                  f"조치: {ram.get('emergency_controls')}")
        else:
            print(f"    [RAM] 정상 (max_risk={ram.get('max_risk_score', 0):.2f})")
    except Exception as e:
        errors.append({"ticker": "meetings", "error": str(e)})
        print(f"    [Meetings] ❌ {str(e)[:80]}")

    # Calibration / Audit / Reliability (Phase 5)
    cal_result = {}
    calibration_context = ""
    try:
        cal_result = run_calibration_audit(stock_results, sim_results, run_date)
        calibration_context = format_calibration_for_prompt(cal_result)
        flags = cal_result.get("flags", [])
        gating = cal_result.get("gating_decisions", {})
        hard_gated = [a for a, g in gating.items() if g == "hard_gate"]
        if hard_gated:
            print(f"    [CAL] ⚠️  HARD_GATE: {hard_gated}")
        if flags:
            for flag in flags[:3]:
                print(f"    [CAL] {flag}")
    except Exception as e:
        errors.append({"ticker": "calibration", "error": str(e)})
        print(f"    [CAL] ❌ {str(e)[:80]}")

    portfolio = {}
    if stock_results:
        try:
            portfolio = run_portfolio_manager(
                llm_decision, run_date, stock_results,
                memory_context=memory_context,
                sim_context=sim_context,
                meetings_context=meetings_context,
                calibration_context=calibration_context,
            )
        except Exception as e:
            errors.append({"ticker": "portfolio", "error": str(e)})
            print(f"    [Portfolio] ❌ {str(e)[:80]}")

    return {
        "date":          run_date,
        "tickers":       tickers,
        "stock_results": stock_results,
        "portfolio":     portfolio,
        "meetings":      meetings,
        "calibration":   cal_result,
        "errors":        errors,
        "prev_date":     prev_date,
    }


# ─── 루프 요약 출력 ─────────────────────────────────────────────────────────

def print_cycle_summary(run_date: str, result: dict, elapsed: float):
    portfolio = result.get("portfolio", {})
    errors    = result.get("errors", [])
    allocs    = portfolio.get("allocations", [])

    status = "✅" if not errors else f"⚠️ ({len(errors)} 오류)"
    print(f"\n  {status}  {run_date}  [{elapsed:.0f}s]")

    if allocs:
        line = "  ".join(
            f"{a['ticker']} {a['action']} {a['weight']*100:.0f}%"
            for a in sorted(allocs, key=lambda x: x.get("weight", 0), reverse=True)
        )
        cash  = portfolio.get("cash_pct", 0) * 100
        hedge = portfolio.get("hedge_pct", 0) * 100
        print(f"    {line}  | 현금 {cash:.0f}%  헤지 {hedge:.0f}%")


def print_loop_summary(dates: list[str], successes: list[str],
                       failures: list[str], skipped: list[str]):
    total = len(dates)
    print(f"\n{'='*65}")
    print(f"  루프 완료: {total}개 주기")
    print(f"  ✅ 성공: {len(successes)}  ❌ 실패: {len(failures)}  ⏭ 스킵: {len(skipped)}")
    if failures:
        print(f"\n  실패 날짜:")
        for d in failures:
            print(f"    · {d}")
    print(f"\n  결과 저장: {RESULTS_DIR}/")
    print(f"{'='*65}\n")


# ─── 메인 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="날짜 범위 반복 실행 루프")
    parser.add_argument("tickers", nargs="+", help="종목 티커 목록 (예: AAPL NVDA TSLA)")
    parser.add_argument("--start",   required=True, help="시작일 YYYY-MM-DD")
    parser.add_argument("--end",     required=True, help="종료일 YYYY-MM-DD")
    parser.add_argument("--freq",    default="weekly", choices=["weekly", "daily"],
                        help="실행 주기 (weekly=매주 금요일, daily=매 영업일, 기본: weekly)")
    parser.add_argument("--resume",  action="store_true",
                        help="이미 저장된 날짜는 스킵")
    parser.add_argument("--dry-run", action="store_true",
                        help="실행 날짜만 출력, 실제 실행 안 함")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    dates   = generate_dates(args.start, args.end, args.freq)

    print(f"\n{'='*65}")
    print(f"  Run Loop — {args.freq.upper()}")
    print(f"  종목:  {', '.join(tickers)}")
    print(f"  기간:  {args.start} ~ {args.end}  ({len(dates)}개 주기)")
    print(f"  저장:  {RESULTS_DIR}/")
    if args.resume:
        print(f"  모드:  resume (기존 결과 스킵)")
    if args.dry_run:
        print(f"  모드:  dry-run")
    print(f"{'='*65}")

    # dry-run
    if args.dry_run:
        print("\n  실행 예정 날짜:")
        for d in dates:
            saved = "  [저장됨]" if load_result(d) else ""
            print(f"    {d}{saved}")
        print()
        return

    from llm.factory import create_provider
    llm          = create_provider(node_role="analyst")
    llm_decision = create_provider(node_role="decision")

    successes = []
    failures  = []
    skipped   = []
    prev_result = None

    for i, run_date in enumerate(dates, 1):
        print(f"\n[{i}/{len(dates)}] {run_date}")

        # resume: 이미 저장된 날짜 스킵
        if args.resume and load_result(run_date):
            print(f"  ⏭ 스킵 (이미 저장됨)")
            prev_result = load_result(run_date)
            skipped.append(run_date)
            continue

        t0 = time.time()
        try:
            result  = run_one_cycle(run_date, tickers, llm, llm_decision)
            path    = save_result(run_date, result)
            elapsed = time.time() - t0

            print_cycle_summary(run_date, result, elapsed)
            print(f"    저장: {path.relative_to(ROOT)}")

            prev_result = result
            successes.append(run_date)

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ❌ 실패 ({elapsed:.0f}s): {str(e)[:100]}")
            traceback.print_exc()
            failures.append(run_date)
            # 실패해도 루프 계속

    print_loop_summary(dates, successes, failures, skipped)


if __name__ == "__main__":
    main()
