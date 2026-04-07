"""
tests.unit.test_transforms - Unit tests for agent output transform functions.
Phase 6: Transformation Layer 검증.
"""

import pytest
from pydantic import ValidationError

from transforms.emily_to_bob import transform_emily_to_bob
from transforms.bob_to_dave import transform_bob_to_dave
from transforms.bob_to_execution import transform_bob_to_execution
from transforms.all_to_otto import transform_all_to_otto


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def emily_output_base():
    return {
        "agent": "Emily",
        "date": "2026-04-01",
        "market_regime": "risk_on",
        "regime_confidence": 0.75,
        "macro_state": {
            "rates": 0.2,
            "inflation": -0.1,
            "growth": 0.4,
            "liquidity": 0.3,
            "risk_sentiment": 0.5,
        },
        "technical_signal_state": {
            "trend_direction": "up",
            "continuation_strength": 0.7,
            "reversal_risk": 0.25,
            "technical_confidence": 0.8,
        },
        "sector_preference": [
            {"sector": "tech", "score": 0.8},
            {"sector": "healthcare", "score": 0.5},
            {"sector": "utilities", "score": 0.3},
            {"sector": "energy", "score": 0.65},
        ],
        "bull_catalysts": ["strong earnings", "rate cut expectations"],
        "bear_catalysts": ["geopolitical tension"],
        "event_sensitivity_map": [
            {"event": "FOMC", "risk_level": 0.6},
            {"event": "CPI", "risk_level": 0.4},
        ],
        "technical_conflict_flags": [],
        "risk_flags": ["elevated volatility"],
        "uncertainty_reasons": ["macro data mixed", "geopolitical risk"],
        "recommended_market_bias": "selective_long",
    }


@pytest.fixture
def emily_output_no_events(emily_output_base):
    data = dict(emily_output_base)
    data["event_sensitivity_map"] = []
    return data


@pytest.fixture
def bob_output_base():
    return {
        "agent": "Bob",
        "date": "2026-04-01",
        "candidate_strategies": [
            {
                "name": "momentum_tech",
                "type": "momentum",
                "logic_summary": "momentum on tech sector with trailing stop",
                "regime_fit": 0.8,
                "technical_alignment": 0.75,
                "sim_window": {
                    "train_start": "2024-01-01",
                    "train_end": "2025-12-31",
                },
                "sim_metrics": {
                    "return": 0.18,
                    "sharpe": 1.4,
                    "sortino": 1.8,
                    "mdd": 0.12,
                    "turnover": 0.25,
                    "hit_rate": 0.58,
                },
                "failure_conditions": ["regime flips to risk_off", "vol spike > 30%"],
                "optimization_suggestions": ["tighten stop loss in fragile_rebound"],
                "confidence": 0.78,
            },
            {
                "name": "defensive_hedge",
                "type": "hedged",
                "logic_summary": "long defensive, short beta",
                "regime_fit": 0.5,
                "technical_alignment": 0.35,
                "sim_window": {
                    "train_start": "2024-01-01",
                    "train_end": "2025-12-31",
                },
                "sim_metrics": {
                    "return": 0.08,
                    "sharpe": 0.9,
                    "sortino": 1.1,
                    "mdd": 0.07,
                    "turnover": 0.15,
                    "hit_rate": 0.52,
                },
                "failure_conditions": ["sustained risk_on rally"],
                "optimization_suggestions": [],
                "confidence": 0.55,
            },
        ],
        "selected_for_review": ["momentum_tech"],
    }


@pytest.fixture
def dave_output_base():
    return {
        "agent": "Dave",
        "date": "2026-04-01",
        "risk_score": 0.45,
        "risk_components": {
            "beta": 0.9,
            "illiquidity": 0.1,
            "sector_concentration": 0.3,
            "volatility": 0.2,
        },
        "signal_conflict_risk": 0.2,
        "stress_test": {
            "severity_score": 0.4,
            "worst_case_drawdown": 0.15,
        },
        "risk_level": "medium",
        "recommended_controls": ["reduce tech weight if vol spikes"],
        "risk_constraints": {
            "max_single_sector_weight": 0.35,
            "max_beta": 1.2,
            "max_gross_exposure": 0.95,
        },
        "trigger_risk_alert_meeting": False,
    }


@pytest.fixture
def dave_output_high_risk(dave_output_base):
    data = dict(dave_output_base)
    data["risk_score"] = 0.82
    data["risk_level"] = "high"
    data["trigger_risk_alert_meeting"] = True
    return data


@pytest.fixture
def emily_packet_for_otto(emily_output_base):
    return transform_emily_to_bob(emily_output_base, "2026-04-01")


