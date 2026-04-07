"""
tests/unit/test_reliability.py

Phase 8: Agent Reliability & Conditional Gating 단위 테스트.
총 19개 테스트 케이스.
"""
import pytest
from unittest.mock import MagicMock
import json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_llm(response_dict: dict):
    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps(response_dict)
    mock_llm.name.return_value = "mock"
    return mock_llm


VALID_OTTO_OUTPUT = {
    "agent": "Otto",
    "date": "2026-04-01",
    "candidate_policies": ["momentum_tech", "defensive_bond"],
    "adaptive_weights": {"w_sim": 0.55, "w_real": 0.45, "lookback_steps": 10},
    "selected_policy": "momentum_tech",
    "allocation": {"equities": 0.65, "hedge": 0.15, "cash": 0.2},
    "execution_plan": {
        "entry_style": "staggered",
        "rebalance_frequency": "weekly",
        "stop_loss": 0.08,
    },
    "policy_reasoning_summary": ["Risk-on regime favors momentum", "Low risk score"],
    "approval_status": "approved",
}


# ===========================================================================
# 1. ReliabilityState — cold start score = 0.5
# ===========================================================================

def test_reliability_state_cold_start():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="emily")
    assert state.score == 0.5, "cold start score must be 0.5 (neutral)"


# ===========================================================================
# 2. ReliabilityState.update() — decision_usefulness=1.0 → score 증가
# ===========================================================================

def test_reliability_state_update_increases_score():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="emily", score=0.5)
    state.update(
        decision_usefulness=1.0,
        contradiction_penalty=0.0,
        propagation_adoption_rate=1.0,
        outcome_alignment=1.0,
        noise_penalty=0.0,
    )
    assert state.score > 0.5, "perfect feedback must increase score above 0.5"


# ===========================================================================
# 3. ReliabilityState.update() — contradiction_penalty=1.0 → score 감소
# ===========================================================================

def test_reliability_state_update_decreases_score():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="emily", score=0.5)
    state.update(
        decision_usefulness=0.0,
        contradiction_penalty=1.0,
        propagation_adoption_rate=0.0,
        outcome_alignment=0.0,
        noise_penalty=1.0,
    )
    assert state.score < 0.5, "worst feedback must decrease score below 0.5"


# ===========================================================================
# 4. ReliabilityState.update() — score는 항상 [0, 1] 범위 유지
# ===========================================================================

def test_reliability_state_score_clamped():
    from reliability.agent_reliability import ReliabilityState

    # 극단적으로 좋은 업데이트를 반복
    state = ReliabilityState(agent_name="emily", score=0.99)
    for _ in range(100):
        state.update(decision_usefulness=1.0, contradiction_penalty=0.0,
                     propagation_adoption_rate=1.0, outcome_alignment=1.0, noise_penalty=0.0)
    assert 0.0 <= state.score <= 1.0, "score must remain in [0, 1]"

    # 극단적으로 나쁜 업데이트를 반복
    state2 = ReliabilityState(agent_name="bob", score=0.01)
    for _ in range(100):
        state2.update(decision_usefulness=0.0, contradiction_penalty=1.0,
                      propagation_adoption_rate=0.0, outcome_alignment=0.0, noise_penalty=1.0)
    assert 0.0 <= state2.score <= 1.0, "score must remain in [0, 1]"


# ===========================================================================
# 5. ReliabilityState.get_gating_decision() — score > floor+0.1 → FULL
# ===========================================================================

def test_gating_decision_full():
    from reliability.agent_reliability import ReliabilityState, GatingDecision

    state = ReliabilityState(agent_name="emily", score=0.8, floor=0.35)
    assert state.get_gating_decision() == GatingDecision.FULL


# ===========================================================================
# 6. ReliabilityState.get_gating_decision() — score = floor+0.05 → DOWNWEIGHT
# ===========================================================================

def test_gating_decision_downweight():
    from reliability.agent_reliability import ReliabilityState, GatingDecision

    # floor=0.35, floor+0.05=0.40 → DOWNWEIGHT 구간 (floor <= score < floor+0.1)
    state = ReliabilityState(agent_name="bob", score=0.40, floor=0.35)
    assert state.get_gating_decision() == GatingDecision.DOWNWEIGHT


# ===========================================================================
# 7. ReliabilityState.get_gating_decision() — score < floor → HARD_GATE
# ===========================================================================

def test_gating_decision_hard_gate():
    from reliability.agent_reliability import ReliabilityState, GatingDecision

    state = ReliabilityState(agent_name="dave", score=0.20, floor=0.35)
    assert state.get_gating_decision() == GatingDecision.HARD_GATE


