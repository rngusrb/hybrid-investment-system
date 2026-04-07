"""
Baseline 비교군 — v3.6 섹션 12.6 기준 9개.

baselines:
1. buy_and_hold
2. mean_variance
3. single_agent_llm
4. multi_agent_no_sim_trading
5. multi_agent_no_risk_alert
6. multi_agent_no_memory
7. multi_agent_no_calibration
8. multi_agent_no_propagation_audit
9. full_hybrid_system
"""
from typing import List, Dict
from dataclasses import dataclass

BASELINE_NAMES = [
    "buy_and_hold",
    "mean_variance",
    "single_agent_llm",
    "multi_agent_no_sim_trading",
    "multi_agent_no_risk_alert",
    "multi_agent_no_memory",
    "multi_agent_no_calibration",
    "multi_agent_no_propagation_audit",
    "full_hybrid_system",
]


@dataclass
class BaselineConfig:
    name: str
    description: str
    disabled_components: List[str]  # 비활성화된 컴포넌트 목록


BASELINE_CONFIGS = {
    "buy_and_hold": BaselineConfig(
        name="buy_and_hold",
        description="단순 buy-and-hold 인덱스",
        disabled_components=["all_agents", "meetings", "risk_alert", "memory"],
    ),
    "mean_variance": BaselineConfig(
        name="mean_variance",
        description="Mean-Variance 최적화 allocator",
        disabled_components=["llm_agents", "meetings", "debate"],
    ),
    "single_agent_llm": BaselineConfig(
        name="single_agent_llm",
        description="단일 LLM agent (multi-agent 없음)",
        disabled_components=["bob", "dave", "meetings", "risk_alert"],
    ),
    "multi_agent_no_sim_trading": BaselineConfig(
        name="multi_agent_no_sim_trading",
        description="simulated trading 없는 multi-agent",
        disabled_components=["simulated_reward"],
    ),
    "multi_agent_no_risk_alert": BaselineConfig(
        name="multi_agent_no_risk_alert",
        description="Risk Alert Meeting 없는 multi-agent",
        disabled_components=["risk_alert_meeting"],
    ),
    "multi_agent_no_memory": BaselineConfig(
        name="multi_agent_no_memory",
        description="memory retrieval 없는 multi-agent",
        disabled_components=["market_memory", "strategy_memory", "retrieval"],
    ),
    "multi_agent_no_calibration": BaselineConfig(
        name="multi_agent_no_calibration",
        description="calibration layer 없는 multi-agent",
        disabled_components=["calibration"],
    ),
    "multi_agent_no_propagation_audit": BaselineConfig(
        name="multi_agent_no_propagation_audit",
        description="propagation audit 없는 multi-agent",
        disabled_components=["propagation_audit"],
    ),
    "full_hybrid_system": BaselineConfig(
        name="full_hybrid_system",
        description="전체 hybrid system (모든 컴포넌트 활성)",
        disabled_components=[],
    ),
}


def get_baseline_config(name: str) -> BaselineConfig:
    if name not in BASELINE_CONFIGS:
        raise ValueError(f"Unknown baseline: {name}. Available: {list(BASELINE_CONFIGS.keys())}")
    return BASELINE_CONFIGS[name]


def list_baselines() -> List[str]:
    return list(BASELINE_NAMES)
