"""
Propagation Audit — 하위 signal이 실제로 상위 결정에 반영됐는지 추적.

추적 항목:
- adopted_keyword_rate: 소스 packet의 핵심 키워드가 타겟 요약에 포함된 비율
- dropped_critical_signal_rate: 중요 signal이 타겟에서 누락된 비율
- has_contradiction: transformation 후 방향성 모순 발생 여부
- semantic_similarity_score: source packet vs target summary 유사도 (간단한 token overlap)
- technical_signal_adoption_rate: technical signal이 타겟에 반영된 비율
"""
from typing import Optional, List, Dict
from schemas.audit_schema import PropagationAuditLog


def _token_overlap(text_a: str, text_b: str) -> float:
    """간단한 token overlap 기반 유사도 (0~1)."""
    tokens_a = set(str(text_a).lower().split())
    tokens_b = set(str(text_b).lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def audit_emily_to_bob(
    emily_packet: dict,
    bob_output: dict,
    date: str,
) -> PropagationAuditLog:
    """Emily → Bob 전달에서 signal 손실 여부 감사."""

    # technical signal 전달 여부
    technical_fields = ["technical_direction", "technical_confidence", "reversal_risk"]
    adopted_technical = sum(1 for f in technical_fields if emily_packet.get(f) is not None)
    technical_adoption_rate = adopted_technical / len(technical_fields)

    # Bob의 candidate strategies에서 technical_alignment가 있는지
    candidates = bob_output.get("candidate_strategies", [])
    tech_aligned = sum(1 for c in candidates if c.get("technical_alignment", 0) > 0.0)
    if candidates:
        technical_adoption_rate = min(technical_adoption_rate, tech_aligned / len(candidates))

    # keyword adoption: regime, market_bias가 Bob output에 반영됐는지
    key_terms = [
        str(emily_packet.get("regime", "")),
        str(emily_packet.get("market_bias", "")),
    ]
    bob_text = str(bob_output)
    adopted_keywords = sum(1 for t in key_terms if t and t.lower() in bob_text.lower())
    adopted_keyword_rate = adopted_keywords / len(key_terms) if key_terms else 0.0

    # dropped critical signal: reversal_risk 높은데 Bob에 hedged strategy 없으면 신호 누락
    reversal_risk = emily_packet.get("reversal_risk", 0.0)
    has_hedge = any(c.get("type") in ("hedged", "market_neutral", "defensive") for c in candidates)
    dropped_critical = (reversal_risk > 0.6 and not has_hedge)
    dropped_critical_signal_rate = 1.0 if dropped_critical else 0.0

    # semantic similarity
    emily_text = f"{emily_packet.get('regime','')} {emily_packet.get('market_bias','')} {emily_packet.get('technical_direction','')}"
    bob_strategy_text = " ".join(c.get("logic_summary", "") for c in candidates)
    semantic_sim = _token_overlap(emily_text, bob_strategy_text)

    # contradiction check: Emily가 defensive인데 Bob이 directional long → 모순
    market_bias = emily_packet.get("market_bias", "")
    has_contradiction = (
        market_bias == "defensive" and
        any(c.get("type") == "directional" and c.get("regime_fit", 1.0) > 0.7 for c in candidates)
    )

    return PropagationAuditLog(
        date=date,
        source_agent="Emily",
        target_agent="Bob",
        adopted_keyword_rate=adopted_keyword_rate,
        dropped_critical_signal_rate=dropped_critical_signal_rate,
        has_contradiction=has_contradiction,
        semantic_similarity_score=semantic_sim,
        technical_signal_adoption_rate=technical_adoption_rate,
    )


def audit_bob_to_dave(
    bob_dave_packet: dict,
    dave_output: dict,
    date: str,
) -> PropagationAuditLog:
    """Bob → Dave 전달에서 strategy signal 손실 여부 감사."""

    # strategy_confidence가 dave risk 판단에 반영됐는지
    strategy_confidence = bob_dave_packet.get("strategy_confidence", 0.5)
    risk_level = dave_output.get("risk_level", "medium")

    # low confidence인데 risk_level이 low이면 의심 (Bob의 confidence가 Dave에게 전달 안 된 것)
    has_contradiction = (strategy_confidence < 0.4 and risk_level == "low")

    # technical_alignment가 Dave output에 간접 반영됐는지
    technical_alignment = bob_dave_packet.get("technical_alignment", 0.5)
    recommended_controls = dave_output.get("recommended_controls", [])
    dave_text = str(dave_output)

    # failure_conditions 키워드가 Dave의 recommended_controls에 있는지
    failure_conditions = bob_dave_packet.get("failure_conditions", [])
    adopted_count = sum(
        1 for fc in failure_conditions
        if any(word in dave_text.lower() for word in fc.lower().split())
    )
    adopted_keyword_rate = adopted_count / len(failure_conditions) if failure_conditions else 1.0

    dropped_critical_signal_rate = 1.0 - adopted_keyword_rate

    bob_text = f"{bob_dave_packet.get('strategy_name','')} {' '.join(failure_conditions)}"
    semantic_sim = _token_overlap(bob_text, dave_text)

    return PropagationAuditLog(
        date=date,
        source_agent="Bob",
        target_agent="Dave",
        adopted_keyword_rate=adopted_keyword_rate,
        dropped_critical_signal_rate=dropped_critical_signal_rate,
        has_contradiction=has_contradiction,
        semantic_similarity_score=semantic_sim,
        technical_signal_adoption_rate=min(technical_alignment, 0.9),
    )


def audit_to_otto(
    otto_packet: dict,
    otto_output: dict,
    date: str,
) -> PropagationAuditLog:
    """aggregated packet → Otto 전달에서 최종 policy signal 반영 여부 감사."""

    # risk_score가 otto approval에 반영됐는지
    risk_score = otto_packet.get("risk_score", 0.0)
    approval_status = otto_output.get("approval_status", "")
    trigger_alert = otto_packet.get("trigger_risk_alert", False)

    # high risk인데 approved → 모순
    has_contradiction = (risk_score > 0.75 and approval_status == "approved")

    # reversal_risk와 allocation이 일관성 있는지
    reversal_risk = otto_packet.get("reversal_risk", 0.0)
    allocation = otto_output.get("allocation", {})
    equity_allocation = allocation.get("equities", 0.5)

    # reversal_risk 높은데 equities 높으면 신호 누락
    dropped_critical = (reversal_risk > 0.6 and equity_allocation > 0.7)
    dropped_critical_signal_rate = 1.0 if dropped_critical else 0.0

    # keyword adoption
    key_terms = [
        otto_packet.get("market_regime", ""),
        otto_packet.get("selected_strategy_name", ""),
    ]
    otto_text = str(otto_output)
    adopted = sum(1 for t in key_terms if t and t.lower() in otto_text.lower())
    adopted_keyword_rate = adopted / len(key_terms) if key_terms else 0.0

    packet_text = f"{otto_packet.get('market_regime','')} {otto_packet.get('selected_strategy_name','')}"
    semantic_sim = _token_overlap(packet_text, otto_text)

    technical_confidence = otto_packet.get("technical_confidence", 0.5)

    return PropagationAuditLog(
        date=date,
        source_agent="Aggregator",
        target_agent="Otto",
        adopted_keyword_rate=adopted_keyword_rate,
        dropped_critical_signal_rate=dropped_critical_signal_rate,
        has_contradiction=has_contradiction,
        semantic_similarity_score=semantic_sim,
        technical_signal_adoption_rate=technical_confidence,
    )
