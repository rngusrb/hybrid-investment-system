"""WEEKLY_PROPAGATION_AUDIT node — 실제 audit 함수 호출.

spec 4.3 step 8: propagation audit
audit/propagation_audit.py의 실제 함수를 사용하여
Emily→Bob, Bob→Dave, Aggregator→Otto 세 구간의 signal 전파를 감사.
"""
from graph.state import SystemState
from audit.propagation_audit import audit_emily_to_bob, audit_bob_to_dave, audit_to_otto
from ledger.shared_ledger import SharedLedger


def weekly_propagation_audit(state: SystemState) -> SystemState:
    """
    주간 전파 감사:
      1. Emily→Bob: technical signal 전달 여부
      2. Bob→Dave: strategy signal 전달 여부
      3. Aggregator→Otto: 최종 policy 반영 여부
    결과는 propagation_audit_log에 누적하고 Ledger에도 기록.
    """
    updated = dict(state)
    current_date = state.get("current_date", "")

    emily_packet = state.get("emily_to_bob_packet") or {}
    bob_output = state.get("bob_output") or {}
    bob_dave_packet = state.get("bob_to_dave_packet") or {}
    dave_output = state.get("dave_output") or {}
    otto_packet = state.get("otto_policy_packet") or {}
    otto_output = state.get("otto_output") or {}

    audit_logs = list(state.get("propagation_audit_log", []))
    audit_summaries = []

    # ① Emily → Bob
    if emily_packet and bob_output:
        log_eb = audit_emily_to_bob(emily_packet, bob_output, current_date)
        audit_logs.append(log_eb.model_dump())
        audit_summaries.append(log_eb.model_dump())

    # ② Bob → Dave
    if bob_dave_packet and dave_output:
        log_bd = audit_bob_to_dave(bob_dave_packet, dave_output, current_date)
        audit_logs.append(log_bd.model_dump())
        audit_summaries.append(log_bd.model_dump())

    # ③ Aggregator → Otto
    if otto_packet and otto_output:
        log_ao = audit_to_otto(otto_packet, otto_output, current_date)
        audit_logs.append(log_ao.model_dump())
        audit_summaries.append(log_ao.model_dump())

    updated["propagation_audit_log"] = audit_logs

    # weekly summary를 Ledger에 기록
    if audit_summaries:
        weekly_summary = {
            "date": current_date,
            "audit_count": len(audit_summaries),
            "avg_adoption_rate": sum(s["adopted_keyword_rate"] for s in audit_summaries) / len(audit_summaries),
            "avg_technical_adoption": sum(s["technical_signal_adoption_rate"] for s in audit_summaries) / len(audit_summaries),
            "any_contradiction": any(s["has_contradiction"] for s in audit_summaries),
            "avg_semantic_similarity": sum(s["semantic_similarity_score"] for s in audit_summaries) / len(audit_summaries),
            "details": audit_summaries,
        }

        # Ledger에 weekly_propagation_audit_summary 기록
        ledger = state.get("_ledger")  # Orchestrator가 state에 주입한 경우
        if ledger is None:
            ledger = SharedLedger()
        try:
            ledger.record("weekly_propagation_audit_summary", weekly_summary, current_date, "PropagationAudit")
        except ValueError:
            pass  # ledger가 state에 없으면 skip (ledger는 Orchestrator 레벨에서 관리)

    updated["next_node"] = "MEMORY_CONSOLIDATION"
    return updated
