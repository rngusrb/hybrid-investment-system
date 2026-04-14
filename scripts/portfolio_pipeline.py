"""
portfolio_pipeline.py — 멀티 종목 포트폴리오 분석 파이프라인

사용법:
    python scripts/portfolio_pipeline.py AAPL NVDA TSLA
    python scripts/portfolio_pipeline.py AAPL NVDA --date 2024-01-15
    python scripts/portfolio_pipeline.py AAPL NVDA MSFT GOOGL --date 2024-06-01 --verbose
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

# stock_pipeline 함수 재사용
from scripts.stock_pipeline import (
    fetch_data,
    run_fundamental, run_sentiment, run_news, run_technical,
    run_researcher, run_trader, run_risk_manager,
)


# ──────────────────────────────────────────
# 단일 종목 전체 파이프라인 실행
# ──────────────────────────────────────────

def run_single_stock(ticker: str, date: str, llm, llm_decision) -> dict:
    """한 종목에 대해 전체 파이프라인(fetch → Risk Manager)을 실행하고 결과 반환."""
    print(f"  [{ticker}] 데이터 수집 중...")
    data = fetch_data(ticker, date)
    print(f"    OHLCV {len(data['bars'])}봉 | 뉴스 {len(data['articles'])}건 | 재무 {len(data['financials'])}년")

    print(f"  [{ticker}] Fundamental Analyst...")
    fundamental = run_fundamental(llm, data)

    print(f"  [{ticker}] Sentiment Analyst...")
    sentiment = run_sentiment(llm, data)

    print(f"  [{ticker}] News Analyst...")
    news = run_news(llm, data)

    print(f"  [{ticker}] Technical Analyst...")
    technical = run_technical(llm, data)

    print(f"  [{ticker}] Researcher (Bull/Bear)...")
    researcher = run_researcher(llm, ticker, date, fundamental, sentiment, news, technical)

    print(f"  [{ticker}] Trader...")
    trader = run_trader(llm_decision, ticker, date, data["current_price"],
                        fundamental, sentiment, news, technical, researcher)

    print(f"  [{ticker}] Risk Manager...")
    risk_mgr = run_risk_manager(llm_decision, ticker, date, data["current_price"],
                                trader, fundamental, sentiment, news, technical, researcher)

    return {
        "ticker":        ticker,
        "current_price": data["current_price"],
        "bars":          data.get("bars", []),   # backtester용
        "fundamental":   fundamental,
        "sentiment":     sentiment,
        "news":          news,
        "technical":     technical,
        "researcher":    researcher,
        "trader":        trader,
        "risk_manager":  risk_mgr,
    }


# ──────────────────────────────────────────
# Portfolio Manager LLM 호출
# ──────────────────────────────────────────

def run_portfolio_manager(llm_decision, date: str, stock_results: list[dict],
                          memory_context: str = "",
                          sim_context: str = "",
                          meetings_context: str = "",
                          calibration_context: str = "") -> dict:
    from schemas.portfolio_schemas import PortfolioManagerOutput

    system = (ROOT / "prompts/portfolio_manager_system.md").read_text().replace(
        "{n_stocks}", str(len(stock_results))
    )

    # 각 종목 signal 요약
    signals = []
    for r in stock_results:
        t  = r["ticker"]
        rm = r["risk_manager"]
        tr = r["trader"]
        fu = r["fundamental"]
        te = r["technical"]
        signals.append(f"""
--- {t} (현재가: ${r['current_price']}) ---
Trader 초안:    {tr.get('action')} | confidence={tr.get('confidence')} | position={tr.get('position_size_pct',0)*100:.1f}%
Risk Manager:  {rm.get('final_action')} | risk_level={rm.get('risk_level')} | final_position={rm.get('final_position_size_pct',0)*100:.1f}%
  action_changed={rm.get('action_changed')} | cash_reserve={rm.get('cash_reserve_pct',0)*100:.1f}%
  hedge={rm.get('hedge_type')} | risk_flags={rm.get('risk_flags')}
Fundamental:   score={fu.get('fundamental_score')} | value={fu.get('intrinsic_value_signal')} | PE={fu.get('pe_ratio')}
Technical:     score={te.get('technical_score')} | trend={te.get('trend_direction')} | RSI={te.get('rsi')}
Researcher:    consensus={r['researcher'].get('consensus')} | conviction={r['researcher'].get('conviction')} | rr={r['researcher'].get('risk_reward_ratio')}
""")

    memory_section      = f"\n{memory_context}\n"      if memory_context      else ""
    sim_section         = f"\n{sim_context}\n"         if sim_context         else ""
    meetings_section    = f"\n{meetings_context}\n"    if meetings_context    else ""
    calibration_section = f"\n{calibration_context}\n" if calibration_context else ""
    user = f"""
Date: {date}
Tickers: {[r['ticker'] for r in stock_results]}
{memory_section}{sim_section}{meetings_section}{calibration_section}
=== INDIVIDUAL STOCK SIGNALS ===
{"".join(signals)}

