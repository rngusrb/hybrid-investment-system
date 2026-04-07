"""
tests/unit/test_agents.py
Unit tests for BaseAgent, EmilyAgent, BobAgent, DaveAgent, OttoAgent.
All tests use mock LLM — no real API calls.
"""
import json
import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_llm(response_dict: dict):
    mock_llm = MagicMock()
    mock_llm.chat.return_value = json.dumps(response_dict)
    mock_llm.name.return_value = "mock"
    return mock_llm


BASE_CONFIG = {"name": "TestAgent", "max_retries": 3, "agent_confidence_floor": 0.45}


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

VALID_EMILY_OUTPUT = {
    "agent": "Emily",
    "date": "2026-04-01",
    "market_regime": "risk_on",
    "regime_confidence": 0.8,
    "macro_state": {
        "rates": 0.2,
        "inflation": -0.1,
        "growth": 0.5,
        "liquidity": 0.3,
        "risk_sentiment": 0.4,
    },
    "technical_signal_state": {
        "trend_direction": "up",
        "continuation_strength": 0.7,
        "reversal_risk": 0.2,
        "technical_confidence": 0.75,
    },
    "sector_preference": [
        {"sector": "technology", "score": 0.8},
        {"sector": "energy", "score": 0.3},
    ],
    "bull_catalysts": ["Strong earnings growth"],
    "bear_catalysts": ["Rate uncertainty"],
    "event_sensitivity_map": [{"event": "FOMC", "risk_level": 0.4}],
    "technical_conflict_flags": [],
    "risk_flags": [],
    "uncertainty_reasons": ["Mixed signals"],
    "recommended_market_bias": "selective_long",
}

VALID_BOB_OUTPUT = {
    "agent": "Bob",
    "date": "2026-04-01",
    "candidate_strategies": [
        {
            "name": "momentum_tech",
            "type": "momentum",
            "logic_summary": "Buy tech momentum leaders",
            "regime_fit": 0.8,
            "technical_alignment": 0.75,
            "sim_window": {"train_start": "2024-01-01", "train_end": "2025-12-31"},
            "sim_metrics": {
                "return": 0.18,
                "sharpe": 1.4,
                "sortino": 1.8,
                "mdd": 0.12,
                "turnover": 0.25,
                "hit_rate": 0.58,
            },
            "failure_conditions": ["Regime shifts to risk_off", "VIX > 30"],
            "optimization_suggestions": ["Tighten stop-loss"],
            "confidence": 0.72,
        }
    ],
    "selected_for_review": ["momentum_tech"],
}

VALID_DAVE_OUTPUT = {
    "agent": "Dave",
    "date": "2026-04-01",
    "risk_score": 0.45,
    "risk_components": {
        "beta": 0.5,
        "illiquidity": 0.3,
        "sector_concentration": 0.4,
        "volatility": 0.35,
    },
    "signal_conflict_risk": 0.2,
    "stress_test": {"severity_score": 0.4, "worst_case_drawdown": 0.15},
    "risk_level": "medium",
    "recommended_controls": ["Cap single sector at 30%"],
    "risk_constraints": {
        "max_single_sector_weight": 0.3,
        "max_beta": 1.2,
        "max_gross_exposure": 0.95,
    },
    "trigger_risk_alert_meeting": False,
}

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
# 1. BaseAgent — normal run with mock LLM
# ===========================================================================

def test_base_agent_normal_run():
    from agents.base_agent import BaseAgent

    response = {"confidence": 0.8, "result": "ok"}
    llm = make_mock_llm(response)
    agent = BaseAgent(llm=llm, config=BASE_CONFIG)
    result = agent.run(input_packet={"foo": "bar"}, state={})
    assert result == response


# ===========================================================================
# 2. BaseAgent retry — validation failure hits max_retries → RuntimeError
# ===========================================================================

def test_base_agent_retry_raises_after_max_retries():
    from agents.base_agent import BaseAgent

    # LLM always returns invalid JSON
    mock_llm = MagicMock()
    mock_llm.chat.return_value = "NOT VALID JSON !!!"
    mock_llm.name.return_value = "mock"

    agent = BaseAgent(llm=mock_llm, config={**BASE_CONFIG, "max_retries": 3})

    with pytest.raises(RuntimeError) as exc_info:
        agent.run(input_packet={}, state={})

    assert "failed after 3 retries" in str(exc_info.value)
    assert mock_llm.chat.call_count == 3


# ===========================================================================
# 3. BaseAgent._should_retry — confidence < floor → True
# ===========================================================================

