"""
Ablation Suite — v3.6 섹션 12.7 기준 12개 변형.
"""
from typing import List, Dict
from dataclasses import dataclass

ABLATION_VARIANTS = [
    "remove_simulated_reward",
    "remove_strategy_memory",
    "remove_market_analysis_meeting",
    "remove_risk_alert_meeting",
    "remove_adaptive_weighting",
    "remove_debate_protocol",
    "remove_execution_feasibility_layer",
    "remove_retrieval_validity_scoring",
    "remove_technical_priority_routing",
    "remove_calibration_layer",
    "remove_propagation_audit",
    "remove_agent_reliability_gating",
]


@dataclass
class AblationConfig:
    variant_name: str
    description: str
    removed_component: str
    expected_degradation: str  # 어떤 성능이 저하될 것으로 예상되는지


ABLATION_CONFIGS = {
    "remove_simulated_reward": AblationConfig(
        variant_name="remove_simulated_reward",
        description="simulated reward를 제거하고 real reward만 사용",
        removed_component="r_sim in CombinedReward",
        expected_degradation="policy stability 저하, forward-looking evaluation 부재",
    ),
    "remove_strategy_memory": AblationConfig(
        variant_name="remove_strategy_memory",
        description="strategy memory retrieval 제거",
        removed_component="StrategyMemory.retrieve()",
        expected_degradation="과거 실패 전략 반복, regime fit 저하",
    ),
    "remove_market_analysis_meeting": AblationConfig(
        variant_name="remove_market_analysis_meeting",
        description="Weekly Market Analysis Meeting 제거",
        removed_component="MarketAnalysisMeeting",
        expected_degradation="regime 해석 품질 저하, debate resolution 부재",
    ),
    "remove_risk_alert_meeting": AblationConfig(
        variant_name="remove_risk_alert_meeting",
        description="Risk Alert Meeting 제거 (단순 threshold check만)",
        removed_component="RiskAlertMeeting",
        expected_degradation="극단적 리스크 상황에서 손실 증가",
    ),
    "remove_adaptive_weighting": AblationConfig(
        variant_name="remove_adaptive_weighting",
        description="w_sim/w_real 고정 (0.5/0.5), adaptive update 제거",
        removed_component="compute_adaptive_weights()",
        expected_degradation="시장 regime 변화에 적응 실패",
    ),
    "remove_debate_protocol": AblationConfig(
        variant_name="remove_debate_protocol",
        description="bull/bear debate sub-step 제거",
        removed_component="MarketAnalysisMeeting._run_debate()",
        expected_degradation="편향 통제 부재, signal conflict 미감지",
    ),
    "remove_execution_feasibility_layer": AblationConfig(
        variant_name="remove_execution_feasibility_layer",
        description="execution feasibility check 제거 (strategy = execution order)",
        removed_component="BobToExecutionPacket, execution_feasibility_check node",
        expected_degradation="비현실적 execution, slippage 증가",
    ),
    "remove_retrieval_validity_scoring": AblationConfig(
        variant_name="remove_retrieval_validity_scoring",
        description="validity scoring 제거, cosine similarity만 사용",
        removed_component="compute_validity_score() — RecencyDecay, RegimeMatch 등 제거",
        expected_degradation="stale/irrelevant case 사용으로 노이즈 증가",
    ),
    "remove_technical_priority_routing": AblationConfig(
        variant_name="remove_technical_priority_routing",
        description="technical signal을 macro/news와 동등하게 처리",
        removed_component="TechnicalSignalState 독립 필드, technical_confidence routing",
        expected_degradation="technical signal adoption rate 저하",
    ),
    "remove_calibration_layer": AblationConfig(
        variant_name="remove_calibration_layer",
        description="calibration 없이 raw score 그대로 상위 단계로 전달",
        removed_component="AgentCalibrator",
        expected_degradation="score drift, noise amplification",
    ),
    "remove_propagation_audit": AblationConfig(
        variant_name="remove_propagation_audit",
        description="propagation audit 제거 (전달됐다고 가정)",
        removed_component="PropagationAuditLog, audit functions",
        expected_degradation="signal 손실 감지 불가, dropped critical signal 증가",
    ),
    "remove_agent_reliability_gating": AblationConfig(
        variant_name="remove_agent_reliability_gating",
        description="모든 agent를 동일 가중으로 신뢰",
        removed_component="AgentReliabilityManager, gating decisions",
        expected_degradation="신뢰도 낮은 agent 출력이 policy에 과도하게 반영",
    ),
}


def get_ablation_config(variant: str) -> AblationConfig:
    if variant not in ABLATION_CONFIGS:
        raise ValueError(f"Unknown ablation variant: {variant}. Available: {ABLATION_VARIANTS}")
    return ABLATION_CONFIGS[variant]


def list_ablations() -> List[str]:
    return list(ABLATION_VARIANTS)


def run_ablation_suite(
    variants: List[str] = None,
    run_fn=None,  # Callable[[AblationConfig], dict] — 각 변형 실행 함수
) -> Dict[str, dict]:
    """
    ablation suite 실행.
    run_fn이 없으면 config만 반환 (dry run).
    """
    variants = variants or ABLATION_VARIANTS
    results = {}
    for v in variants:
        config = get_ablation_config(v)
        if run_fn:
            results[v] = run_fn(config)
        else:
            results[v] = {"config": config, "status": "pending"}
    return results
