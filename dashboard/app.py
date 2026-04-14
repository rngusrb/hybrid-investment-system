"""dashboard/app.py — 메인 페이지 (종목 입력 + 실행)."""
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Hybrid Investment System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Hybrid Investment System")
st.markdown("TradingAgents 기반 멀티 종목 포트폴리오 분석 시스템")
st.markdown("---")

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("1. 종목 설정")
    tickers_input = st.text_input(
        "분석할 종목 (쉼표로 구분)",
        value="AAPL, NVDA, TSLA",
        placeholder="AAPL, NVDA, TSLA, MSFT",
    )
with col2:
    st.subheader("2. 날짜")
    analysis_date = st.date_input(
        "분석 기준일",
        value=datetime.date(2024, 1, 15),
        min_value=datetime.date(2020, 1, 1),
        max_value=datetime.date.today(),
    )

st.markdown("---")

if st.button("🚀 분석 시작", type="primary", use_container_width=True):
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    date_str = analysis_date.strftime("%Y-%m-%d")

    if not tickers:
        st.error("종목을 하나 이상 입력하세요.")
        st.stop()

    st.session_state["tickers"]   = tickers
    st.session_state["date"]      = date_str
    st.session_state["results"]   = {}
    st.session_state["portfolio"] = {}

    from llm.factory import create_provider
    llm          = create_provider(node_role="analyst")
    llm_decision = create_provider(node_role="decision")

    from scripts.stock_pipeline import (
        fetch_data, run_fundamental, run_sentiment,
        run_news, run_technical, run_researcher,
        run_trader, run_risk_manager,
    )

    total_steps = len(tickers) * 7 + 1
    step        = 0
    progress    = st.progress(0)
    status      = st.empty()
    all_results = []

    for ticker in tickers:
        status.info(f"**[{ticker}]** 데이터 수집 중...")
        data = fetch_data(ticker, date_str)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** Fundamental Analyst 실행 중...")
        fundamental = run_fundamental(llm, data)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** Sentiment Analyst 실행 중...")
        sentiment = run_sentiment(llm, data)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** News Analyst 실행 중...")
        news_out = run_news(llm, data)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** Technical Analyst 실행 중...")
        technical = run_technical(llm, data)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** Researcher (Bull/Bear 토론) 실행 중...")
        researcher = run_researcher(llm, ticker, date_str, fundamental, sentiment, news_out, technical)
        step += 1; progress.progress(step / total_steps)

        status.info(f"**[{ticker}]** Trader + Risk Manager 실행 중...")
        trader  = run_trader(llm_decision, ticker, date_str, data["current_price"],
                             fundamental, sentiment, news_out, technical, researcher)
        risk_mgr = run_risk_manager(llm_decision, ticker, date_str, data["current_price"],
                                    trader, fundamental, sentiment, news_out, technical, researcher)
        step += 1; progress.progress(step / total_steps)

        result = {
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
        }
        all_results.append(result)
        st.session_state["results"][ticker] = result

    status.info("**Portfolio Manager** 최종 배분 결정 중...")
    from scripts.portfolio_pipeline import run_portfolio_manager
    portfolio = run_portfolio_manager(llm_decision, date_str, all_results)
    st.session_state["portfolio"] = portfolio
    step += 1; progress.progress(1.0)

    status.success("✅ 분석 완료! 왼쪽 사이드바에서 결과를 확인하세요.")
    st.balloons()

# ── 현재 세션 상태 표시 ──────────────────────────────────────
if st.session_state.get("results"):
    st.markdown("---")
    st.subheader("현재 분석 결과 요약")
    tickers = st.session_state.get("tickers", [])
    date    = st.session_state.get("date", "")
    st.caption(f"종목: {', '.join(tickers)}  |  날짜: {date}")

    from dashboard.utils.formatters import action_icon, risk_icon, pct_str, price_str

    cols = st.columns(len(tickers))
    for i, ticker in enumerate(tickers):
        r  = st.session_state["results"].get(ticker, {})
        rm = r.get("risk_manager", {})
        action    = rm.get("final_action", "?")
        risk_lvl  = rm.get("risk_level", "moderate")
        pos       = rm.get("final_position_size_pct", 0)
        with cols[i]:
            st.metric(
                label=f"{risk_icon(risk_lvl)} {ticker}",
                value=price_str(r.get("current_price")),
                delta=f"{action_icon(action)}  {pct_str(pos)}",
            )

    # 포트폴리오 요약
    pf = st.session_state.get("portfolio", {})
    if pf:
        st.markdown("---")
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("주식 합계", pct_str(pf.get("total_equity_pct", 0)))
        pc2.metric("현금", pct_str(pf.get("cash_pct", 0)))
        pc3.metric("헤지", pct_str(pf.get("hedge_pct", 0)))

    st.info("👈 사이드바에서 상세 결과 페이지로 이동하세요.")

else:
    st.info("종목과 날짜를 입력하고 **분석 시작** 버튼을 누르세요.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.code("AAPL, NVDA, TSLA\n날짜: 2024-01-15\n(역사적 검증)")
    with c2:
        st.code("MSFT, GOOGL, META\n날짜: 2024-06-01\n(빅테크 비교)")
    with c3:
        st.code("NVDA, AMD, INTC\n날짜: 2024-03-01\n(반도체 섹터)")
