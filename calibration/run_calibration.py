"""
calibration/run_calibration.py — Pipeline B/C용 Calibration + Audit + Reliability 어댑터

run_loop.py의 run_one_cycle 내에서:
1. Calibration  : technical/fundamental/sentiment score rolling 정규화 (drift 방지)
2. Propagation Audit: analyst signal이 Trader/Risk Manager까지 전달됐는지 추적
3. Reliability  : agent별 신뢰도 EMA 업데이트 (cycle 내 신호 품질 기반)

흐름:
  stock_results + sim_results
  → calibrate_stock_scores()        : score drift 방지
  → audit_bc_propagation()          : signal 손실 / 채택률 추적
  → update_bc_reliability()         : agent 신뢰도 EMA 갱신
  → format_calibration_for_prompt() : Portfolio Manager 텍스트

Pipeline A(Emily/Bob/Dave/Otto)와 무관하게 B/C 파이프라인 전용으로 동작.
"""

from calibration.calibrator import AgentCalibrator
from reliability.agent_reliability import AgentReliabilityManager, GatingDecision

# ─── 모듈 레벨 상태 (run_loop 세션 내 누적) ──────────────────────────────────

# ticker별 calibrator 캐시 {ticker → AgentCalibrator}
_calibrators: dict[str, AgentCalibrator] = {}

# B/C 에이전트 역할 목록
_BC_AGENTS = ["fundamental", "sentiment", "news", "technical", "researcher", "trader", "risk_manager"]

# 세션 공유 reliability manager (모든 ticker 공통)
_reliability_manager: AgentReliabilityManager | None = None


def _get_calibrator(ticker: str) -> AgentCalibrator:
    """ticker별 AgentCalibrator — 세션 내 rolling history 누적."""
    if ticker not in _calibrators:
        _calibrators[ticker] = AgentCalibrator(
            agent_name=ticker,
            rolling_window=20,
            shrinkage_factor=0.3,
            clip_range=(0.0, 1.0),
        )
    return _calibrators[ticker]


def _get_reliability_manager() -> AgentReliabilityManager:
    """세션 공유 AgentReliabilityManager — 최초 1회 초기화."""
    global _reliability_manager
    if _reliability_manager is None:
        _reliability_manager = AgentReliabilityManager(_BC_AGENTS)
    return _reliability_manager


def reset_session_state():
    """테스트용 세션 상태 초기화."""
    global _calibrators, _reliability_manager
    _calibrators = {}
    _reliability_manager = None


# ─── Calibration ─────────────────────────────────────────────────────────────

_SCORE_FIELDS = {
    "technical":    ["technical_score"],
    "fundamental":  ["fundamental_score"],
    "sentiment":    ["sentiment_score", "bullish_score", "bearish_score"],
    "researcher":   ["conviction_score", "risk_reward_ratio"],
}

# 0~10 점수 → 0~1 정규화
def _normalize_10(v) -> float | None:
    try:
        f = float(v)
        return max(0.0, min(1.0, f / 10.0))
    except (TypeError, ValueError):
        return None


def calibrate_stock_scores(
    stock_results: list[dict],
    run_date: str,
) -> dict[str, dict]:
    """
    각 종목 analyst score를 rolling std calibration으로 정규화.

    반환: {ticker → {field → calibrated_value, ...}}
    cold start / 데이터 부족 시 원본 값 그대로 반환.
    """
    calibrated: dict[str, dict] = {}

    for r in stock_results:
        ticker = r.get("ticker", "?")
        cal = _get_calibrator(ticker)
        result: dict = {}

        for agent_role, fields in _SCORE_FIELDS.items():
            agent_data = r.get(agent_role) or {}
            for field in fields:
                raw = agent_data.get(field)
                if raw is None:
                    continue
                norm = _normalize_10(raw)
                if norm is None:
                    continue
                cal_val, _ = cal.calibrate(
                    field_name=f"{agent_role}.{field}",
                    raw_value=norm,
                    date=run_date,
                    method="rolling_std",
                )
                result[f"{agent_role}.{field}"] = round(cal_val, 4)

        calibrated[ticker] = result

    return calibrated


# ─── Propagation Audit ────────────────────────────────────────────────────────

