"""페이지 0 — 파이프라인 전체 추적 (회의록 + 데이터 흐름)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from dashboard.utils.formatters import (
    build_pipeline_trace, action_icon, risk_icon, pct_str, price_str,
)

st.set_page_config(page_title="파이프라인 추적", page_icon="🔄", layout="wide")
st.title("🔄 파이프라인 전체 추적")
st.caption("어떤 데이터가 들어갔고, 각 에이전트가 무슨 회의를 했으며, 무엇을 다음 단계에 넘겼는지 전부 보여줍니다.")

if not st.session_state.get("results"):
    st.warning("먼저 메인 페이지에서 분석을 실행하세요.")
    st.stop()

tickers = st.session_state.get("tickers", [])
date    = st.session_state.get("date", "")
st.caption(f"분석 기준일: {date}  |  종목: {', '.join(tickers)}")

ticker = st.selectbox("종목 선택", tickers)
result = st.session_state["results"].get(ticker, {})
trace  = build_pipeline_trace(result)

# 스텝 색상/배경
STEP_COLORS = {
    0: "#1a3a4a",  # 데이터 수집
    1: "#1a3a2a",  # Fundamental
    2: "#2a2a3a",  # Sentiment
    3: "#3a2a1a",  # News
    4: "#1a2a3a",  # Technical
    5: "#3a1a3a",  # Researcher 회의
    6: "#3a2a1a",  # Trader
    7: "#3a1a1a",  # Risk Manager 회의
}
SPEAKER_COLORS = {
    "🐂 Bull Analyst":     "#26a69a",
    "🐻 Bear Analyst":     "#ef5350",
    "🔬 Researcher 합의":  "#ab47bc",
    "😤 Aggressive Rick":  "#ef5350",
    "🛡️ Conservative Clara": "#42a5f5",
    "⚖️ Neutral Nathan":   "#66bb6a",
    "🛡️ 최종 합의":        "#ab47bc",
    "⚠️ 리스크 플래그":    "#ffa726",
    "⚡ 논점":              "#ffa726",
    "💼 Trader":           "#78909c",
    "💼 결정":             "#ab47bc",
}

def speaker_color(speaker: str) -> str:
    for key, color in SPEAKER_COLORS.items():
        if key in speaker:
            return color
    return "#90a4ae"


# ── 상단: 파이프라인 전체 요약 바 ────────────────────────────
st.markdown("---")
st.subheader("파이프라인 요약")

step_cols = st.columns(len(trace))
for col, t in zip(step_cols, trace):
    with col:
        bg = STEP_COLORS.get(t["step"], "#1e2130")
        st.markdown(
            f"<div style='text-align:center; padding:6px 2px; background:{bg};"
            f"border-radius:6px; border:1px solid #444; font-size:0.75em'>"
            f"<div style='font-size:1.4em'>{t['emoji']}</div>"
            f"<div style='color:#ddd; margin-top:2px'>{t['label'].split('(')[0].strip()}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── 단계별 상세 ──────────────────────────────────────────────
for t in trace:
    bg = STEP_COLORS.get(t["step"], "#1e2130")
    is_meeting = len(t["meeting_lines"]) > 1  # 회의가 있는 단계

    # 헤더
    st.markdown(
        f"<div style='background:{bg}; padding:12px 16px; border-radius:8px 8px 0 0;"
        f"border:1px solid #444; margin-top:16px'>"
        f"<span style='font-size:1.4em'>{t['emoji']}</span> "
        f"<span style='font-size:1.1em; font-weight:bold'> Step {t['step']} — {t['label']}</span>"
        + ("  <span style='background:#5c3a7a; padding:2px 8px; border-radius:4px; font-size:0.8em'>🗣️ 회의</span>" if is_meeting else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    # 입력/출력 요약
    io_col1, io_col2 = st.columns(2)
    with io_col1:
        st.markdown(
            f"<div style='background:#0d1117; padding:8px 12px; border-left:3px solid #444;'>"
            f"<span style='color:#888; font-size:0.8em'>📥 입력</span><br>"
            f"<span style='color:#ccc'>{t['input_summary']}</span></div>",
            unsafe_allow_html=True,
        )
    with io_col2:
        st.markdown(
            f"<div style='background:#0d1117; padding:8px 12px; border-left:3px solid #26a69a;'>"
            f"<span style='color:#888; font-size:0.8em'>📤 출력</span><br>"
            f"<span style='color:#ccc'>{t['output_summary']}</span></div>",
            unsafe_allow_html=True,
        )

    # Key Output 메트릭
    key_out = {k: v for k, v in t["key_output"].items() if v is not None}
    if key_out:
        metric_cols = st.columns(min(len(key_out), 5))
        for col, (k, v) in zip(metric_cols, key_out.items()):
            if isinstance(v, float) and 0 < v <= 1 and k not in ("목표가", "손절가"):
                display = f"{v:.2f}"
            elif isinstance(v, float):
                display = f"{v:.2f}"
            elif isinstance(v, list):
                display = ", ".join(str(x) for x in v[:2])
            elif isinstance(v, bool):
                display = "✅ 예" if v else "❌ 아니오"
            else:
                display = str(v) if v is not None else "N/A"
            col.metric(k, display)

    # 회의록
    if t["meeting_lines"]:
        if is_meeting:
            st.markdown(
                "<div style='background:#0d1117; padding:4px 12px; margin-top:4px;"
                "border-left:3px solid #5c3a7a;'>"
                "<span style='color:#ab47bc; font-size:0.85em'>🗣️ 회의 내용</span></div>",
                unsafe_allow_html=True,
            )
        for speaker, content in t["meeting_lines"]:
            color = speaker_color(speaker)
            st.markdown(
                f"<div style='background:#111827; padding:10px 14px; margin:4px 0;"
                f"border-left:4px solid {color}; border-radius:0 6px 6px 0'>"
                f"<span style='color:{color}; font-weight:bold; font-size:0.85em'>{speaker}</span><br>"
                f"<span style='color:#e0e0e0'>{content}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div style='background:#0d1117; padding:4px; border-radius:0 0 8px 8px;"
        "border:1px solid #444; border-top:none'></div>",
        unsafe_allow_html=True,
    )

# ── 하단: 포트폴리오 최종 결정 ───────────────────────────────
portfolio = st.session_state.get("portfolio", {})
if portfolio:
    st.markdown("---")
    st.markdown(
        "<div style='background:#1a2a1a; padding:12px 16px; border-radius:8px 8px 0 0;"
        "border:1px solid #444;'>"
        "<span style='font-size:1.4em'>🗂️</span> "
        "<span style='font-size:1.1em; font-weight:bold'> Portfolio Manager 최종 배분</span>"
        "  <span style='background:#1a4a1a; padding:2px 8px; border-radius:4px; font-size:0.8em'>전 종목 통합</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    allocs = portfolio.get("allocations", [])
    for a in sorted(allocs, key=lambda x: x.get("weight", 0), reverse=True):
        w = a.get("weight", 0)
        act = a.get("action", "HOLD")
        color = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#ffa726"}.get(act, "#888")
        if w > 0 or act in ("BUY", "HOLD"):
            st.markdown(
                f"<div style='background:#111827; padding:10px 14px; margin:4px 0;"
                f"border-left:4px solid {color}; border-radius:0 6px 6px 0'>"
                f"<span style='color:{color}; font-weight:bold'>{action_icon(act)} {a.get('ticker','')}</span>"
                f"  <span style='color:#aaa'>→ {pct_str(w)}</span><br>"
                f"<span style='color:#ccc; font-size:0.9em'>{a.get('rationale','')}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    pf_cols = st.columns(3)
    pf_cols[0].metric("주식 합계", pct_str(portfolio.get("total_equity_pct", 0)))
    pf_cols[1].metric("현금", pct_str(portfolio.get("cash_pct", 0)))
    pf_cols[2].metric("헤지", pct_str(portfolio.get("hedge_pct", 0)))

    st.markdown(
        "<div style='background:#0d1117; padding:4px; border-radius:0 0 8px 8px;"
        "border:1px solid #444; border-top:none'></div>",
        unsafe_allow_html=True,
    )
