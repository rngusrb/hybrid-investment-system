"""페이지 4 — Pipeline B/C 결과 (results/{date}/portfolio.json 조회)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard.utils.formatters import (
    list_bc_dates, load_bc_result,
    format_approval_badge, format_reliability_rows,
    pct_str,
)

st.set_page_config(page_title="B/C 파이프라인 결과", page_icon="🔄", layout="wide")
st.title("🔄 Pipeline B/C 결과")
st.caption("run_loop.py 실행 결과 (results/{date}/portfolio.json) 조회")

dates = list_bc_dates()
if not dates:
    st.warning("저장된 결과가 없습니다. `python scripts/run_loop.py ...` 를 먼저 실행하세요.")
    st.stop()

selected = st.selectbox("날짜 선택", dates, index=len(dates) - 1)
data = load_bc_result(selected)
if not data:
    st.error(f"results/{selected}/portfolio.json 로드 실패.")
    st.stop()

emily       = data.get("emily", {}) or {}
dave        = data.get("dave", {}) or {}
otto        = data.get("otto", {}) or {}
# reliability_summary 없으면 calibration.reliability_scores 폴백
rel = data.get("reliability_summary") or {}
if not rel:
    cal = data.get("calibration", {}) or {}
    rel = cal.get("reliability_scores", {}) or {}
feas        = data.get("execution_feasibility", {}) or {}
meetings    = data.get("meetings", {}) or {}
errors      = data.get("errors", []) or []
uncertainty = data.get("uncertainty_mode", False)

tickers_str = ", ".join(data.get("tickers", []))
st.caption(f"종목: {tickers_str}  |  기준일: {selected}")

if errors:
    st.error(f"실행 중 {len(errors)}개 에러: {[e.get('node', '?') for e in errors]}")

st.markdown("---")

# ── Emily ──────────────────────────────────────────────────────────────────
st.subheader("Emily — 시장 레짐 분석")
ec1, ec2, ec3, ec4 = st.columns(4)
ec1.metric("레짐", emily.get("market_regime", "N/A"))
ec2.metric("레짐 신뢰도", f"{emily.get('regime_confidence', 0):.2f}")
ec3.metric("기술적 신뢰도", f"{emily.get('technical_confidence', 0):.2f}")
uncertainty_label = "🔴 ON" if uncertainty else "🟢 OFF"
ec4.metric("불확실성 모드", uncertainty_label)

if emily.get("reversal_risk"):
    st.warning(f"반전 리스크 감지: {emily.get('reversal_risk')}")

st.markdown("---")

# ── Dave ───────────────────────────────────────────────────────────────────
st.subheader("Dave — 포트폴리오 리스크 평가")
dc1, dc2, dc3 = st.columns(3)
risk_score = float(dave.get("risk_score", 0))
risk_color = "🔴" if risk_score > 0.7 else ("🟡" if risk_score > 0.5 else "🟢")
dc1.metric("리스크 점수", f"{risk_color} {risk_score:.3f}")
dc2.metric("Defensive 트리거", "✅ 발동" if data.get("dave_rerun_triggered") else "❌ 미발동")
dc3.metric("스트레스 배수", f"{dave.get('stress_multiplier', 1.0):.2f}x")

components = dave.get("risk_components", {})
if components:
    comp_df = pd.DataFrame([
        {"구성요소": k, "값": f"{v:.3f}"} for k, v in components.items()
    ])
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Otto ───────────────────────────────────────────────────────────────────
st.subheader("Otto — 최종 승인 게이트")
oc1, oc2, oc3 = st.columns(3)
approval = otto.get("approval_status", "N/A")
feas_score = feas.get("feasibility_score", 0) if isinstance(feas, dict) else float(feas or 0)
oc1.metric("승인 상태", format_approval_badge(approval))
oc2.metric("Retry 횟수", data.get("otto_retry_count", 0))
oc3.metric("Exec. Feasibility", f"{feas_score:.3f}")

if feas_score < 0.4:
    st.warning("Execution Feasibility < 0.4 → staggered execution 강제됨")

if otto.get("conditional_controls"):
    st.info(f"조건부 제어: {otto['conditional_controls']}")
if otto.get("rejection_reason"):
    st.error(f"거부 이유: {otto['rejection_reason']}")

st.markdown("---")

# ── Reliability ────────────────────────────────────────────────────────────
st.subheader("에이전트 신뢰도 (Reliability)")
if rel:
    rel_rows = format_reliability_rows(rel)
    rel_df = pd.DataFrame(rel_rows)
    st.dataframe(rel_df, use_container_width=True, hide_index=True)

    agents = list(rel.keys())
    scores = [rel[a] for a in agents]
    bar_colors = [
        "#ef5350" if s < 0.35 else ("#ffa726" if s < 0.6 else "#26a69a")
        for s in scores
    ]
    fig_bar = go.Figure(go.Bar(
        x=agents, y=scores,
        marker_color=bar_colors,
        text=[f"{s:.3f}" for s in scores],
        textposition="outside",
    ))
    fig_bar.update_layout(
        height=280, template="plotly_dark",
        yaxis=dict(range=[0, 1.1], title="신뢰도"),
        margin=dict(t=10, b=10),
    )
    fig_bar.add_hline(y=0.35, line_dash="dash", line_color="red",
                      annotation_text="floor=0.35")
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("신뢰도 데이터 없음")

st.markdown("---")

# ── Execution Feasibility ──────────────────────────────────────────────────
st.subheader("Execution Feasibility 상세")
if isinstance(feas, dict) and feas:
    FEAS_LABELS = {
        "feasibility_score": "종합 점수",
        "avg_sharpe":        "평균 Sharpe",
        "cash_pct":          "현금 비중",
        "dave_risk_score":   "Dave 리스크",
        "rebalance_urgency": "리밸런싱 긴급도",
    }
    feas_cols = st.columns(len(FEAS_LABELS))
    for col, (key, label) in zip(feas_cols, FEAS_LABELS.items()):
        val = feas.get(key)
        if val is not None:
            if key == "cash_pct":
                col.metric(label, pct_str(float(val)))
            else:
                col.metric(label, f"{float(val):.3f}")

st.markdown("---")

# ── Meetings ───────────────────────────────────────────────────────────────
st.subheader("회의 요약 (Meetings)")
if meetings:
    for meeting_type, content in meetings.items():
        with st.expander(f"📋 {meeting_type}"):
            if isinstance(content, dict):
                st.json(content)
            else:
                st.write(content)
else:
    st.info("회의 데이터 없음")

# ── Raw 출력 ────────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📄 전체 결과 raw (portfolio.json)"):
    st.json(data)
