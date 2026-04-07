"""
stock_pipeline.py — 개별 종목 TradingAgents 파이프라인

사용법:
    python scripts/stock_pipeline.py AAPL
    python scripts/stock_pipeline.py NVDA --date 2024-06-01
    python scripts/stock_pipeline.py TSLA --date 2024-01-15 --verbose
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()


# ──────────────────────────────────────────
# 데이터 수집
# ──────────────────────────────────────────

def fetch_data(ticker: str, date: str) -> dict:
    """Polygon에서 OHLCV + 뉴스 + 재무제표 수집."""
    from data.polygon_fetcher import PolygonFetcher
    from polygon import RESTClient

    api_key = os.getenv("POLYGON_API_KEY")
    fetcher = PolygonFetcher(api_key=api_key)
    client  = RESTClient(api_key=api_key)

    dt = datetime.strptime(date, "%Y-%m-%d")
    from_date = (dt - timedelta(days=180)).strftime("%Y-%m-%d")
    news_from = (dt - timedelta(days=30)).strftime("%Y-%m-%d")

    # OHLCV
    ohlcv = fetcher.get_ohlcv(ticker, from_date, date, as_of=date)
    bars  = ohlcv.get("data", [])

    # 뉴스
    news  = fetcher.get_news(ticker, news_from, date, as_of=date, limit=30)
    articles = news.get("articles", [])

    # 현재 주가 (최신 봉)
    current_price = bars[-1]["close"] if bars else None

    # 재무제표 (Polygon vX)
    financials = []
    try:
        items = list(client.vx.list_stock_financials(ticker=ticker, limit=4, timeframe="annual"))
        for item in items[:2]:  # 최근 2년
            inc = item.financials.income_statement
            financials.append({
                "period": f"{item.start_date} ~ {item.end_date}",
                "revenue":    getattr(inc.revenues,     "value", None) if hasattr(inc, "revenues")     else None,
                "net_income": getattr(inc.net_income_loss, "value", None) if hasattr(inc, "net_income_loss") else None,
            })
    except Exception as e:
        financials = [{"error": str(e)}]

    # EPS + PE
    eps, pe_ratio = None, None
    try:
        items = list(client.vx.list_stock_financials(ticker=ticker, limit=4, timeframe="quarterly"))
        if items and current_price:
            inc = items[0].financials.income_statement
            shares = getattr(items[0].financials.balance_sheet.equity, "value", None) if hasattr(items[0].financials, "balance_sheet") else None
            diluted = None
            for attr in ["diluted_earnings_per_share", "basic_earnings_per_share"]:
                obj = getattr(inc, attr, None)
                if obj is not None:
                    diluted = getattr(obj, "value", None)
                    break
            if diluted:
                eps      = round(diluted * 4, 2)   # 연환산
                pe_ratio = round(current_price / eps, 1) if eps and eps > 0 else None
    except Exception:
        pass

    return {
        "ticker":        ticker,
        "date":          date,
        "current_price": current_price,
        "bars":          bars,
        "articles":      articles,
        "financials":    financials,
        "eps":           eps,
        "pe_ratio":      pe_ratio,
    }


# ──────────────────────────────────────────
# LLM 호출 공통
# ──────────────────────────────────────────

def call_llm(llm, system_prompt: str, user_content: str, schema_class):
    """LLM 호출 → schema 파싱 → dict 반환."""
    import re

    for attempt in range(3):
        raw = llm.chat(
            messages=[{"role": "user", "content": user_content}],
            system=system_prompt,
        )
        # JSON 추출
        text = raw if isinstance(raw, str) else str(raw)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group())
            obj  = schema_class(**data)
            return obj.model_dump()
        except Exception:
            continue
    return {}


# ──────────────────────────────────────────
# 4개 Analyst
# ──────────────────────────────────────────

def run_fundamental(llm, data: dict) -> dict:
    from schemas.stock_schemas import FundamentalAnalystOutput
    system = Path(ROOT / "prompts/fundamental_system.md").read_text().replace("{ticker}", data["ticker"])

    fin_str = json.dumps(data["financials"], indent=2)
    user = f"""
Ticker: {data['ticker']}
Date: {data['date']}
Current Price: ${data['current_price']}
EPS (annualized): {data['eps']}
P/E Ratio: {data['pe_ratio']}

Financial Statements (recent 2 years):
{fin_str}

Analyze and return JSON.
"""
    return call_llm(llm, system, user, FundamentalAnalystOutput)


def run_sentiment(llm, data: dict) -> dict:
    from schemas.stock_schemas import SentimentAnalystOutput
    system = Path(ROOT / "prompts/sentiment_system.md").read_text().replace("{ticker}", data["ticker"])

    headlines = "\n".join(
        f"- {a.get('title','')}" for a in data["articles"][:20]
    )
    user = f"""
Ticker: {data['ticker']}
Date: {data['date']}
Total news articles: {len(data['articles'])}

