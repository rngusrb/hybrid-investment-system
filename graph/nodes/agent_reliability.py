"""DAILY_AGENT_RELIABILITY_UPDATE node — agent별 신뢰도 갱신.

spec 4.1: DAILY_AGENT_RELIABILITY_UPDATE 상태
spec 4.2 step 3 이후: agent reliability update가 risk check 전에 수행돼야 함

매일 propagation audit log + 전일 도착한 outcome alignment 기반으로 5차원 EMA 업데이트.
"""
from datetime import datetime, timedelta
from graph.state import SystemState
from reliability.agent_reliability import AgentReliabilityManager, GatingDecision
from memory.registry import strategy_memory


def _prev_business_date(date_str: str) -> str:
    """직전 영업일 반환."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ""


def _compute_outcome_alignment(current_date: str) -> float:
    """
    전일 저장된 outcome으로부터 outcome_alignment 계산.
    - approved + 긍정 sim_metrics → 0.7 (잘 예측)
    - rejected/conditional + 부정 → 0.65 (보수적이지만 맞음)
    - 데이터 없으면 0.5 neutral
    """
    prev = _prev_business_date(current_date)
    if not prev:
        return 0.5
    record = strategy_memory._store.get(f"outcome_{prev}")
    if not isinstance(record, dict):
        return 0.5
    outcome = record.get("value", {})
    if not isinstance(outcome, dict):
        return 0.5
    approval = outcome.get("approval_status", "")
    r_sim = float(outcome.get("r_sim", 0.0))
    horizon_closed = outcome.get("horizon_closed", False)
    if not horizon_closed:
        return 0.5
    # approved + 양수 sim return → 좋은 예측
    if approval in ("approved", "approved_with_modification") and r_sim >= 0:
        return 0.72
    # approved + 음수 sim return → 잘못된 예측
    if approval in ("approved", "approved_with_modification") and r_sim < 0:
        return 0.32
    # rejected/conditional + 음수 → 보수적이었지만 맞음
    if approval in ("rejected", "conditional_approval") and r_sim < 0:
        return 0.65
    # rejected + 양수 → 너무 보수적이었음
    return 0.38


def daily_agent_reliability_update(state: SystemState) -> SystemState:
    """
    State의 propagation_audit_log와 calibration_log를 읽어
    AgentReliabilityManager를 업데이트한 뒤 state.agent_reliability를 갱신.

    업데이트 근거:
      - decision_usefulness: 오늘 otto_output이 approved 여부
      - contradiction_penalty: audit log의 has_contradiction 평균
      - propagation_adoption_rate: audit log의 adopted_keyword_rate 평균
      - outcome_alignment: 이전 cycle 결과 없으면 0.5 neutral 유지
      - noise_penalty: retry_log 건수 / 1.0 (최대 1)
    """
    updated = dict(state)
    current_date = state.get("current_date", "")

    agent_names = ["emily", "bob", "dave", "otto"]
    current_reliability = state.get("agent_reliability", {})

    # AgentReliabilityManager 초기화 (현재 state의 score로 seed)
    manager = AgentReliabilityManager(agent_names)
    for name in agent_names:
        if name in current_reliability:
            manager.states[name].score = float(current_reliability[name])

    # propagation audit log에서 신호 추출
    audit_logs = [
        e for e in state.get("propagation_audit_log", [])
        if isinstance(e, dict) and e.get("date") == current_date
    ]

    # 오늘 audit 기록이 있으면 각 agent 업데이트
    if audit_logs:
        avg_adoption = sum(e.get("adopted_keyword_rate", 0.5) for e in audit_logs) / len(audit_logs)
        avg_contradiction = sum(1.0 if e.get("has_contradiction", False) else 0.0 for e in audit_logs) / len(audit_logs)

        # otto_output 기반 decision_usefulness
        otto_output = state.get("otto_output") or {}
        approval = otto_output.get("approval_status", "")
        decision_usefulness = 0.8 if approval in ("approved", "approved_with_modification") else 0.4

        # retry_log 기반 noise_penalty
        retry_count = len([r for r in state.get("retry_log", []) if isinstance(r, dict) and r.get("date") == current_date])
        noise_penalty = min(retry_count * 0.2, 1.0)

        # 전일 outcome으로부터 실제 outcome_alignment 계산
        outcome_alignment = _compute_outcome_alignment(current_date)

        # Emily / Bob / Dave 업데이트 (각 agent 역할에 맞게 분리)
        manager.update_agent(
            "emily",
            decision_usefulness=decision_usefulness,
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=outcome_alignment,
            noise_penalty=noise_penalty,
        )
        manager.update_agent(
            "bob",
            decision_usefulness=decision_usefulness,
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=outcome_alignment,
            noise_penalty=noise_penalty,
        )
        manager.update_agent(
            "dave",
            decision_usefulness=decision_usefulness * 0.9,  # risk analyst는 approved에 덜 민감
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=outcome_alignment,
            noise_penalty=noise_penalty,
        )
        # otto는 policy maker이므로 decision_usefulness 직접 반영
        manager.update_agent(
            "otto",
            decision_usefulness=decision_usefulness,
            contradiction_penalty=0.0,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=outcome_alignment,
            noise_penalty=noise_penalty,
        )

    new_reliability = manager.get_reliability_summary()
    updated["agent_reliability"] = new_reliability

    # HARD_GATE: 해당 agent 출력을 None으로 초기화해 downstream이 stale data 사용 방지
    _AGENT_OUTPUT_FIELDS = {
        "emily": ["emily_output", "emily_to_bob_packet"],
        "bob": ["bob_output", "bob_to_dave_packet", "bob_to_execution_packet"],
        "dave": ["dave_output"],
        "otto": ["otto_output", "otto_policy_packet"],
    }
    gating = manager.get_gating_decisions()
    hard_gated = [name for name, g in gating.items() if g == GatingDecision.HARD_GATE]
    if hard_gated:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "DAILY_AGENT_RELIABILITY_UPDATE",
            "reason": f"hard_gated agents: {hard_gated}",
            "date": current_date,
        }]
        for agent_name in hard_gated:
            for field in _AGENT_OUTPUT_FIELDS.get(agent_name, []):
                updated[field] = None

    updated["calibration_log"] = list(state.get("calibration_log", [])) + [{
        "date": current_date,
        "node": "DAILY_AGENT_RELIABILITY_UPDATE",
        "reliability_snapshot": new_reliability,
        "gating_decisions": {k: v.value for k, v in gating.items()},
    }]

    updated["next_node"] = "DAILY_RISK_CHECK"
    return updated