Allocate the portfolio across these stocks, cash, and hedge. Return JSON.
"""

    for attempt in range(3):
        raw = llm_decision.chat(
            messages=[{"role": "user", "content": user}],
            system=system,
        )
        text = raw if isinstance(raw, str) else str(raw)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group())
            obj  = PortfolioManagerOutput(**data)
            return obj.model_dump()
        except Exception:
            continue
    return {}


# ──────────────────────────────────────────
# 출력
# ──────────────────────────────────────────

def print_portfolio_results(date: str, stock_results: list[dict],
                            portfolio: dict, verbose: bool = False):
    def sep(title):
        print(f"\n{'='*65}")
        print(f"  {title}")
        print(f"{'='*65}")

    sep(f"포트폴리오 분석  ({date})")

    if verbose:
        sep("개별 종목 요약")
        for r in stock_results:
            t  = r["ticker"]
            rm = r["risk_manager"]
            icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(rm.get("final_action"), "⚪")
            changed = " ← 변경" if rm.get("action_changed") else ""
            print(f"\n  {icon} {t:6s}  {rm.get('final_action'):4s}{changed}")
            print(f"       포지션 {rm.get('final_position_size_pct',0)*100:.1f}% | "
                  f"리스크 {rm.get('risk_level','?').upper()} | "
                  f"현금 {rm.get('cash_reserve_pct',0)*100:.1f}%")
            flags = rm.get("risk_flags", [])
            if flags:
                print(f"       ⚠️  {', '.join(flags)}")

    sep("Portfolio Manager 최종 배분")

    allocations = portfolio.get("allocations", [])
    print(f"\n  {'종목':<8} {'비중':>6}  {'결정':>5}  근거")
    print(f"  {'-'*60}")
    for a in sorted(allocations, key=lambda x: x.get("weight", 0), reverse=True):
        icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(a.get("action"), "⚪")
        w    = a.get("weight", 0) * 100
        print(f"  {icon} {a.get('ticker'):<6}  {w:>5.1f}%  {a.get('action'):>4}  {a.get('rationale','')[:50]}")

    print(f"\n  {'─'*60}")
    eq   = portfolio.get("total_equity_pct", 0) * 100
    cash = portfolio.get("cash_pct", 0) * 100
    hedge= portfolio.get("hedge_pct", 0) * 100
    print(f"  주식 합계:  {eq:>5.1f}%")
    print(f"  현금:       {cash:>5.1f}%")
    hedge_inst = portfolio.get("hedge_instrument", "none")
    if hedge_inst != "none":
        print(f"  헤지({hedge_inst}): {hedge:>5.1f}%")
    print(f"  {'─'*60}")
    print(f"  합계:       {eq+cash+hedge:>5.1f}%")

    print(f"\n  포트폴리오 리스크:  {portfolio.get('portfolio_risk_level','?').upper()}")
    print(f"  분산도:            {portfolio.get('diversification_score',0):.2f}")
    print(f"  집중 리스크:       {'있음 ⚠️' if portfolio.get('concentration_risk') else '없음'}")
    print(f"  리밸런싱 긴급도:   {portfolio.get('rebalance_urgency','?')}")
    print(f"  진입 방식:         {portfolio.get('entry_style','?')}")

    print(f"\n  시장 전망: {portfolio.get('market_outlook','')}")

    risks = portfolio.get("key_risks", [])
    if risks:
        print(f"\n  핵심 리스크:")
        for r in risks:
            print(f"    · {r}")

    reasoning = portfolio.get("reasoning", [])
    if reasoning:
        print(f"\n  판단 근거:")
        for r in reasoning:
            print(f"    → {r}")

    print(f"\n{'='*65}\n")


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="멀티 종목 포트폴리오 분석 파이프라인")
    parser.add_argument("tickers", nargs="+", help="종목 티커 목록 (예: AAPL NVDA TSLA)")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 (YYYY-MM-DD, 기본값: 오늘)")
    parser.add_argument("--verbose", action="store_true", help="개별 종목 상세 출력")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    date    = args.date

    print(f"\n포트폴리오 분석 시작: {tickers}  ({date})")
    print(f"{'='*65}")

    from llm.factory import create_provider
    llm          = create_provider(node_role="analyst")
    llm_decision = create_provider(node_role="decision")

    # 종목별 순차 실행
    stock_results = []
    for ticker in tickers:
        print(f"\n[{ticker}] 분석 시작...")
        result = run_single_stock(ticker, date, llm, llm_decision)
        stock_results.append(result)
        print(f"  [{ticker}] 완료 ✓")

    print(f"\n[Portfolio Manager] 최종 배분 결정 중...")
    portfolio = run_portfolio_manager(llm_decision, date, stock_results)

    print_portfolio_results(date, stock_results, portfolio, verbose=args.verbose)


if __name__ == "__main__":
    main()