def _tech_adopted(tech_score, action: str) -> bool:
    """기술적 신호가 Trader 액션과 일관성 있는지."""
    if tech_score is None:
        return True  # 데이터 없으면 패스
    try:
        score = float(tech_score)
    except (TypeError, ValueError):
        return True
    if score >= 7 and action == "BUY":
        return True
    if score <= 3 and action == "SELL":
        return True
    if 3 < score < 7:
        return True   # 중립 구간 — 어떤 액션도 허용
    return False  # 강한 신호와 반대 액션 → 미채택


def _consensus_adopted(consensus: str, final_action: str) -> bool:
    """Researcher consensus가 Risk Manager 최종 액션과 일관성 있는지."""
    mapping = {"bullish": "BUY", "bearish": "SELL", "neutral": "HOLD"}
    expected = mapping.get(consensus, "")
    if not expected:
        return True
    return final_action == expected


def audit_bc_propagation(
    stock_results: list[dict],
    run_date: str,
) -> dict[str, dict]:
    """
    B/C 파이프라인 내 signal 전달 감사.

    추적:
    - tech_adoption_rate    : technical_score → Trader action 일관성
    - consensus_adoption_rate: Researcher consensus → Risk Manager final_action 일관성
    - action_drift_rate     : Trader action → Risk Manager에서 변경된 비율
    - dropped_signal_count  : 강한 신호가 반대 방향 액션과 충돌한 횟수

    반환: {ticker → audit_dict}
    """
    audit: dict[str, dict] = {}

    for r in stock_results:
        ticker = r.get("ticker", "?")
        tech = r.get("technical") or {}
        researcher = r.get("researcher") or {}
        trader = r.get("trader") or {}
        rm = r.get("risk_manager") or {}

        tech_score = tech.get("technical_score")
        trader_action = trader.get("action", "HOLD")
        final_action = rm.get("final_action", trader_action)
        consensus = researcher.get("consensus", "neutral")

        tech_ok = _tech_adopted(tech_score, trader_action)
        consensus_ok = _consensus_adopted(consensus, final_action)
        action_drifted = rm.get("action_changed", False)

        tech_adoption_rate = 1.0 if tech_ok else 0.0
        consensus_adoption_rate = 1.0 if consensus_ok else 0.0
        dropped = (not tech_ok) + (not consensus_ok)

        audit[ticker] = {
            "date": run_date,
            "tech_adoption_rate": tech_adoption_rate,
            "consensus_adoption_rate": consensus_adoption_rate,
            "action_changed": action_drifted,
            "dropped_signal_count": dropped,
            "propagation_score": round(
                (tech_adoption_rate + consensus_adoption_rate) / 2, 4
            ),
        }

    return audit


# ─── Reliability ──────────────────────────────────────────────────────────────

def update_bc_reliability(
    stock_results: list[dict],
    propagation_audit: dict[str, dict],
    sim_results: dict[str, dict],
) -> dict[str, float]:
    """
    B/C 에이전트 역할별 reliability EMA 업데이트.

    업데이트 기준:
    - decision_usefulness     : trader confidence 평균
    - contradiction_penalty   : action_changed 비율
    - propagation_adoption    : propagation_score 평균
    - outcome_alignment       : sim sharpe > 0 비율 (proxy)
    - noise_penalty           : empty result 비율

    반환: {agent_role → reliability_score}
    """
    mgr = _get_reliability_manager()

    if not stock_results:
        return mgr.get_reliability_summary()

    n = len(stock_results)

    # trader metrics
    trader_confidences = [r.get("trader", {}).get("confidence", 0.5) for r in stock_results]
    avg_confidence = sum(trader_confidences) / n

    # action_changed (contradiction proxy)
    action_changed_count = sum(
        1 for r in stock_results if r.get("risk_manager", {}).get("action_changed", False)
    )
    action_changed_rate = action_changed_count / n

    # propagation adoption rate 평균
    prop_scores = [v.get("propagation_score", 0.5) for v in propagation_audit.values()]
    avg_prop = sum(prop_scores) / max(len(prop_scores), 1)

    # outcome alignment proxy: sim sharpe > 0 비율
    if sim_results:
        positive_sharpe = sum(
            1 for sim in sim_results.values()
            if (sim.get("best") or {}).get("sharpe", 0) > 0
        )
        outcome_proxy = positive_sharpe / len(sim_results)
    else:
        outcome_proxy = 0.5

    # noise penalty: 각 analyst field 누락 비율
    noise_counts = []
    for r in stock_results:
        missing = sum(1 for role in ["technical", "fundamental", "sentiment", "researcher"]
                      if not r.get(role))
        noise_counts.append(missing / 4.0)
    avg_noise = sum(noise_counts) / n

    # 에이전트별 업데이트 (동일 지표 공유, 역할별 특화 불가 — B/C 단순화)
    for agent in _BC_AGENTS:
        mgr.update_agent(
            agent,
            decision_usefulness=avg_confidence,
            contradiction_penalty=action_changed_rate,
            propagation_adoption_rate=avg_prop,
            outcome_alignment=outcome_proxy,
            noise_penalty=avg_noise,
        )

    return mgr.get_reliability_summary()


