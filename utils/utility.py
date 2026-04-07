"""
공유 utility 계산 함수.
OttoAgent.compute_utility()와 policy_selection 노드가 동일한 공식을 사용하도록
단일 구현으로 통합.

공식:
  U = CombinedReward
      - λ1 * risk_score
      - λ2 * constraint_violation
      - λ3 * market_alignment_penalty
      - λ4 * execution_feasibility_penalty
      - λ5 * agent_reliability_penalty
"""
from __future__ import annotations

# 기본 lambda 값 — config에서 오버라이드 가능
DEFAULT_LAMBDAS = {
    "lambda1": 0.30,  # risk
    "lambda2": 0.20,  # constraint violation
    "lambda3": 0.15,  # market alignment
    "lambda4": 0.20,  # execution feasibility
    "lambda5": 0.15,  # agent reliability
}


def compute_utility(
    combined_reward: float,
    risk_score: float,
    constraint_violation: float = 0.0,
    market_alignment_penalty: float = 0.0,
    execution_feasibility_penalty: float = 0.0,
    agent_reliability_penalty: float = 0.0,
    lambdas: dict | None = None,
) -> float:
    """
    Utility_t(μ) = CombinedReward
                   - λ1*RiskScore
                   - λ2*ConstraintViolation
                   - λ3*MarketAlignment
                   - λ4*ExecutionFeasibility
                   - λ5*AgentReliability

    Args:
        combined_reward: w_sim * r_sim + w_real * r_real (또는 approval 기반 proxy)
        risk_score: Dave R_score [0, 1]
        constraint_violation: 제약 위반 정도 [0, 1]
        market_alignment_penalty: 시장 불확실성 proxy [0, 1]
        execution_feasibility_penalty: 1 - execution_feasibility_score
        agent_reliability_penalty: 1 - avg(agent_reliability)
        lambdas: dict with lambda1..lambda5 override (없으면 DEFAULT_LAMBDAS 사용)

    Returns:
        utility score (unbounded float, 보통 [-1, 1] 범위)
    """
    lam = {**DEFAULT_LAMBDAS, **(lambdas or {})}
    return (
        combined_reward
        - lam["lambda1"] * risk_score
        - lam["lambda2"] * constraint_violation
        - lam["lambda3"] * market_alignment_penalty
        - lam["lambda4"] * execution_feasibility_penalty
        - lam["lambda5"] * agent_reliability_penalty
    )


def compute_utility_from_state(state: dict, approval_status: str, lambdas: dict | None = None) -> float:
    """
    SystemState dict에서 직접 utility를 계산하는 편의 함수.
    policy_selection 노드에서 사용.
    """
    risk_score = state.get("risk_score", 0.5)
    exec_score = state.get("execution_feasibility_score", 0.5)
    uncertainty = state.get("uncertainty_level", 0.5)
    reliability = state.get("agent_reliability", {})

    combined_reward = 0.5 if approval_status in ("approved", "approved_with_modification") else 0.1
    exec_penalty = 1.0 - exec_score
    if reliability:
        avg_rel = sum(reliability.values()) / len(reliability)
        reliability_penalty = max(0.0, 1.0 - avg_rel)
    else:
        reliability_penalty = 0.5

    return compute_utility(
        combined_reward=combined_reward,
        risk_score=risk_score,
        market_alignment_penalty=uncertainty,
        execution_feasibility_penalty=exec_penalty,
        agent_reliability_penalty=reliability_penalty,
        lambdas=lambdas,
    )