def test_base_agent_should_retry_low_confidence():
    from agents.base_agent import BaseAgent

    llm = make_mock_llm({})
    agent = BaseAgent(llm=llm, config={**BASE_CONFIG, "agent_confidence_floor": 0.5})

    should_retry, reason = agent._should_retry({"confidence": 0.3}, attempt=0)
    assert should_retry is True
    assert "0.3" in reason

    should_retry_ok, _ = agent._should_retry({"confidence": 0.6}, attempt=0)
    assert should_retry_ok is False


# ===========================================================================
# 4. EmilyAgent._validate_output — valid dict passes, invalid raises
# ===========================================================================

def test_emily_validate_output_valid():
    from agents.emily import EmilyAgent

    llm = make_mock_llm({})
    agent = EmilyAgent(llm=llm, config=BASE_CONFIG)
    result = agent._validate_output(VALID_EMILY_OUTPUT)
    assert result["market_regime"] == "risk_on"
    assert "technical_signal_state" in result


def test_emily_validate_output_invalid():
    from agents.emily import EmilyAgent

    llm = make_mock_llm({})
    agent = EmilyAgent(llm=llm, config=BASE_CONFIG)

    with pytest.raises((ValidationError, Exception)):
        agent._validate_output({"agent": "Emily", "date": "2026-04-01"})  # missing required fields


# ===========================================================================
# 5. EmilyAgent._should_retry — missing technical_signal_state → retry=True
# ===========================================================================

def test_emily_should_retry_missing_technical_signal():
    from agents.emily import EmilyAgent

    llm = make_mock_llm({})
    agent = EmilyAgent(llm=llm, config=BASE_CONFIG)

    output_missing_ts = {k: v for k, v in VALID_EMILY_OUTPUT.items() if k != "technical_signal_state"}
    should_retry, reason = agent._should_retry(output_missing_ts, attempt=0)
    assert should_retry is True
    assert "technical_signal_state" in reason


def test_emily_should_retry_not_triggered_when_valid():
    from agents.emily import EmilyAgent

    llm = make_mock_llm({})
    agent = EmilyAgent(llm=llm, config=BASE_CONFIG)

    should_retry, _ = agent._should_retry(VALID_EMILY_OUTPUT, attempt=0)
    assert should_retry is False


# ===========================================================================
# 6. EmilyAgent.to_bob_packet — EmilyOutput dict → EmilyToBobPacket dict
# ===========================================================================

def test_emily_to_bob_packet():
    from agents.emily import EmilyAgent

    llm = make_mock_llm({})
    agent = EmilyAgent(llm=llm, config=BASE_CONFIG)
    packet = agent.to_bob_packet(VALID_EMILY_OUTPUT, date="2026-04-01")

    assert packet["source_agent"] == "Emily"
    assert packet["target_agent"] == "Bob"
    assert packet["regime"] == "risk_on"
    assert packet["regime_confidence"] == 0.8
    assert "technology" in packet["preferred_sectors"]
    assert "energy" in packet["avoid_sectors"]
    assert packet["technical_direction"] == "up"
    assert packet["technical_confidence"] == 0.75
    assert packet["reversal_risk"] == 0.2


# ===========================================================================
# 7. BobAgent._validate_output — valid BobOutput passes
# ===========================================================================

def test_bob_validate_output_valid():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)
    result = agent._validate_output(VALID_BOB_OUTPUT)
    assert result["agent"] == "Bob"
    assert len(result["candidate_strategies"]) == 1


def test_bob_validate_output_invalid():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)

    with pytest.raises((ValidationError, Exception)):
        # candidate에 필수 필드(sim_window) 누락 → CandidateStrategy validation 실패
        agent._validate_output({
            "agent": "Bob", "date": "2026-04-01",
            "candidate_strategies": [{"name": "bad", "type": "momentum"}],  # sim_window/sim_metrics 없음
            "selected_for_review": [],
        })


# ===========================================================================
# 8. BobAgent._should_retry — sim_window missing → retry=True
# ===========================================================================

def test_bob_should_retry_missing_sim_window():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)

    output_bad = {
        "candidate_strategies": [
            {
                "name": "bad_strategy",
                "sim_window": {},  # empty — missing train_start
                "failure_conditions": ["some condition"],
            }
        ],
        "selected_for_review": ["bad_strategy"],
    }
    should_retry, reason = agent._should_retry(output_bad, attempt=0)
    assert should_retry is True
    assert "sim_window" in reason


def test_bob_should_retry_no_candidates():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)

    should_retry, reason = agent._should_retry({"candidate_strategies": []}, attempt=0)
    assert should_retry is True


def test_bob_should_retry_missing_failure_conditions():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)

    output_bad = {
        "candidate_strategies": [
            {
                "name": "no_failure_cond",
                "sim_window": {"train_start": "2024-01-01", "train_end": "2025-12-31"},
                "failure_conditions": [],  # empty list — falsy
            }
        ]
    }
    should_retry, reason = agent._should_retry(output_bad, attempt=0)
    assert should_retry is True
    assert "failure_conditions" in reason