Recent headlines:
{headlines}

Analyze sentiment and return JSON.
"""
    return call_llm(llm, system, user, SentimentAnalystOutput)


def run_news(llm, data: dict) -> dict:
    from schemas.stock_schemas import NewsAnalystOutput
    system = Path(ROOT / "prompts/news_system.md").read_text().replace("{ticker}", data["ticker"])

    articles_str = "\n".join(
        f"- [{a.get('published_utc','')[:10]}] {a.get('title','')}" for a in data["articles"][:15]
    )
    user = f"""
Ticker: {data['ticker']}
Date: {data['date']}

News Articles:
{articles_str}

Analyze macro impact and company events, return JSON.
"""
    return call_llm(llm, system, user, NewsAnalystOutput)


def run_technical(llm, data: dict) -> dict:
    from schemas.stock_schemas import TechnicalAnalystOutput
    from tools.technical import TechnicalAnalyzer

    system = Path(ROOT / "prompts/technical_system.md").read_text().replace("{ticker}", data["ticker"])

    # 기존 TechnicalAnalyzer 툴 활용
    tech_indicators = {}
    bars = data["bars"]
    if len(bars) >= 20:
        analyzer = TechnicalAnalyzer()
        try:
            tech_indicators = analyzer.analyze(bars)
        except Exception:
            pass

    recent_bars = bars[-10:] if bars else []
    bars_str = "\n".join(
        f"  {b.get('date')}: close={b.get('close')} vol={b.get('volume')}"
        for b in recent_bars
    )
    user = f"""
Ticker: {data['ticker']}
Date: {data['date']}
Current Price: ${data['current_price']}

Recent OHLCV (last 10 bars):
{bars_str}

Pre-calculated indicators:
{json.dumps(tech_indicators, indent=2)}

Analyze technical setup and return JSON.
"""
    return call_llm(llm, system, user, TechnicalAnalystOutput)


# ──────────────────────────────────────────
# Researcher (Bull/Bear)
# ──────────────────────────────────────────

def run_researcher(llm, ticker: str, date: str,
                   fundamental: dict, sentiment: dict,
                   news: dict, technical: dict) -> dict:
    from schemas.stock_schemas import ResearcherOutput
    system = Path(ROOT / "prompts/researcher_system.md").read_text().replace("{ticker}", ticker)

    user = f"""
Ticker: {ticker}
Date: {date}

=== FUNDAMENTAL ANALYST ===
Score: {fundamental.get('fundamental_score')}
Intrinsic Value: {fundamental.get('intrinsic_value_signal')}
PE Ratio: {fundamental.get('pe_ratio')}
Revenue Growth: {fundamental.get('revenue_growth_yoy')}
Strengths: {fundamental.get('key_strengths')}
Risks: {fundamental.get('key_risks')}

=== SENTIMENT ANALYST ===
Sentiment Score: {sentiment.get('sentiment_score')}
Dominant Emotion: {sentiment.get('dominant_emotion')}
Key Themes: {sentiment.get('key_themes')}

=== NEWS ANALYST ===
Macro Impact: {news.get('macro_impact')}
Company Events: {news.get('company_events')}
Catalysts: {news.get('catalyst_signals')}
Event Risk: {news.get('event_risk_level')}

=== TECHNICAL ANALYST ===
Score: {technical.get('technical_score')}
Trend: {technical.get('trend_direction')} (strength: {technical.get('trend_strength')})
RSI: {technical.get('rsi')}
MACD: {technical.get('macd_signal')}
Entry Signal: {technical.get('entry_signal')}

Conduct bull/bear debate and return consensus JSON.
"""
    return call_llm(llm, system, user, ResearcherOutput)


# ──────────────────────────────────────────
# Trader
# ──────────────────────────────────────────

def run_trader(llm_decision, ticker: str, date: str, current_price: float,
               fundamental: dict, sentiment: dict, news: dict,
               technical: dict, researcher: dict) -> dict:
    from schemas.stock_schemas import TraderOutput
    system = Path(ROOT / "prompts/trader_system.md").read_text().replace("{ticker}", ticker)

    user = f"""
Ticker: {ticker}
Date: {date}
Current Price: ${current_price}

=== RESEARCH SYNTHESIS ===
Consensus: {researcher.get('consensus')}
Conviction: {researcher.get('conviction')}
Bull Thesis: {researcher.get('bull_thesis')}
Bear Thesis: {researcher.get('bear_thesis')}
Risk/Reward: {researcher.get('risk_reward_ratio')}

=== KEY SCORES ===
Fundamental Score: {fundamental.get('fundamental_score')}
Technical Score:   {technical.get('technical_score')}
Sentiment Score:   {sentiment.get('sentiment_score')}
Event Risk Level:  {news.get('event_risk_level')}

=== TECHNICAL LEVELS ===
Support:    ${technical.get('support_level')}
Resistance: ${technical.get('resistance_level')}
Entry Signal: {technical.get('entry_signal')}