@pytest.fixture
def bob_dave_packet_for_otto(bob_output_base):
    return transform_bob_to_dave(bob_output_base, "2026-04-01")


@pytest.fixture
def execution_packet_for_otto(bob_output_base):
    return transform_bob_to_execution(bob_output_base, "2026-04-01")


# ---------------------------------------------------------------------------
# TestEmilyToBob
# ---------------------------------------------------------------------------

class TestEmilyToBob:
    """Unit tests for transform_emily_to_bob."""

    def test_basic_transform_success(self, emily_output_base):
        """테스트 1: 정상 EmilyOutput → EmilyToBobPacket 변환 성공."""
        result = transform_emily_to_bob(emily_output_base, "2026-04-01")
        assert isinstance(result, dict)
        assert result["source_agent"] == "Emily"
        assert result["target_agent"] == "Bob"
        assert result["date"] == "2026-04-01"

    def test_technical_fields_preserved(self, emily_output_base):
        """테스트 2: technical_direction, technical_confidence, reversal_risk 손실 없이 전달."""
        result = transform_emily_to_bob(emily_output_base, "2026-04-01")
        assert result["technical_direction"] == "up"
        assert result["technical_confidence"] == 0.8
        assert result["reversal_risk"] == 0.25

    def test_sector_preference_classification(self, emily_output_base):
        """테스트 3: sector_preference에서 score >= 0.6 → preferred, < 0.4 → avoid."""
        result = transform_emily_to_bob(emily_output_base, "2026-04-01")
        # tech(0.8), energy(0.65) → preferred
        assert "tech" in result["preferred_sectors"]
        assert "energy" in result["preferred_sectors"]
        # healthcare(0.5) → neither
        assert "healthcare" not in result["preferred_sectors"]
        assert "healthcare" not in result["avoid_sectors"]
        # utilities(0.3) → avoid
        assert "utilities" in result["avoid_sectors"]

    def test_event_risk_default_when_no_events(self, emily_output_no_events):
        """테스트 4: event_sensitivity_map 없으면 event_risk_level = 0.3."""
        result = transform_emily_to_bob(emily_output_no_events, "2026-04-01")
        assert result["event_risk_level"] == pytest.approx(0.3)

    def test_market_uncertainty_proportional_to_reasons(self, emily_output_base):
        """테스트 5: uncertainty_reasons 수에 따라 market_uncertainty 비례 증가."""
        # base: 2 reasons → 2 * 0.12 = 0.24
        result_base = transform_emily_to_bob(emily_output_base, "2026-04-01")
        assert result_base["market_uncertainty"] == pytest.approx(0.24)

        # 5 reasons → 5 * 0.12 = 0.60
        five_reasons = dict(emily_output_base)
        five_reasons["uncertainty_reasons"] = ["r1", "r2", "r3", "r4", "r5"]
        result_five = transform_emily_to_bob(five_reasons, "2026-04-01")
        assert result_five["market_uncertainty"] == pytest.approx(0.60)

        # 8 reasons → min(8*0.12, 0.9) = min(0.96, 0.9) = 0.9 (capped)
        eight_reasons = dict(emily_output_base)
        eight_reasons["uncertainty_reasons"] = ["r" + str(i) for i in range(8)]
        result_eight = transform_emily_to_bob(eight_reasons, "2026-04-01")
        assert result_eight["market_uncertainty"] == pytest.approx(0.9)

    def test_event_risk_average_from_map(self, emily_output_base):
        """event_sensitivity_map이 있으면 risk_level 평균으로 계산."""
        result = transform_emily_to_bob(emily_output_base, "2026-04-01")
        # (0.6 + 0.4) / 2 = 0.5
        assert result["event_risk_level"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TestBobToDave
# ---------------------------------------------------------------------------

class TestBobToDave:
    """Unit tests for transform_bob_to_dave."""

    def test_selected_for_review_strategy_extracted(self, bob_output_base):
        """테스트 6: selected_for_review 기준 전략 추출."""
        result = transform_bob_to_dave(bob_output_base, "2026-04-01")
        assert result["strategy_name"] == "momentum_tech"

    def test_failure_conditions_in_packet(self, bob_output_base):
        """테스트 7: failure_conditions이 packet에 포함됨."""
        result = transform_bob_to_dave(bob_output_base, "2026-04-01")
        assert "failure_conditions" in result
        assert len(result["failure_conditions"]) > 0
        assert "regime flips to risk_off" in result["failure_conditions"]

    def test_technical_alignment_in_packet(self, bob_output_base):
        """테스트 8: technical_alignment가 packet에 포함됨."""
        result = transform_bob_to_dave(bob_output_base, "2026-04-01")
        assert "technical_alignment" in result
        assert result["technical_alignment"] == pytest.approx(0.75)

    def test_fallback_to_highest_confidence_when_no_selection(self, bob_output_base):
        """selected_for_review 없으면 confidence 가장 높은 전략 선택."""
        data = dict(bob_output_base)
        data["selected_for_review"] = []
        result = transform_bob_to_dave(data, "2026-04-01")
        # momentum_tech의 confidence(0.78) > defensive_hedge(0.55)
        assert result["strategy_name"] == "momentum_tech"

    def test_strategy_confidence_in_packet(self, bob_output_base):
        """strategy_confidence가 올바르게 전달됨."""
        result = transform_bob_to_dave(bob_output_base, "2026-04-01")
        assert result["strategy_confidence"] == pytest.approx(0.78)


# ---------------------------------------------------------------------------
# TestBobToExecution
# ---------------------------------------------------------------------------

class TestBobToExecution:
    """Unit tests for transform_bob_to_execution."""

    def test_selected_strategy_name_in_packet(self, bob_output_base):
        """테스트 9: selected_strategy_name 포함 확인."""
        result = transform_bob_to_execution(bob_output_base, "2026-04-01")
        assert result["selected_strategy_name"] == "momentum_tech"

    def test_moderate_hedge_when_low_technical_alignment(self, bob_output_base):
        """테스트 10: technical_alignment < 0.4이면 hedge_preference = 'moderate'."""
        # defensive_hedge has technical_alignment=0.35 < 0.4
        data = dict(bob_output_base)
        data["selected_for_review"] = ["defensive_hedge"]
        result = transform_bob_to_execution(data, "2026-04-01")
        assert result["hedge_preference"] == "moderate"

    def test_high_sharpe_lowers_rebalance_urgency(self, bob_output_base):
        """테스트 11: sharpe 높으면 rebalance_urgency 낮아짐."""
        # Low sharpe version
        low_sharpe = dict(bob_output_base)
        low_sharpe["candidate_strategies"] = [
            dict(
                name="low_sharpe_strat",
                type="directional",
                logic_summary="low sharpe strategy",
                regime_fit=0.5,
                technical_alignment=0.6,
                sim_window={"train_start": "2024-01-01", "train_end": "2025-12-31"},
                sim_metrics={
                    "return": 0.05,
                    "sharpe": 0.5,
                    "sortino": 0.6,
                    "mdd": 0.2,
                    "turnover": 0.3,
                    "hit_rate": 0.45,
                },
                failure_conditions=["market crash"],
                optimization_suggestions=[],
                confidence=0.5,
            )
        ]
        low_sharpe["selected_for_review"] = ["low_sharpe_strat"]

        high_sharpe = dict(bob_output_base)
        high_sharpe["candidate_strategies"] = [
            dict(
                name="high_sharpe_strat",
                type="directional",
                logic_summary="high sharpe strategy",
                regime_fit=0.5,
                technical_alignment=0.6,
                sim_window={"train_start": "2024-01-01", "train_end": "2025-12-31"},
                sim_metrics={
                    "return": 0.25,
                    "sharpe": 2.5,
                    "sortino": 3.0,
                    "mdd": 0.08,
                    "turnover": 0.2,
                    "hit_rate": 0.65,
                },
                failure_conditions=["market crash"],
                optimization_suggestions=[],
                confidence=0.85,
            )
        ]
        high_sharpe["selected_for_review"] = ["high_sharpe_strat"]

        result_low = transform_bob_to_execution(low_sharpe, "2026-04-01")
        result_high = transform_bob_to_execution(high_sharpe, "2026-04-01")

        assert result_high["rebalance_urgency"] < result_low["rebalance_urgency"]

    def test_light_hedge_for_medium_technical_alignment(self, bob_output_base):
        """technical_alignment 0.4-0.6이면 hedge_preference = 'light'."""
        data = dict(bob_output_base)
        data["candidate_strategies"] = [
            dict(
                name="mid_align_strat",
                type="directional",
                logic_summary="mid alignment",
                regime_fit=0.6,
                technical_alignment=0.5,
                sim_window={"train_start": "2024-01-01", "train_end": "2025-12-31"},
                sim_metrics={
                    "return": 0.12,
                    "sharpe": 1.0,
                    "sortino": 1.2,
                    "mdd": 0.1,
                    "turnover": 0.2,
                    "hit_rate": 0.55,
                },
                failure_conditions=["regime shift"],
                optimization_suggestions=[],
                confidence=0.65,
            )
        ]
        data["selected_for_review"] = ["mid_align_strat"]
        result = transform_bob_to_execution(data, "2026-04-01")
        assert result["hedge_preference"] == "light"

    def test_none_hedge_for_high_technical_alignment(self, bob_output_base):
        """technical_alignment >= 0.6이면 hedge_preference = 'none'."""
        result = transform_bob_to_execution(bob_output_base, "2026-04-01")
        # momentum_tech has technical_alignment=0.75 >= 0.6
        assert result["hedge_preference"] == "none"


# ---------------------------------------------------------------------------
# TestAllToOtto
# ---------------------------------------------------------------------------

class TestAllToOtto:
    """Unit tests for transform_all_to_otto."""

    def test_otto_packet_creation_success(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_base,
        execution_packet_for_otto,
    ):
        """테스트 12: 4개 packet → OttoPolicyPacket 생성 성공."""
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_base,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
        )
        assert isinstance(result, dict)
        assert result["source_agent"] == "Aggregator"
        assert result["target_agent"] == "Otto"

    def test_no_raw_fields_in_otto_packet(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_base,
        execution_packet_for_otto,
    ):
        """테스트 13: raw_news, raw_ohlcv 필드가 Otto packet에 없음."""
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_base,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
        )
        assert "raw_news" not in result
        assert "raw_ohlcv" not in result
        assert "macro_state" not in result
        assert "bull_catalysts" not in result
        assert "bear_catalysts" not in result

    def test_agent_reliability_summary_included(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_base,
        execution_packet_for_otto,
    ):
        """테스트 14: agent_reliability_summary가 packet에 포함됨."""
        reliability = {"emily": 0.85, "bob": 0.72, "dave": 0.78}
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_base,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
            agent_reliability_summary=reliability,
        )
        assert result["agent_reliability_summary"] == reliability

    def test_dave_risk_score_and_trigger_alert_preserved(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_high_risk,
        execution_packet_for_otto,
    ):
        """테스트 15: dave.risk_score와 trigger_risk_alert가 올바르게 전달됨."""
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_high_risk,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
        )
        assert result["risk_score"] == pytest.approx(0.82)
        assert result["trigger_risk_alert"] is True

    def test_reversal_risk_from_emily_preserved(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_base,
        execution_packet_for_otto,
    ):
        """테스트 16: reversal_risk가 Otto packet에 포함됨 (Emily에서 전달)."""
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_base,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
        )
        assert "reversal_risk" in result
        assert result["reversal_risk"] == pytest.approx(0.25)

    def test_default_reliability_when_not_provided(
        self,
        emily_packet_for_otto,
        bob_dave_packet_for_otto,
        dave_output_base,
        execution_packet_for_otto,
    ):
        """agent_reliability_summary 미제공 시 default 값 사용."""
        result = transform_all_to_otto(
            emily_packet=emily_packet_for_otto,
            bob_dave_packet=bob_dave_packet_for_otto,
            dave_output=dave_output_base,
            execution_packet=execution_packet_for_otto,
            date="2026-04-01",
        )
        assert result["agent_reliability_summary"] == {"emily": 0.5, "bob": 0.5, "dave": 0.5}