# ===========================================================================
# 8. ReliabilityState.get_weight_multiplier() — HARD_GATE → 0.0
# ===========================================================================

def test_weight_multiplier_hard_gate_is_zero():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="dave", score=0.20, floor=0.35)
    assert state.get_weight_multiplier() == 0.0, "HARD_GATE must return weight multiplier 0.0"


# ===========================================================================
# 9. ReliabilityState.get_weight_multiplier() — FULL → 1.0
# ===========================================================================

def test_weight_multiplier_full_is_one():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="emily", score=0.8, floor=0.35)
    assert state.get_weight_multiplier() == 1.0, "FULL must return weight multiplier 1.0"


# ===========================================================================
# 10. AgentReliabilityManager — 초기화 시 모든 agent score = 0.5 (cold start)
# ===========================================================================

def test_manager_cold_start_all_agents():
    from reliability.agent_reliability import AgentReliabilityManager

    agent_names = ["emily", "bob", "dave"]
    manager = AgentReliabilityManager(agent_names=agent_names)

    for name in agent_names:
        assert manager.states[name].score == 0.5, (
            f"cold start: agent '{name}' score must be 0.5"
        )


# ===========================================================================
# 11. AgentReliabilityManager.update_agent() — 특정 agent만 업데이트
# ===========================================================================

def test_manager_update_only_target_agent():
    from reliability.agent_reliability import AgentReliabilityManager

    agent_names = ["emily", "bob", "dave"]
    manager = AgentReliabilityManager(agent_names=agent_names)

    # emily만 완벽한 피드백으로 업데이트
    manager.update_agent("emily", decision_usefulness=1.0, contradiction_penalty=0.0,
                         propagation_adoption_rate=1.0, outcome_alignment=1.0, noise_penalty=0.0)

    assert manager.states["emily"].score > 0.5, "emily score must increase after positive update"
    assert manager.states["bob"].score == 0.5, "bob score must remain untouched"
    assert manager.states["dave"].score == 0.5, "dave score must remain untouched"


# ===========================================================================
# 12. AgentReliabilityManager.get_reliability_summary() — dict 반환, 모든 agent 포함
# ===========================================================================

def test_manager_get_reliability_summary():
    from reliability.agent_reliability import AgentReliabilityManager

    agent_names = ["emily", "bob", "dave"]
    manager = AgentReliabilityManager(agent_names=agent_names)
    summary = manager.get_reliability_summary()

    assert isinstance(summary, dict), "reliability summary must be a dict"
    for name in agent_names:
        assert name in summary, f"summary must include '{name}'"
        assert isinstance(summary[name], float), f"score for '{name}' must be float"


# ===========================================================================
# 13. AgentReliabilityManager.compute_reliability_penalty() — 신뢰도 낮으면 penalty 높음
# ===========================================================================

def test_penalty_high_when_reliability_low():
    from reliability.agent_reliability import AgentReliabilityManager

    manager = AgentReliabilityManager(agent_names=["emily", "bob", "dave"])

    # 모든 agent를 낮은 신뢰도로 강제 설정
    for name in ["emily", "bob", "dave"]:
        manager.states[name].score = 0.1

    penalty = manager.compute_reliability_penalty(
        selected_strategy_source="bob",
        market_analysis_source="emily",
        risk_source="dave",
    )
    # avg_reliability = 0.1 → penalty = 1 - 0.1 = 0.9
    assert penalty > 0.8, f"low reliability must produce high penalty, got {penalty}"


# ===========================================================================
# 14. AgentReliabilityManager.compute_reliability_penalty() — 신뢰도 높으면 penalty 낮음
# ===========================================================================

def test_penalty_low_when_reliability_high():
    from reliability.agent_reliability import AgentReliabilityManager

    manager = AgentReliabilityManager(agent_names=["emily", "bob", "dave"])

    # 모든 agent를 높은 신뢰도로 설정
    for name in ["emily", "bob", "dave"]:
        manager.states[name].score = 0.9

    penalty = manager.compute_reliability_penalty(
        selected_strategy_source="bob",
        market_analysis_source="emily",
        risk_source="dave",
    )
    # avg_reliability = 0.9 → penalty = 1 - 0.9 = 0.1
    assert penalty < 0.2, f"high reliability must produce low penalty, got {penalty}"


# ===========================================================================
# 15. AgentReliabilityManager.get_active_agents_for_regime() — HARD_GATE agent 제외
# ===========================================================================

