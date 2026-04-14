"""페이지 1 — 뉴스 데이터 & OHLCV 차트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard.utils.formatters import extract_articles_table, extract_ohlcv_table

st.set_page_config(page_title="뉴스 데이터", page_icon="📰", layout="wide")
st.title("📰 뉴스 & 시장 데이터")

if not st.session_state.get("results"):
    st.warning("먼저 메인 페이지에서 분석을 실행하세요.")
    st.stop()

tickers = st.session_state.get("tickers", [])
date    = st.session_state.get("date", "")
st.caption(f"분석 기준일: {date}  |  종목: {', '.join(tickers)}")

ticker = st.selectbox("종목 선택", tickers)
result = st.session_state["results"].get(ticker, {})

tab1, tab2, tab3 = st.tabs(["📈 OHLCV 차트", "📰 뉴스 목록 (전체)", "💰 재무제표"])

# ── Tab 1: OHLCV 캔들차트 ─────────────────────────────────
with tab1:
    bars = result.get("bars", [])
    if not bars:
        st.info("OHLCV 데이터가 없습니다.")
    else:
        rows = extract_ohlcv_table(bars)
        df   = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])

        fig = go.Figure(data=[go.Candlestick(
            x=df["date"],
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name=ticker,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )])
        import pandas as pd
        vline_x = pd.Timestamp(date)
        fig.add_vline(
            x=vline_x.timestamp() * 1000,
            line_dash="dash", line_color="orange", opacity=0.8,
            annotation_text="분석일", annotation_position="top left",
        )
        fig.update_layout(
            title=f"{ticker} OHLCV (최근 180일)",
            xaxis_title="날짜", yaxis_title="주가 ($)",
            xaxis_rangeslider_visible=False,
            height=460, template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        vol_fig = go.Figure(go.Bar(
            x=df["date"], y=df["volume"],
            marker_color="#42a5f5", name="거래량",
        ))
        vol_fig.update_layout(
            title="거래량", height=180, template="plotly_dark",
            margin=dict(t=30, b=10),
        )
        st.plotly_chart(vol_fig, use_container_width=True)
        st.caption(f"총 {len(bars)}개 봉 | 현재가: ${result.get('current_price', 0):.2f}")

# ── Tab 2: 뉴스 전체 목록 ────────────────────────────────
with tab2:
    articles = result.get("articles", [])
    if not articles:
        st.info("뉴스 데이터가 없습니다.")
    else:
        st.markdown(f"**총 {len(articles)}건** 뉴스가 파이프라인에 입력됨 (최근 30일)")
        st.caption("Fundamental/Sentiment/News/Technical 4개 Analyst 모두 이 뉴스 데이터를 사용합니다.")

        search = st.text_input("🔍 뉴스 검색", placeholder="키워드 입력...")
        rows   = extract_articles_table(articles)
        df_news = pd.DataFrame(rows)

        if search:
            mask    = df_news["제목"].str.contains(search, case=False, na=False)
            df_news = df_news[mask]

        st.caption(f"표시: {len(df_news)}건")

        for _, row in df_news.iterrows():
            title  = row.get("제목", "")
            date_r = row.get("날짜", "")
            src    = row.get("출처", "")
            url    = row.get("URL", "")
            label  = f"[{date_r}] {title[:90]}"
            with st.expander(label):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**출처**: {src}")
                if url:
                    c2.markdown(f"[기사 보기 🔗]({url})")

# ── Tab 3: 재무제표 ──────────────────────────────────────
with tab3:
    financials = result.get("financials", [])
    fund       = result.get("fundamental", {})

    st.markdown("**파이프라인에 입력된 재무 데이터**")
    st.caption(
        f"Fundamental Analyst가 이 데이터를 기반으로 EPS, PE, 성장률을 판단합니다.  "
        f"**분석 기준일 `{date}` 이전 공시 데이터만 표시됩니다.** "
        f"(filing\\_date ≤ {date})"
    )

    if financials:
        for fin in financials:
            if "error" in fin:
                st.error(f"재무 데이터 오류: {fin['error']}")
                continue
            period = fin.get("period", "")
            filed  = fin.get("filed", "")
            filed_label = f" — SEC 공시일: `{filed}`" if filed else ""
            st.subheader(f"📅 {period}{filed_label}")
            fc1, fc2 = st.columns(2)
            rev = fin.get("revenue")
            ni  = fin.get("net_income")
            fc1.metric("매출", f"${rev/1e9:.2f}B" if rev else "N/A")
            fc2.metric("순이익", f"${ni/1e9:.2f}B" if ni else "N/A")
    else:
        st.info("재무제표 데이터 없음")

    st.markdown("---")
    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("EPS (연환산)", f"${fund.get('eps', 'N/A')}" if fund.get("eps") else "N/A")
    ec2.metric("P/E Ratio", fund.get("pe_ratio", "N/A"))
    ec3.metric("매출 성장(YoY)", f"{fund.get('revenue_growth_yoy', 0)*100:.1f}%" if fund.get("revenue_growth_yoy") else "N/A")
