"""MEMORY_CONSOLIDATION node — 주간 사이클 종료 후 통합.

spec 4.3 step 9: memory consolidation
weekly propagation audit 결과를 바탕으로 4개 agent의 reliability를 모두 업데이트.
"""
from graph.state import SystemState
from reliability.agent_reliability import AgentReliabilityManager


def memory_consolidation(state: SystemState) -> SystemState:
    """
    주간 propagation audit 결과를 읽어 all agent reliability를 업데이트.
    - adopted_keyword_rate → propagation_adoption_rate
    - has_contradiction → contradiction_penalty
    - technical_signal_adoption_rate → Emily 특화 dimension
    - weekly_strategy_set rejection_reasons → Bob noise_penalty
    - risk_alert_triggered → Dave decision_usefulness
    """
    updated = dict(state)
    current_date = state.get("current_date", "")
    agent_names = ["emily", "bob", "dave", "otto"]

    # 현재 reliability로 manager seed
    current_reliability = state.get("agent_reliability", {})
    manager = AgentReliabilityManager(agent_names)
    for name in agent_names:
        if name in current_reliability:
            manager.states[name].score = float(current_reliability[name])

    # 이번 주 propagation audit 결과 집계
    weekly_audits = [
        e for e in state.get("propagation_audit_log", [])
        if isinstance(e, dict)
        and e.get("date") == current_date
        and "adopted_keyword_rate" in e   # PropagationAuditLog 엔트리 식별
    ]

    if weekly_audits:
        avg_adoption = sum(e.get("adopted_keyword_rate", 0.5) for e in weekly_audits) / len(weekly_audits)
        avg_tech_adoption = sum(e.get("technical_signal_adoption_rate", 0.5) for e in weekly_audits) / len(weekly_audits)
        avg_contradiction = sum(1.0 if e.get("has_contradiction", False) else 0.0 for e in weekly_audits) / len(weekly_audits)
        avg_semantic = sum(e.get("semantic_similarity_score", 0.5) for e in weekly_audits) / len(weekly_audits)

        # approval_status 기반 decision_usefulness
        otto_output = state.get("otto_output") or {}
        approval = otto_output.get("approval_status", "")
        decision_usefulness = 0.85 if approval in ("approved", "approved_with_modification") else 0.45

        # weekly_strategy_set rejection 비율 → Bob noise_penalty
        strategy_set = state.get("weekly_strategy_set") or {}
        rejection_reasons = strategy_set.get("rejection_reasons") or {}
        candidate_count = len(strategy_set.get("candidate_strategies", [])) or 1
        bob_noise = min(len(rejection_reasons) / candidate_count, 1.0)

        # risk_alert → Dave가 유용하게 기여했는지 여부
        risk_alert = state.get("risk_alert_triggered", False)
        dave_usefulness = 0.9 if risk_alert else decision_usefulness

        manager.update_agent(
            "emily",
            decision_usefulness=avg_tech_adoption,       # technical signal이 얼마나 채택됐는가
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=avg_semantic,
            noise_penalty=0.0,
        )
        manager.update_agent(
            "bob",
            decision_usefulness=decision_usefulness,
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=0.5,                       # weekly에서는 아직 outcome 미확정
            noise_penalty=bob_noise,
        )
        manager.update_agent(
            "dave",
            decision_usefulness=dave_usefulness,
            contradiction_penalty=0.0,                   # Dave는 risk 경보 역할 — contradiction 불필요
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=0.5,
            noise_penalty=0.0,
        )
        manager.update_agent(
            "otto",
            decision_usefulness=decision_usefulness,
            contradiction_penalty=avg_contradiction,
            propagation_adoption_rate=avg_adoption,
            outcome_alignment=avg_semantic,
            noise_penalty=0.0,
        )

    new_reliability = manager.get_reliability_summary()
    updated["agent_reliability"] = new_reliability

    updated["calibration_log"] = list(state.get("calibration_log", [])) + [{
        "date": current_date,
        "node": "MEMORY_CONSOLIDATION",
        "agent_reliability_final": new_reliability,
        "weekly_audit_count": len(weekly_audits),
    }]

    updated["next_node"] = None   # 주간 사이클 완료
    return updated
