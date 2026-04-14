"""
scripts/live_e2e_bc_test.py

파이프라인 B/C 실제 실행 검증 (LLM + Polygon API).
fetch_data → 4 Analysts → Researcher → Trader → Risk Manager → Portfolio Manager

실행:
    python scripts/live_e2e_bc_test.py
    python scripts/live_e2e_bc_test.py --tickers AAPL NVDA --date 2024-01-15
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

# ─── 기본 설정 ────────────────────────────────────────────────
DEFAULT_TICKERS = ["AAPL"]
DEFAULT_DATE    = "2024-01-15"
# ─────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def record(step: str, ok: bool, detail: str = ""):
    tag = PASS if ok else FAIL
    results.append((step, tag, detail))
    print(f"  {tag}  {step}" + (f"  — {detail}" if detail else ""))


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main(tickers: list[str], date: str):
    from llm.factory import create_provider
    from scripts.stock_pipeline import (
        fetch_data, run_fundamental, run_sentiment,
        run_news, run_technical, run_researcher,
        run_trader, run_risk_manager,
    )
    from scripts.portfolio_pipeline import run_portfolio_manager

    llm          = create_provider(node_role="analyst")
    llm_decision = create_provider(node_role="decision")

    all_results = []

    for ticker in tickers:

        # ════════════════════════════════════════════════════
        # STEP 1: fetch_data
        # ════════════════════════════════════════════════════
        section(f"STEP 1 · fetch_data [{ticker}] {date}")
        t0 = time.time()
        try:
            data = fetch_data(ticker, date)
            elapsed = time.time() - t0

            record(f"[{ticker}] fetch_data 성공",       True, f"{elapsed:.1f}s")
            record(f"[{ticker}] OHLCV bars",            len(data.get("bars", [])) >= 10,
                   f"{len(data.get('bars', []))}개 봉")
            record(f"[{ticker}] 뉴스 articles",         len(data.get("articles", [])) >= 0,
                   f"{len(data.get('articles', []))}건")
            record(f"[{ticker}] current_price 존재",    data.get("current_price") is not None,
                   f"${data.get('current_price', 0):.2f}")

            # 재무제표 룩어헤드 체크
            fin_ok = True
            for f in data.get("financials", []):
                if "error" in f:
                    continue
                filed = f.get("filed", "")
                end   = (f.get("period", "") or "").split(" ~ ")[-1]
                if (filed and filed > date) or (end and end > date):
                    fin_ok = False
            record(f"[{ticker}] 재무제표 룩어헤드 없음", fin_ok,
                   f"{len(data.get('financials', []))}건, filed≤{date}")

        except Exception as e:
            record(f"[{ticker}] fetch_data 성공", False, str(e)[:100])
            continue

        # ════════════════════════════════════════════════════
        # STEP 2: 4 Analysts
        # ════════════════════════════════════════════════════
        section(f"STEP 2 · 4 Analysts [{ticker}]")

        fundamental = {}
        try:
            t0 = time.time()
            fundamental = run_fundamental(llm, data)
            elapsed = time.time() - t0
            record(f"[{ticker}] Fundamental",
                   bool(fundamental.get("fundamental_score") is not None),
                   f"score={fundamental.get('fundamental_score'):.2f}  {elapsed:.1f}s")
        except Exception as e:
            record(f"[{ticker}] Fundamental", False, str(e)[:100])

        sentiment = {}
        try:
            t0 = time.time()
            sentiment = run_sentiment(llm, data)
            elapsed = time.time() - t0
            record(f"[{ticker}] Sentiment",
                   bool(sentiment.get("sentiment_score") is not None),
                   f"score={sentiment.get('sentiment_score'):.2f}  emotion={sentiment.get('dominant_emotion')}  {elapsed:.1f}s")
        except Exception as e:
            record(f"[{ticker}] Sentiment", False, str(e)[:100])

        news_out = {}
        try:
            t0 = time.time()
            news_out = run_news(llm, data)
            elapsed = time.time() - t0
            record(f"[{ticker}] News",
                   bool(news_out.get("macro_impact") is not None),
                   f"macro={news_out.get('macro_impact'):.2f}  event_risk={news_out.get('event_risk_level'):.2f}  {elapsed:.1f}s")
        except Exception as e:
            record(f"[{ticker}] News", False, str(e)[:100])

        technical = {}
        try:
            t0 = time.time()
            technical = run_technical(llm, data)
            elapsed = time.time() - t0
            record(f"[{ticker}] Technical",
                   bool(technical.get("technical_score") is not None),
                   f"score={technical.get('technical_score'):.2f}  signal={technical.get('entry_signal')}  {elapsed:.1f}s")
        except Exception as e:
            record(f"[{ticker}] Technical", False, str(e)[:100])

        # ════════════════════════════════════════════════════
        # STEP 3: Researcher
        # ════════════════════════════════════════════════════
        section(f"STEP 3 · Researcher [{ticker}]")

        researcher = {}
        try:
            t0 = time.time()
            researcher = run_researcher(llm, ticker, date,
                                        fundamental, sentiment, news_out, technical)
            elapsed = time.time() - t0
            record(f"[{ticker}] Researcher",
                   bool(researcher.get("consensus")),
                   f"consensus={researcher.get('consensus')}  conviction={researcher.get('conviction'):.2f}  {elapsed:.1f}s")
            record(f"[{ticker}] Researcher bull_thesis 존재",
                   bool(researcher.get("bull_thesis")))
            record(f"[{ticker}] Researcher bear_thesis 존재",
                   bool(researcher.get("bear_thesis")))
        except Exception as e:
            record(f"[{ticker}] Researcher", False, str(e)[:100])

        # ════════════════════════════════════════════════════
        # STEP 4: Trader
        # ════════════════════════════════════════════════════
        section(f"STEP 4 · Trader [{ticker}]")

        trader = {}
        try:
            t0 = time.time()
            trader = run_trader(llm_decision, ticker, date, data["current_price"],
                                fundamental, sentiment, news_out, technical, researcher)
            elapsed = time.time() - t0
            record(f"[{ticker}] Trader",
                   trader.get("action") in ("BUY", "SELL", "HOLD"),
                   f"action={trader.get('action')}  conf={trader.get('confidence'):.2f}  {elapsed:.1f}s")
            record(f"[{ticker}] Trader target_price",
                   trader.get("target_price") is not None,
                   f"target=${trader.get('target_price')}  stop=${trader.get('stop_loss_price')}")
        except Exception as e:
            record(f"[{ticker}] Trader", False, str(e)[:100])

        # ════════════════════════════════════════════════════
        # STEP 5: Risk Manager
        # ════════════════════════════════════════════════════
        section(f"STEP 5 · Risk Manager [{ticker}]")

        risk_mgr = {}
        try:
            t0 = time.time()
            risk_mgr = run_risk_manager(llm_decision, ticker, date, data["current_price"],
                                        trader, fundamental, sentiment, news_out, technical, researcher)
            elapsed = time.time() - t0
            record(f"[{ticker}] Risk Manager",
                   risk_mgr.get("final_action") in ("BUY", "SELL", "HOLD"),
                   f"final={risk_mgr.get('final_action')}  risk={risk_mgr.get('risk_level')}  {elapsed:.1f}s")
            record(f"[{ticker}] action_changed 필드",
                   "action_changed" in risk_mgr,
                   f"changed={risk_mgr.get('action_changed')}")
            record(f"[{ticker}] risk_flags 존재",
                   isinstance(risk_mgr.get("risk_flags"), list))
        except Exception as e:
            record(f"[{ticker}] Risk Manager", False, str(e)[:100])

        all_results.append({
            "ticker":        ticker,
            "current_price": data["current_price"],
            "bars":          data["bars"],
            "articles":      data["articles"],
            "financials":    data["financials"],
            "fundamental":   fundamental,
            "sentiment":     sentiment,
            "news":          news_out,
            "technical":     technical,
            "researcher":    researcher,
            "trader":        trader,
            "risk_manager":  risk_mgr,
        })

    # ════════════════════════════════════════════════════════
    # STEP 6: Portfolio Manager (멀티 종목일 때만)
    # ════════════════════════════════════════════════════════
    if len(tickers) > 1 or True:  # 단일 종목도 portfolio 검증
        section(f"STEP 6 · Portfolio Manager [{', '.join(tickers)}]")
        try:
            t0 = time.time()
            portfolio = run_portfolio_manager(llm_decision, date, all_results)
            elapsed = time.time() - t0

            allocs = portfolio.get("allocations", [])
            total_eq = portfolio.get("total_equity_pct", 0)
            cash     = portfolio.get("cash_pct", 0)
            hedge    = portfolio.get("hedge_pct", 0)
            total    = round(total_eq + cash + hedge, 4)

            record("Portfolio Manager 성공",       bool(allocs), f"{elapsed:.1f}s")
            record("allocations 종목 수 일치",      len(allocs) == len(tickers),
                   f"{len(allocs)}개 배분")
            record("합계 ≈ 1.0 (equity+cash+hedge)", abs(total - 1.0) < 0.05,
                   f"equity={total_eq:.2f} cash={cash:.2f} hedge={hedge:.2f} 합={total:.2f}")

            print(f"\n  📊 Portfolio 배분:")
            for a in sorted(allocs, key=lambda x: x.get("weight", 0), reverse=True):
                print(f"     {a['ticker']:6s}  {a['action']:4s}  {a['weight']*100:.1f}%")
            print(f"     현금 {cash*100:.1f}%  헤지 {hedge*100:.1f}%")
        except Exception as e:
            record("Portfolio Manager 성공", False, str(e)[:100])

    # ════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ════════════════════════════════════════════════════════
    section("FINAL RESULTS")
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total  = len(results)

    col_w = max(len(r[0]) for r in results) + 2
    print(f"\n  {'체크':<{col_w}} {'결과':<10} 상세")
    print(f"  {'-'*(col_w+70)}")
    for step, status, detail in results:
        print(f"  {step:<{col_w}} {status:<10} {detail[:60]}")

    print(f"\n  {'─'*(col_w+70)}")
    print(f"  총 {total}개   {PASS} {passed}개   {FAIL} {failed}개")
    print()

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--date",    default=DEFAULT_DATE)
    args = parser.parse_args()

    ok = main(args.tickers, args.date)
    sys.exit(0 if ok else 1)
