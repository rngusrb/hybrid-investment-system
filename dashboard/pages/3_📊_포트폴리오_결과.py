"""페이지 3 — 포트폴리오 최종 결과."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from dashboard.utils.formatters import (
    action_icon, risk_icon, pct_str, price_str, build_allocation_rows,
)

st.set_page_config(page_title="포트폴리오 결과", page_icon="📊", layout="wide")
st.title("📊 포트폴리오 최종 결과")

if not st.session_state.get("results"):
    st.warning("먼저 메인 페이지에서 분석을 실행하세요.")
    st.stop()

if not st.session_state.get("portfolio"):
    st.warning("포트폴리오 분석 결과가 없습니다. 메인 페이지에서 다시 실행하세요.")
    st.stop()

tickers   = st.session_state.get("tickers", [])
date      = st.session_state.get("date", "")
portfolio = st.session_state.get("portfolio", {})
results   = st.session_state.get("results", {})

st.caption(f"분석 기준일: {date}  |  종목: {', '.join(tickers)}")

# ── 상단 KPI ─────────────────────────────────────────────────
st.subheader("포트폴리오 요약")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("주식 합계",      pct_str(portfolio.get("total_equity_pct", 0)))
k2.metric("현금",           pct_str(portfolio.get("cash_pct", 0)))
k3.metric("헤지",           pct_str(portfolio.get("hedge_pct", 0)))
risk_lvl = portfolio.get("portfolio_risk_level", "moderate")
k4.metric("포트폴리오 리스크", f"{risk_icon(risk_lvl)} {risk_lvl.upper()}")
k5.metric("분산도", f"{portfolio.get('diversification_score', 0):.2f}")

st.markdown("---")

# ── 파이차트 + 배분표 ────────────────────────────────────────
col_pie, col_table = st.columns([1, 1])

with col_pie:
    st.subheader("배분 파이차트")
    palette = px.colors.qualitative.Set2
    labels, values, colors = [], [], []

    allocs = portfolio.get("allocations", [])
    for i, a in enumerate(allocs):
        if a.get("weight", 0) > 0:
            labels.append(a.get("ticker", ""))
            values.append(a.get("weight", 0))
            colors.append(palette[i % len(palette)])

    cash  = portfolio.get("cash_pct", 0)
    hedge = portfolio.get("hedge_pct", 0)
    if cash > 0:
        labels.append("현금")
        values.append(cash)
        colors.append("#78909c")
    if hedge > 0:
        labels.append("헤지")
        values.append(hedge)
        colors.append("#b0bec5")

    if values:
        fig_pie = go.Figure(go.Pie(
            labels=labels, values=values,
            marker_colors=colors,
            hole=0.4,
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:.1%}<extra></extra>",
        ))
        fig_pie.update_layout(
            height=350, template="plotly_dark",
            showlegend=True,
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("배분 데이터가 없습니다.")

with col_table:
    st.subheader("배분 상세")
    rows = build_allocation_rows(portfolio)
    df   = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    rebal      = portfolio.get("rebalance_urgency", "monitor")
    entry      = portfolio.get("entry_style", "hold")
    hedge_inst = portfolio.get("hedge_instrument", "none")
    conc       = portfolio.get("concentration_risk", False)

    st.markdown("**실행 계획**")
    i1, i2 = st.columns(2)
    i1.info(f"리밸런싱: **{rebal}**")
    i2.info(f"진입 방식: **{entry}**")
    if hedge_inst != "none":
        st.info(f"헤지 수단: **{hedge_inst}**")
    if conc:
        st.warning("집중 리스크 감지됨")

# ── 종목 비교 레이더차트 ─────────────────────────────────────
st.markdown("---")
st.subheader("종목별 점수 비교 (레이더)")

categories = ["Fundamental", "Technical", "Sentiment", "Conviction", "Risk(역)"]
fig_radar  = go.Figure()

for ticker in tickers:
    r   = results.get(ticker, {})
    rm  = r.get("risk_manager", {})
    res = r.get("researcher", {})
    sent = r.get("sentiment", {})

    risk_map  = {"low": 0.9, "moderate": 0.6, "high": 0.3, "extreme": 0.1}
    risk_inv  = risk_map.get(rm.get("risk_level", "moderate"), 0.5)
    sent_norm = (sent.get("sentiment_score", 0) + 1) / 2

    vals = [
        r.get("fundamental", {}).get("fundamental_score", 0.5),
        r.get("technical", {}).get("technical_score", 0.5),
        sent_norm,
        res.get("conviction", 0.5),
        risk_inv,
    ]
    vals_closed = vals + vals[:1]
    cats_closed = categories + [categories[0]]

    fig_radar.add_trace(go.Scatterpolar(
        r=vals_closed, theta=cats_closed,
        fill="toself", name=ticker, opacity=0.7,
    ))

fig_radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    height=400, template="plotly_dark",
    legend=dict(orientation="h", y=-0.15),
)
st.plotly_chart(fig_radar, use_container_width=True)

# ── 시장 전망 & 리스크 ──────────────────────────────────────
st.markdown("---")
col_out, col_risk = st.columns(2)

with col_out:
    st.subheader("시장 전망")
    st.info(portfolio.get("market_outlook", "N/A"))
    st.markdown("**판단 근거**")
    for reason in portfolio.get("reasoning", []):
        st.markdown(f"→ {reason}")

with col_risk:
    st.subheader("핵심 리스크")
    for risk in portfolio.get("key_risks", []):
        st.error(f"🔴 {risk}")

# ── 개별 종목 Risk Manager 요약 카드 ───────────────────────
st.markdown("---")
st.subheader("종목별 Risk Manager 최종 요약")

cols = st.columns(len(tickers))
for i, ticker in enumerate(tickers):
    r        = results.get(ticker, {})
    rm       = r.get("risk_manager", {})
    trader   = r.get("trader", {})
    final    = rm.get("final_action", "HOLD")
    changed  = rm.get("action_changed", False)
    risk_lv  = rm.get("risk_level", "moderate")

    border_color = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#ffa726"}.get(final, "#555")

    with cols[i]:
        st.markdown(
            f"<div style='padding:12px; background:#1e2130; border-radius:8px;"
            f"border:2px solid {border_color}; margin-bottom:8px'>"
            f"<b style='font-size:1.1em'>{ticker}</b><br>"
            f"<span style='font-size:1.3em'>{action_icon(final)}</span><br>"
            + ("<span style='color:orange'>⚡ 결정 변경됨</span><br>" if changed else "")
            + f"포지션: {pct_str(rm.get('final_position_size_pct', 0))}<br>"
            f"현금 권고: {pct_str(rm.get('cash_reserve_pct', 0))}<br>"
            f"리스크: {risk_icon(risk_lv)} {risk_lv.upper()}"
            f"</div>",
            unsafe_allow_html=True,
        )
        flags = rm.get("risk_flags", [])
        if flags:
            st.caption(f"⚠️ {', '.join(flags)}")

        # 트레이더 초안 vs 최종 비교
        with st.expander("트레이더 초안 vs 최종"):
            t_action = trader.get("action", "?")
            t_pos    = trader.get("position_size_pct", 0)
            f_pos    = rm.get("final_position_size_pct", 0)
            st.markdown(f"**트레이더 초안**: {action_icon(t_action)} / {pct_str(t_pos)}")
            st.markdown(f"**Risk Manager**: {action_icon(final)} / {pct_str(f_pos)}")
            adj = rm.get("position_adjustment", 0)
            if adj != 0:
                sign = "+" if adj >= 0 else ""
                st.markdown(f"**포지션 조정**: {sign}{pct_str(abs(adj))}")

# ── 포트폴리오 raw 출력 ─────────────────────────────────────
st.markdown("---")
with st.expander("📄 Portfolio Manager 전체 출력 (raw)"):
    st.json(portfolio)