# ===========================================================================
# 9. BobAgent.to_dave_packet — BobToDavePacket generated correctly
# ===========================================================================

def test_bob_to_dave_packet():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)
    packet = agent.to_dave_packet(VALID_BOB_OUTPUT, date="2026-04-01")

    assert packet["source_agent"] == "Bob"
    assert packet["target_agent"] == "Dave"
    assert packet["strategy_name"] == "momentum_tech"
    assert packet["strategy_confidence"] == 0.72
    assert packet["technical_alignment"] == 0.75
    assert isinstance(packet["failure_conditions"], list)


# ===========================================================================
# 10. BobAgent.to_execution_packet — BobToExecutionPacket generated correctly
# ===========================================================================

def test_bob_to_execution_packet():
    from agents.bob import BobAgent

    llm = make_mock_llm({})
    agent = BobAgent(llm=llm, config=BASE_CONFIG)
    packet = agent.to_execution_packet(VALID_BOB_OUTPUT, date="2026-04-01")

    assert packet["source_agent"] == "Bob"
    assert packet["target_agent"] == "Execution"
    assert packet["selected_strategy_name"] == "momentum_tech"
    assert packet["hedge_preference"] == "none"  # technical_alignment=0.75 >= 0.6
    assert 0.0 <= packet["rebalance_urgency"] <= 1.0


# ===========================================================================
# 11. DaveAgent._validate_output — risk_score > 0.75 → trigger forced True
# ===========================================================================

def test_dave_validate_output_forces_trigger_when_high_risk():
    from agents.dave import DaveAgent

    llm = make_mock_llm({})
    agent = DaveAgent(llm=llm, config=BASE_CONFIG)

    # risk_score는 컴포넌트 가중합으로 덮어쓰므로 컴포넌트를 0.75 초과가 되도록 설정
    # 0.3*1.0 + 0.25*1.0 + 0.25*1.0 + 0.2*1.0 = 1.0 > 0.75
    high_risk_components = {"beta": 1.0, "illiquidity": 1.0, "sector_concentration": 1.0, "volatility": 1.0}
    high_risk_output = {**VALID_DAVE_OUTPUT, "risk_components": high_risk_components, "trigger_risk_alert_meeting": False}
    result = agent._validate_output(high_risk_output)
    assert result["trigger_risk_alert_meeting"] is True


def test_dave_validate_output_no_trigger_when_low_risk():
    from agents.dave import DaveAgent

    llm = make_mock_llm({})
    agent = DaveAgent(llm=llm, config=BASE_CONFIG)

    result = agent._validate_output(VALID_DAVE_OUTPUT)  # risk_score = 0.45
    assert result["trigger_risk_alert_meeting"] is False


# ===========================================================================
# 12. DaveAgent.compute_risk_score — weighted sum formula
# ===========================================================================

def test_dave_compute_risk_score():
    from agents.dave import DaveAgent

    llm = make_mock_llm({})
    agent = DaveAgent(llm=llm, config=BASE_CONFIG)

    components = {"beta": 1.0, "illiquidity": 1.0, "sector_concentration": 1.0, "volatility": 1.0}
    score = agent.compute_risk_score(components)
    assert abs(score - 1.0) < 1e-6  # all 1.0 → should cap at 1.0

    components_partial = {"beta": 0.5, "illiquidity": 0.0, "sector_concentration": 0.0, "volatility": 0.0}
    score_partial = agent.compute_risk_score(components_partial)
    expected = 0.3 * 0.5  # only beta contributes
    assert abs(score_partial - expected) < 1e-6


def test_dave_compute_risk_score_formula():
    from agents.dave import DaveAgent

    llm = make_mock_llm({})
    agent = DaveAgent(llm=llm, config=BASE_CONFIG)

    components = {"beta": 0.8, "illiquidity": 0.6, "sector_concentration": 0.4, "volatility": 0.5}
    # R = 0.3*0.8 + 0.25*0.6 + 0.25*0.4 + 0.2*0.5
    expected = 0.3 * 0.8 + 0.25 * 0.6 + 0.25 * 0.4 + 0.2 * 0.5
    score = agent.compute_risk_score(components)
    assert abs(score - expected) < 1e-6


# ===========================================================================
# 13. OttoAgent._block_raw_data_access — raw_news → ValueError
# ===========================================================================

def test_otto_blocks_raw_news():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    with pytest.raises(ValueError) as exc_info:
        agent._block_raw_data_access({"raw_news": ["article1"], "market_regime": "risk_on"})
    assert "raw_news" in str(exc_info.value)