# ---------------------------------------------------------------------------
# TestTransformValidationErrors
# ---------------------------------------------------------------------------

class TestTransformValidationErrors:
    """테스트 17: 잘못된 입력(빈 dict)에서 ValidationError/ValueError 발생."""

    def test_emily_to_bob_empty_input_raises(self):
        """빈 dict 입력 시 ValidationError 발생."""
        with pytest.raises((ValidationError, ValueError)):
            transform_emily_to_bob({}, "2026-04-01")

    def test_bob_to_dave_empty_input_raises(self):
        """빈 dict 입력 시 ValidationError 발생."""
        with pytest.raises((ValidationError, ValueError)):
            transform_bob_to_dave({}, "2026-04-01")

    def test_bob_to_execution_empty_input_raises(self):
        """빈 dict 입력 시 ValidationError 발생."""
        with pytest.raises((ValidationError, ValueError)):
            transform_bob_to_execution({}, "2026-04-01")

    def test_all_to_otto_empty_inputs_raises(self):
        """빈 dict 입력 시 ValidationError 발생."""
        with pytest.raises((ValidationError, ValueError)):
            transform_all_to_otto({}, {}, {}, {}, "2026-04-01")

    def test_bob_to_dave_no_candidates_raises(self):
        """candidate_strategies가 없으면 ValueError 발생."""
        with pytest.raises((ValidationError, ValueError)):
            transform_bob_to_dave(
                {
                    "agent": "Bob",
                    "date": "2026-04-01",
                    "candidate_strategies": [],
                    "selected_for_review": [],
                },
                "2026-04-01",
            )