Make BUY/SELL/HOLD decision and return JSON.
"""
    return call_llm(llm_decision, system, user, TraderOutput)


# ──────────────────────────────────────────
# 출력
# ──────────────────────────────────────────

def print_results(ticker, date, current_price, fundamental, sentiment,
                  news, technical, researcher, trader, verbose=False):

    def sep(title):
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")

    sep(f"종목 분석: {ticker}  ({date})")
    print(f"  현재 주가: ${current_price}")

    if verbose:
        sep("STEP 1 — Analyst Team")
        print(f"\n  [Fundamental]  score={fundamental.get('fundamental_score')}  value={fundamental.get('intrinsic_value_signal')}")
        print(f"    PE={fundamental.get('pe_ratio')}  revenue_growth={fundamental.get('revenue_growth_yoy')}")
        print(f"    강점: {fundamental.get('key_strengths')}")
        print(f"    위험: {fundamental.get('key_risks')}")

        print(f"\n  [Sentiment]    score={sentiment.get('sentiment_score')}  emotion={sentiment.get('dominant_emotion')}")
        print(f"    테마: {sentiment.get('key_themes')}")

        print(f"\n  [News]         macro={news.get('macro_impact')}  event_risk={news.get('event_risk_level')}")
        print(f"    이벤트: {news.get('company_events')}")
        print(f"    촉매:   {news.get('catalyst_signals')}")

        print(f"\n  [Technical]    score={technical.get('technical_score')}  trend={technical.get('trend_direction')}")
        print(f"    RSI={technical.get('rsi')}  MACD={technical.get('macd_signal')}  signal={technical.get('entry_signal')}")
        print(f"    지지선=${technical.get('support_level')}  저항선=${technical.get('resistance_level')}")

        sep("STEP 2 — Researcher (Bull/Bear 토론)")
        print(f"\n  합의:     {researcher.get('consensus')}  (확신도: {researcher.get('conviction')})")
        print(f"  리스크/리워드: {researcher.get('risk_reward_ratio')}")
        print(f"\n  [Bull] {researcher.get('bull_thesis')}")
        print(f"\n  [Bear] {researcher.get('bear_thesis')}")
        print(f"\n  핵심 토론: {researcher.get('key_debate_points')}")

    sep("STEP 3 — Trader 최종 결정")
    action = trader.get('action', 'HOLD')
    action_icon = {"BUY": "🟢 BUY", "SELL": "🔴 SELL", "HOLD": "🟡 HOLD"}.get(action, action)
    print(f"\n  결정:         {action_icon}")
    print(f"  확신도:       {trader.get('confidence')}")
    print(f"  포지션 비중:  {trader.get('position_size_pct', 0)*100:.1f}%")
    print(f"  목표주가:     ${trader.get('target_price')}")
    print(f"  손절가:       ${trader.get('stop_loss_price')}")
    print(f"  투자 기간:    {trader.get('time_horizon')}")
    print(f"\n  판단 근거:")
    for r in trader.get("reasoning", []):
        print(f"    → {r}")

    print(f"\n{'='*60}\n")


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="개별 종목 TradingAgents 파이프라인")
    parser.add_argument("ticker", help="종목 티커 (예: AAPL, NVDA, TSLA)")
    parser.add_argument("--date", default=datetime.today().strftime("%Y-%m-%d"),
                        help="분석 기준일 (YYYY-MM-DD, 기본값: 오늘)")
    parser.add_argument("--verbose", action="store_true", help="모든 analyst 결과 출력")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    date   = args.date

    print(f"\n[{ticker}] 데이터 수집 중... ({date})")
    data = fetch_data(ticker, date)
    print(f"  OHLCV: {len(data['bars'])}봉  |  뉴스: {len(data['articles'])}건  |  재무: {len(data['financials'])}년")

    from llm.factory import create_provider
    llm          = create_provider(node_role="analyst")
    llm_decision = create_provider(node_role="decision")

    print(f"\n[1/4] Fundamental Analyst 실행 중...")
    fundamental = run_fundamental(llm, data)

    print(f"[2/4] Sentiment Analyst 실행 중...")
    sentiment = run_sentiment(llm, data)

    print(f"[3/4] News Analyst 실행 중...")
    news = run_news(llm, data)

    print(f"[4/4] Technical Analyst 실행 중...")
    technical = run_technical(llm, data)

    print(f"\n[Researcher] Bull/Bear 토론 중...")
    researcher = run_researcher(llm, ticker, date, fundamental, sentiment, news, technical)

    print(f"[Trader] 최종 결정 중...")
    trader = run_trader(
        llm_decision, ticker, date, data["current_price"],
        fundamental, sentiment, news, technical, researcher
    )

    print_results(ticker, date, data["current_price"],
                  fundamental, sentiment, news, technical,
                  researcher, trader, verbose=args.verbose)


if __name__ == "__main__":
    main()