# ===========================================================================
# 14. OttoAgent._block_raw_data_access — raw_ohlcv → ValueError
# ===========================================================================

def test_otto_blocks_raw_ohlcv():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    with pytest.raises(ValueError) as exc_info:
        agent._block_raw_data_access({"raw_ohlcv": [[100, 101, 99, 100, 1000]]})
    assert "raw_ohlcv" in str(exc_info.value)


# ===========================================================================
# 15. OttoAgent._block_raw_data_access — clean packet passes
# ===========================================================================

def test_otto_allows_clean_packet():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    # Should not raise
    clean_packet = {
        "market_regime": "risk_on",
        "selected_strategy_name": "momentum_tech",
        "risk_score": 0.45,
    }
    agent._block_raw_data_access(clean_packet)


# ===========================================================================
# 16. OttoAgent.compute_utility — penalty reduces utility
# ===========================================================================

def test_otto_compute_utility_formula():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    lambdas = {"lambda1": 0.3, "lambda2": 0.2, "lambda3": 0.15, "lambda4": 0.2, "lambda5": 0.15}
    utility_no_penalty = agent.compute_utility(
        combined_reward=1.0,
        risk_score=0.0,
        lambdas=lambdas,
    )
    utility_with_penalty = agent.compute_utility(
        combined_reward=1.0,
        risk_score=0.5,
        lambdas=lambdas,
    )
    assert utility_no_penalty > utility_with_penalty


def test_otto_compute_utility_higher_penalty_lower_utility():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    lambdas = {"lambda1": 0.3, "lambda2": 0.2, "lambda3": 0.15, "lambda4": 0.2, "lambda5": 0.15}

    u_low = agent.compute_utility(
        combined_reward=0.5,
        risk_score=0.1,
        constraint_violation=0.0,
        lambdas=lambdas,
    )
    u_high_penalty = agent.compute_utility(
        combined_reward=0.5,
        risk_score=0.8,
        constraint_violation=0.5,
        market_alignment_penalty=0.4,
        execution_feasibility_penalty=0.3,
        agent_reliability_penalty=0.2,
        lambdas=lambdas,
    )
    assert u_low > u_high_penalty


def test_otto_compute_utility_exact():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    lambdas = {"lambda1": 0.3, "lambda2": 0.2, "lambda3": 0.15, "lambda4": 0.2, "lambda5": 0.15}
    result = agent.compute_utility(
        combined_reward=1.0,
        risk_score=0.5,
        constraint_violation=0.2,
        market_alignment_penalty=0.1,
        execution_feasibility_penalty=0.1,
        agent_reliability_penalty=0.1,
        lambdas=lambdas,
    )
    expected = 1.0 - 0.3 * 0.5 - 0.2 * 0.2 - 0.15 * 0.1 - 0.2 * 0.1 - 0.15 * 0.1
    assert abs(result - expected) < 1e-9


# ===========================================================================
# 17. OttoAgent.compute_adaptive_weights — w_sim + w_real = 1.0
# ===========================================================================

def test_otto_adaptive_weights_sum_to_one():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    reward_history = [
        {"r_sim": 0.6, "r_real": 0.4},
        {"r_sim": 0.5, "r_real": 0.5},
        {"r_sim": 0.7, "r_real": 0.3},
    ]
    weights = agent.compute_adaptive_weights(reward_history)
    assert abs(weights["w_sim"] + weights["w_real"] - 1.0) < 1e-4


def test_otto_adaptive_weights_empty_history():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    weights = agent.compute_adaptive_weights([])
    assert weights["w_sim"] == 0.5
    assert weights["w_real"] == 0.5


# ===========================================================================
# 18. OttoAgent._should_retry — invalid approval_status → retry=True
# ===========================================================================

def test_otto_should_retry_invalid_approval_status():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    bad_output = {**VALID_OTTO_OUTPUT, "approval_status": "maybe"}
    should_retry, reason = agent._should_retry(bad_output, attempt=0)
    assert should_retry is True
    assert "approval_status" in reason


def test_otto_should_retry_not_triggered_when_valid():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    should_retry, _ = agent._should_retry(VALID_OTTO_OUTPUT, attempt=0)
    assert should_retry is False


def test_otto_should_retry_missing_selected_policy():
    from agents.otto import OttoAgent

    llm = make_mock_llm(VALID_OTTO_OUTPUT)
    agent = OttoAgent(llm=llm, config=BASE_CONFIG)

    bad_output = {**VALID_OTTO_OUTPUT, "selected_policy": ""}
    should_retry, reason = agent._should_retry(bad_output, attempt=0)
    assert should_retry is True
    assert "selected_policy" in reason
