"""페이지 2 — 에이전트 플로우 & 전체 보고서."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from dashboard.utils.formatters import (
    action_icon, risk_icon, pct_str, price_str, agent_flow_steps,
)

st.set_page_config(page_title="에이전트 보고서", page_icon="🤖", layout="wide")
st.title("🤖 에이전트 보고서")

if not st.session_state.get("results"):
    st.warning("먼저 메인 페이지에서 분석을 실행하세요.")
    st.stop()

tickers = st.session_state.get("tickers", [])
date    = st.session_state.get("date", "")
st.caption(f"분석 기준일: {date}")

ticker = st.selectbox("종목 선택", tickers)
r      = st.session_state["results"].get(ticker, {})

# ── 에이전트 플로우 다이어그램 ──────────────────────────────
st.subheader("🔄 에이전트 실행 흐름")
steps = agent_flow_steps()
flow_cols = st.columns(len(steps))
for i, (col, step) in enumerate(zip(flow_cols, steps)):
    with col:
        emoji = step["label"].split()[0]
        name  = " ".join(step["label"].split()[1:])
        st.markdown(
            "<div style='text-align:center; padding:8px; background:#1e2130;"
            "border-radius:8px; border:1px solid #3d4466;'>"
            f"<div style='font-size:1.3em'>{emoji}</div>"
            f"<div style='font-size:0.7em; color:#ccc'>{name}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── 에이전트별 보고서 탭 ────────────────────────────────────
tab_fund, tab_sent, tab_news, tab_tech, tab_res, tab_trader, tab_risk = st.tabs([
    "🏦 Fundamental", "💬 Sentiment", "📰 News",
    "📈 Technical", "🔬 Researcher", "💼 Trader", "🛡️ Risk Manager",
])

# ── Fundamental ─────────────────────────────────────────────
with tab_fund:
    fund = r.get("fundamental", {})
    st.subheader(f"Fundamental Analyst — {ticker}")
    st.caption("EPS, PER, 매출 성장률, 내재가치를 분석합니다.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fundamental Score", f"{fund.get('fundamental_score', 0):.2f}")
    c2.metric("내재가치 판단", fund.get("intrinsic_value_signal", "N/A"))
    c3.metric("P/E Ratio", fund.get("pe_ratio", "N/A"))
    ygr = fund.get("revenue_growth_yoy")
    c4.metric("매출 성장률(YoY)", f"{ygr*100:.1f}%" if ygr else "N/A")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**💪 핵심 강점**")
        for s in fund.get("key_strengths", []):
            st.markdown(f"- ✅ {s}")
    with col_r:
        st.markdown("**⚠️ 핵심 리스크**")
        for s in fund.get("key_risks", []):
            st.markdown(f"- 🔴 {s}")

    if fund.get("summary"):
        st.info(fund["summary"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(fund)

# ── Sentiment ───────────────────────────────────────────────
with tab_sent:
    sent = r.get("sentiment", {})
    st.subheader(f"Sentiment Analyst — {ticker}")
    st.caption(f"뉴스 {r.get('articles', []).__len__()}건을 분석해 감성 점수를 산출합니다.")

    c1, c2, c3 = st.columns(3)
    score = sent.get("sentiment_score", 0)
    c1.metric("Sentiment Score", f"{score:.2f}", delta="긍정" if score > 0 else "부정")
    c2.metric("지배 감정", sent.get("dominant_emotion", "N/A"))
    c3.metric("불확실성", f"{sent.get('uncertainty', 0):.2f}")

    st.markdown("**📌 주요 테마** (뉴스에서 추출)")
    themes = sent.get("key_themes", [])
    if themes:
        for theme in themes:
            st.markdown(f"- {theme}")

    if sent.get("summary"):
        st.info(sent["summary"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(sent)

# ── News ────────────────────────────────────────────────────
with tab_news:
    news = r.get("news", {})
    st.subheader(f"News Analyst — {ticker}")
    st.caption("거시경제 영향, 이벤트 리스크, 촉매 신호를 분석합니다.")

    c1, c2 = st.columns(2)
    macro = news.get("macro_impact", 0)
    c1.metric("거시경제 영향", f"{macro:+.2f}",
              delta="긍정" if macro > 0 else ("부정" if macro < 0 else "중립"))
    c2.metric("이벤트 리스크", f"{news.get('event_risk_level', 0):.2f}")

    col_l, col_m, col_r = st.columns(3)
    with col_l:
        st.markdown("**📅 주요 이벤트**")
        for e in news.get("company_events", []):
            st.markdown(f"- {e}")
    with col_m:
        st.markdown("**🏭 산업 트렌드**")
        for t in news.get("industry_trends", []):
            st.markdown(f"- {t}")
    with col_r:
        st.markdown("**⚡ 촉매 신호**")
        for c in news.get("catalyst_signals", []):
            st.markdown(f"- {c}")

    if news.get("summary"):
        st.info(news["summary"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(news)

# ── Technical ───────────────────────────────────────────────
with tab_tech:
    tech = r.get("technical", {})
    st.subheader(f"Technical Analyst — {ticker}")
    st.caption("OHLCV 데이터와 지표(RSI, MACD, 볼린저)를 분석합니다.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Technical Score", f"{tech.get('technical_score', 0):.2f}")
    c2.metric("트렌드", tech.get("trend_direction", "N/A"))
    rsi = tech.get("rsi")
    c3.metric("RSI", f"{rsi:.1f}" if rsi else "N/A")
    c4.metric("MACD", tech.get("macd_signal", "N/A"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("볼린저 위치", tech.get("bollinger_position", "N/A"))
    c6.metric("지지선", price_str(tech.get("support_level")))
    c7.metric("저항선", price_str(tech.get("resistance_level")))
    c8.metric("진입 신호", tech.get("entry_signal", "N/A"))

    if rsi:
        st.markdown("**RSI 위치**")
        st.progress(min(rsi / 100, 1.0))
        if rsi > 70:
            st.warning(f"RSI {rsi:.1f} — 과매수 구간 (>70)")
        elif rsi < 30:
            st.warning(f"RSI {rsi:.1f} — 과매도 구간 (<30)")
        else:
            st.success(f"RSI {rsi:.1f} — 정상 구간 (30~70)")

    if tech.get("summary"):
        st.info(tech["summary"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(tech)

# ── Researcher ──────────────────────────────────────────────
with tab_res:
    res = r.get("researcher", {})
    st.subheader(f"Researcher (Bull/Bear 토론) — {ticker}")
    st.caption("4개 Analyst 보고서를 받아 Bull/Bear 논쟁 후 합의를 도출합니다.")

    c1, c2, c3 = st.columns(3)
    c1.metric("합의", res.get("consensus", "N/A"))
    c2.metric("확신도", f"{res.get('conviction', 0):.2f}")
    rr = res.get("risk_reward_ratio")
    c3.metric("Risk/Reward", f"{rr:.1f}x" if rr else "N/A")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**🐂 Bull Thesis**")
        st.success(res.get("bull_thesis", "N/A"))
    with col_r:
        st.markdown("**🐻 Bear Thesis**")
        st.error(res.get("bear_thesis", "N/A"))

    st.markdown("**🔥 핵심 논쟁 포인트**")
    for pt in res.get("key_debate_points", []):
        st.markdown(f"- {pt}")

    if res.get("summary"):
        st.info(res["summary"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(res)

# ── Trader ──────────────────────────────────────────────────
with tab_trader:
    trader = r.get("trader", {})
    st.subheader(f"Trader (초안 결정) — {ticker}")
    st.caption("Researcher 합의를 받아 구체적인 BUY/SELL/HOLD 초안을 결정합니다. Risk Manager가 최종 조정합니다.")

    action = trader.get("action", "HOLD")
    color  = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(action, "gray")
    st.markdown(
        f"<h2 style='color:{color}'>{action_icon(action)}</h2>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("확신도", f"{trader.get('confidence', 0):.2f}")
    c2.metric("포지션 비중", pct_str(trader.get("position_size_pct", 0)))
    c3.metric("목표주가", price_str(trader.get("target_price")))
    c4.metric("손절가", price_str(trader.get("stop_loss_price")))

    st.metric("투자 기간", trader.get("time_horizon", "N/A"))

    st.markdown("**📋 판단 근거**")
    for rr in trader.get("reasoning", []):
        st.markdown(f"→ {rr}")

    if trader.get("key_signals_used"):
        st.markdown("**🔑 사용된 시그널**")
        st.write(trader["key_signals_used"])

    with st.expander("📄 전체 출력 (raw)"):
        st.json(trader)

# ── Risk Manager ────────────────────────────────────────────
with tab_risk:
    rm = r.get("risk_manager", {})
    st.subheader(f"Risk Manager (최종 조정) — {ticker}")
    st.caption("Aggressive Rick / Conservative Clara / Neutral Nathan 3인 토론 후 Trader 결정을 조정합니다.")

    st.markdown("### 🗣️ 3인 토론 전문")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown("**😤 Aggressive Rick**")
        st.markdown(rm.get("aggressive_view", "N/A"))
    with d2:
        st.markdown("**🛡️ Conservative Clara**")
        st.markdown(rm.get("conservative_view", "N/A"))
    with d3:
        st.markdown("**⚖️ Neutral Nathan**")
        st.markdown(rm.get("neutral_view", "N/A"))

    st.markdown("---")
    st.markdown("### 최종 결정")

    final_action = rm.get("final_action", "HOLD")
    changed      = rm.get("action_changed", False)
    fa_color     = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(final_action, "gray")
    change_note  = "  ← **트레이더 결정 변경됨!**" if changed else ""

    st.markdown(
        f"<h3 style='color:{fa_color}'>{action_icon(final_action)}{change_note}</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("리스크 수준",
              f"{risk_icon(rm.get('risk_level','moderate'))} {rm.get('risk_level','?').upper()}")
    c2.metric("최종 포지션", pct_str(rm.get("final_position_size_pct", 0)))
    c3.metric("현금 보유 권고", pct_str(rm.get("cash_reserve_pct", 0)))
    hedge_type = rm.get("hedge_type", "none")
    hedge_size = rm.get("hedge_size_pct", 0)
    c4.metric("헤지", f"{hedge_type} ({pct_str(hedge_size)})" if hedge_type != "none" else "없음")

    flags = rm.get("risk_flags", [])
    if flags:
        st.warning(f"⚠️ 리스크 플래그: {', '.join(flags)}")

    st.markdown("**💬 합의 근거**")
    st.info(rm.get("consensus_reasoning", "N/A"))

    st.markdown("**📋 조정 근거**")
    for adj in rm.get("adjustment_reasons", []):
        st.markdown(f"→ {adj}")

    with st.expander("📄 전체 출력 (raw)"):
        st.json(rm)
