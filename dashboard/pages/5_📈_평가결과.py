"""페이지 5 — 평가 결과 (results/eval_*.json 조회)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard.utils.formatters import load_eval_results, pct_str

st.set_page_config(page_title="평가 결과", page_icon="📈", layout="wide")
st.title("📈 평가 결과 — System vs Baseline")
st.caption("run_eval.py 출력 (results/eval_*.json) 조회")

evals = load_eval_results()
if not evals:
    st.warning(
        "평가 결과가 없습니다. "
        "`python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31` 을 먼저 실행하세요."
    )
    st.stop()

# 여러 eval 파일이 있으면 선택
if len(evals) > 1:
    labels = [
        f"{e.get('period', '?')}  ({e.get('generated_date', '?')})"
        for e in evals
    ]
    idx = st.selectbox(
        "평가 기간 선택", range(len(evals)),
        format_func=lambda i: labels[i],
        index=len(evals) - 1,
    )
    data = evals[idx]
else:
    data = evals[0]

period = data.get("period", "N/A")
n = data.get("n_periods", 0)
st.caption(f"기간: {period}  |  주기 수: {n}")

metrics = data.get("metrics", {})

# ── Hybrid System KPI 카드 ──────────────────────────────────────────────────
st.subheader("Hybrid System 핵심 수치")
sys_m = metrics.get("system", {})
k1, k2, k3, k4 = st.columns(4)
k1.metric("누적 수익률", pct_str(sys_m.get("cumulative_return", 0)))
k2.metric("샤프 비율", f"{sys_m.get('sharpe_ratio', 0):.3f}")
k3.metric("최대 낙폭", pct_str(sys_m.get("max_drawdown", 0)))
k4.metric("승률", pct_str(sys_m.get("win_rate", 0)))

st.markdown("---")

# ── 지표 비교표 ─────────────────────────────────────────────────────────────
st.subheader("전략별 핵심 지표 비교")

METRIC_LABELS = {
    "cumulative_return": "누적 수익률 (CR)",
    "annualized_return": "연환산 수익률 (ARR)",
    "sharpe_ratio":      "샤프 비율 (SR)",
    "sortino_ratio":     "소르티노 비율",
    "max_drawdown":      "최대 낙폭 (MDD)",
    "win_rate":          "승률",
}
PCT_KEYS = {"cumulative_return", "annualized_return", "max_drawdown", "win_rate"}

rows = []
for key, label in METRIC_LABELS.items():
    row = {"지표": label}
    for strat, mdata in metrics.items():
        val = mdata.get(key)
        col_label = mdata.get("label", strat)
        if val is None:
            row[col_label] = "N/A"
        elif key in PCT_KEYS:
            row[col_label] = pct_str(val)
        else:
            row[col_label] = f"{val:.3f}"
    rows.append(row)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# ── 누적 수익률 시계열 차트 ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("누적 수익률 시계열")

sys_returns = data.get("system_returns", [])
baseline_returns = data.get("baseline_returns", {})

BASELINE_COLORS = {
    "buy_and_hold": "#ef5350",
    "macd":         "#ffa726",
    "sma":          "#ab47bc",
}

if sys_returns:
    fig = go.Figure()

    # 시스템
    cum = [1.0]
    for r in sys_returns:
        cum.append(cum[-1] * (1 + r))
    cum_pct = [(c - 1) * 100 for c in cum[1:]]
    fig.add_trace(go.Scatter(
        x=list(range(1, len(cum_pct) + 1)),
        y=cum_pct,
        mode="lines+markers",
        name="Hybrid System",
        line=dict(color="#26a69a", width=2),
    ))

    # 베이스라인
    for key, bl_returns in baseline_returns.items():
        if not bl_returns:
            continue
        cum_bl = [1.0]
        for r in bl_returns:
            cum_bl.append(cum_bl[-1] * (1 + r))
        cum_bl_pct = [(c - 1) * 100 for c in cum_bl[1:]]
        label = metrics.get(key, {}).get("label", key)
        fig.add_trace(go.Scatter(
            x=list(range(1, len(cum_bl_pct) + 1)),
            y=cum_bl_pct,
            mode="lines",
            name=label,
            line=dict(color=BASELINE_COLORS.get(key, "#888"), width=1, dash="dash"),
        ))

    fig.add_hline(y=0, line_dash="dot", line_color="#555")
    fig.update_layout(
        height=400, template="plotly_dark",
        yaxis=dict(title="누적 수익률 (%)"),
        xaxis=dict(title="주기"),
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=10),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Raw 출력 ─────────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📄 평가 결과 전체 (raw)"):
    st.json(data)
