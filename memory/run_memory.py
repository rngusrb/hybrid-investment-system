"""
memory/run_memory.py — 루프 실행 결과 기반 영속 메모리

results/ 디렉토리에 저장된 이전 주기 결과를 로드하여
현재 주기 파이프라인에 컨텍스트로 주입한다.

기존 memory/ (Pipeline A, in-memory)와 별개.
이 모듈은 run_loop.py → portfolio_pipeline.py 경로에서만 사용.
"""
import json
from datetime import date as _date
from pathlib import Path
from typing import Optional


RESULTS_DIR = Path(__file__).parent.parent / "results"


# ─── 이전 결과 탐색 ─────────────────────────────────────────────────────────

def find_prev_dates(current_date: str, n: int = 3) -> list[str]:
    """
    current_date 이전에 저장된 결과 날짜를 최신순으로 최대 n개 반환.
    point-in-time 안전: current_date 포함 이후 데이터는 절대 반환 안 함.
    """
    if not RESULTS_DIR.exists():
        return []

    cutoff = _date.fromisoformat(current_date)
    saved = sorted(
        d.name for d in RESULTS_DIR.iterdir()
        if d.is_dir() and (d / "portfolio.json").exists()
    )
    prev = [d for d in saved if _date.fromisoformat(d) < cutoff]
    return list(reversed(prev))[:n]  # 최신순


def load_result(run_date: str) -> Optional[dict]:
    path = RESULTS_DIR / run_date / "portfolio.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


# ─── 컨텍스트 구성 ───────────────────────────────────────────────────────────

def build_context(prev_results: list[dict]) -> dict:
    """
    이전 결과 목록 → 구조화된 컨텍스트.
    가장 최신 결과를 primary로, 나머지는 trend 파악용.
    """
    if not prev_results:
        return {}

    primary = prev_results[0]
    portfolio = primary.get("portfolio", {})
    stock_results = primary.get("stock_results", [])

    # 종목별 이전 신호 요약
    ticker_signals = {}
    for r in stock_results:
        ticker = r.get("ticker", "")
        rm = r.get("risk_manager", {})
        tr = r.get("trader", {})
        res = r.get("researcher", {})
        ticker_signals[ticker] = {
            "action":       rm.get("final_action") or tr.get("action"),
            "risk_level":   rm.get("risk_level"),
            "conviction":   res.get("conviction"),
            "action_changed": rm.get("action_changed", False),
            "risk_flags":   rm.get("risk_flags", []),
        }

    # 연속 동일 액션 카운트 (trend 파악)
    consecutive = {}
    for sig in ticker_signals:
        action = ticker_signals[sig]["action"]
        count = 1
        for old in prev_results[1:]:
            old_stocks = {r["ticker"]: r for r in old.get("stock_results", [])}
            if sig in old_stocks:
                old_rm = old_stocks[sig].get("risk_manager", {})
                old_action = old_rm.get("final_action") or old_stocks[sig].get("trader", {}).get("action")
                if old_action == action:
                    count += 1
                else:
                    break
        consecutive[sig] = count

    return {
        "prev_date":       primary.get("date"),
        "prev_allocation": portfolio.get("allocations", []),
        "prev_cash_pct":   portfolio.get("cash_pct", 0),
        "prev_hedge_pct":  portfolio.get("hedge_pct", 0),
        "prev_risk_level": portfolio.get("portfolio_risk_level"),
        "prev_outlook":    portfolio.get("market_outlook"),
        "ticker_signals":  ticker_signals,
        "consecutive":     consecutive,
        "prev_errors":     primary.get("errors", []),
    }


def format_context_for_prompt(ctx: dict) -> str:
    """컨텍스트 → Portfolio Manager 프롬프트에 삽입할 텍스트."""
    if not ctx:
        return ""

    lines = [
        f"=== MEMORY CONTEXT (이전 주기: {ctx['prev_date']}) ===",
        "",
        "이전 포트폴리오 배분:",
    ]

    for alloc in ctx.get("prev_allocation", []):
        ticker = alloc.get("ticker", "")
        weight = alloc.get("weight", 0) * 100
        action = alloc.get("action", "")
        consec = ctx["consecutive"].get(ticker, 1)
        streak = f" ({consec}주 연속)" if consec > 1 else ""
        lines.append(f"  {ticker}: {action} {weight:.1f}%{streak}")

    cash  = ctx.get("prev_cash_pct", 0) * 100
    hedge = ctx.get("prev_hedge_pct", 0) * 100
    lines.append(f"  현금: {cash:.1f}%  헤지: {hedge:.1f}%")
    lines.append(f"  포트폴리오 리스크: {ctx.get('prev_risk_level', '?')}")
    lines.append(f"  시장 전망: {ctx.get('prev_outlook', '?')}")

    changed = [t for t, s in ctx["ticker_signals"].items() if s.get("action_changed")]
    if changed:
        lines.append(f"\n⚠️  지난 주기에 리스크 매니저가 액션을 변경한 종목: {', '.join(changed)}")

    flagged = {t: s["risk_flags"] for t, s in ctx["ticker_signals"].items() if s.get("risk_flags")}
    if flagged:
        lines.append("\n리스크 플래그:")
        for t, flags in flagged.items():
            lines.append(f"  {t}: {', '.join(flags)}")

    errors = ctx.get("prev_errors", [])
    if errors:
        lines.append(f"\n지난 주기 오류: {len(errors)}건")

    lines.append("=== END MEMORY CONTEXT ===")
    return "\n".join(lines)


# ─── 공개 인터페이스 ─────────────────────────────────────────────────────────

def load_prev_context(current_date: str, lookback: int = 3) -> dict:
    """
    current_date 이전 최대 lookback개 결과 로드 → 컨텍스트 반환.
    결과가 없으면 {} 반환.
    """
    prev_dates = find_prev_dates(current_date, n=lookback)
    if not prev_dates:
        return {}

    prev_results = []
    for d in prev_dates:
        r = load_result(d)
        if r:
            prev_results.append(r)

    return build_context(prev_results)


def get_context_prompt(current_date: str, lookback: int = 3) -> str:
    """
    current_date 이전 결과로 프롬프트 문자열 반환.
    결과 없으면 빈 문자열.
    """
    ctx = load_prev_context(current_date, lookback)
    return format_context_for_prompt(ctx)