def test_active_agents_excludes_hard_gated():
    from reliability.agent_reliability import AgentReliabilityManager

    agent_names = ["emily", "bob", "dave"]
    manager = AgentReliabilityManager(agent_names=agent_names)

    # dave를 HARD_GATE 수준으로 낮춤
    manager.states["dave"].score = 0.20  # floor=0.35 미만

    active = manager.get_active_agents_for_regime("default")
    assert "dave" not in active, "HARD_GATE agent must be excluded from active list"
    assert "emily" in active
    assert "bob" in active


# ===========================================================================
# 16. AgentReliabilityManager.apply_reliability_to_otto_packet() — reliability_summary 삽입
# ===========================================================================

def test_apply_reliability_to_otto_packet():
    from reliability.agent_reliability import AgentReliabilityManager

    agent_names = ["emily", "bob", "dave"]
    manager = AgentReliabilityManager(agent_names=agent_names)

    base_packet = {"market_regime": "risk_on", "risk_score": 0.4}
    updated = manager.apply_reliability_to_otto_packet(base_packet)

    assert "agent_reliability_summary" in updated, "packet must contain agent_reliability_summary"
    summary = updated["agent_reliability_summary"]
    for name in agent_names:
        assert name in summary, f"reliability_summary must include '{name}'"
    # 원본 패킷 훼손 없이 새 dict 반환
    assert "agent_reliability_summary" not in base_packet, "original packet must not be mutated"


# ===========================================================================
# 17. OttoAgent.compute_utility() — reliability_penalty 높을수록 utility 낮아짐
# ===========================================================================

def test_otto_compute_utility_reliability_penalty_effect():
    from agents.otto import OttoAgent
    from reliability.agent_reliability import AgentReliabilityManager

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    otto = OttoAgent(llm=llm, config={"name": "Otto", "max_retries": 3})

    agent_names = ["emily", "bob", "dave"]
    lambdas = {"lambda1": 0.3, "lambda2": 0.2, "lambda3": 0.15, "lambda4": 0.2, "lambda5": 0.15}

    # 높은 신뢰도 시나리오
    manager_high = AgentReliabilityManager(agent_names=agent_names)
    for name in agent_names:
        manager_high.states[name].score = 0.9
    penalty_high_rel = manager_high.compute_reliability_penalty()

    # 낮은 신뢰도 시나리오
    manager_low = AgentReliabilityManager(agent_names=agent_names)
    for name in agent_names:
        manager_low.states[name].score = 0.2
    penalty_low_rel = manager_low.compute_reliability_penalty()

    utility_high_rel = otto.compute_utility(
        combined_reward=0.8,
        risk_score=0.3,
        agent_reliability_penalty=penalty_high_rel,
        lambdas=lambdas,
    )
    utility_low_rel = otto.compute_utility(
        combined_reward=0.8,
        risk_score=0.3,
        agent_reliability_penalty=penalty_low_rel,
        lambdas=lambdas,
    )

    assert utility_high_rel > utility_low_rel, (
        "higher agent reliability must produce higher utility "
        f"(got high_rel={utility_high_rel:.4f}, low_rel={utility_low_rel:.4f})"
    )


# ===========================================================================
# 18. 여러 번 update 후 history 누적 확인
# ===========================================================================

def test_reliability_state_history_accumulates():
    from reliability.agent_reliability import ReliabilityState

    state = ReliabilityState(agent_name="emily")
    n_updates = 5
    for _ in range(n_updates):
        state.update(decision_usefulness=0.7)

    assert state.update_count == n_updates, f"update_count must be {n_updates}"
    assert len(state.history) == n_updates, f"history length must be {n_updates}"
    # history의 마지막 값이 현재 score와 일치
    assert state.history[-1] == state.score


# ===========================================================================
# 19. floor=0.35 미만으로 score가 내려가면 HARD_GATE 확인
# ===========================================================================

def test_hard_gate_triggered_below_floor():
    from reliability.agent_reliability import ReliabilityState, GatingDecision

    state = ReliabilityState(agent_name="dave", floor=0.35)

    # 최악의 피드백을 반복해서 score를 floor 미만으로 끌어내림
    for _ in range(50):
        state.update(
            decision_usefulness=0.0,
            contradiction_penalty=1.0,
            propagation_adoption_rate=0.0,
            outcome_alignment=0.0,
            noise_penalty=1.0,
        )

    assert state.score < 0.35, (
        f"score should drop below floor=0.35 after repeated bad updates, got {state.score:.4f}"
    )
    assert state.get_gating_decision() == GatingDecision.HARD_GATE, (
        "score below floor must result in HARD_GATE decision"
    )