# ─── 오케스트레이터 ───────────────────────────────────────────────────────────

def run_calibration_audit(
    stock_results: list[dict],
    sim_results: dict[str, dict],
    run_date: str,
) -> dict:
    """
    Calibration + Audit + Reliability 전체 실행.

    반환:
        {
          calibrated_scores: {ticker → {field → value}},
          propagation_audit: {ticker → audit_dict},
          reliability_scores: {agent → score},
          gating_decisions: {agent → "full"|"downweight"|"hard_gate"},
          flags: [str, ...],  # 주의 사항
        }
    """
    calibrated = calibrate_stock_scores(stock_results, run_date)
    audit = audit_bc_propagation(stock_results, run_date)
    reliability = update_bc_reliability(stock_results, audit, sim_results)

    mgr = _get_reliability_manager()
    gating = {
        name: decision.value
        for name, decision in mgr.get_gating_decisions().items()
    }

    # 주의 플래그
    flags: list[str] = []
    hard_gated = [a for a, g in gating.items() if g == "hard_gate"]
    if hard_gated:
        flags.append(f"HARD_GATE: {hard_gated} (신뢰도 < floor)")

    for ticker, a in audit.items():
        if a["dropped_signal_count"] >= 2:
            flags.append(f"[{ticker}] 신호 손실 {a['dropped_signal_count']}건")

    return {
        "date": run_date,
        "calibrated_scores": calibrated,
        "propagation_audit": audit,
        "reliability_scores": reliability,
        "gating_decisions": gating,
        "flags": flags,
    }


# ─── Portfolio Manager 프롬프트 포맷 ─────────────────────────────────────────

def format_calibration_for_prompt(cal: dict) -> str:
    """
    Calibration/Audit/Reliability 결과 → Portfolio Manager 프롬프트 삽입용 텍스트.
    cal이 비어있으면 빈 문자열.
    """
    if not cal:
        return ""

    lines = ["=== CALIBRATION / AUDIT / RELIABILITY ===", ""]

    # Reliability & Gating
    reliability = cal.get("reliability_scores", {})
    gating = cal.get("gating_decisions", {})
    if reliability:
        lines.append("[Reliability] Agent 신뢰도")
        for agent, score in reliability.items():
            gate = gating.get(agent, "full")
            gate_icon = {"full": "✓", "downweight": "↓", "hard_gate": "✗"}.get(gate, "?")
            lines.append(f"  {gate_icon} {agent:<14} {score:.3f}  [{gate}]")
        lines.append("")

    # Propagation Audit
    audit = cal.get("propagation_audit", {})
    if audit:
        lines.append("[Propagation Audit] 신호 전달 추적")
        for ticker, a in audit.items():
            prop = a.get("propagation_score", 0)
            drift = "⚠ 변경" if a.get("action_changed") else "─"
            dropped = a.get("dropped_signal_count", 0)
            lines.append(
                f"  [{ticker}]  전달률={prop:.0%}  {drift}"
                + (f"  신호손실={dropped}" if dropped else "")
            )
        lines.append("")

    # Flags
    flags = cal.get("flags", [])
    if flags:
        lines.append("[⚠ 플래그]")
        for f in flags:
            lines.append(f"  · {f}")
        lines.append("")

    lines.append("=== END CALIBRATION ===")
    return "\n".join(lines)
