"""
tests.unit.test_schemas - Unit tests for all Pydantic schema definitions (v3.6).
"""

import pytest
from pydantic import ValidationError


# ─────────────────────────────────────────────
# 1. Import tests
# ─────────────────────────────────────────────

class TestImports:
    """1. 모든 schema import 성공 검증."""

    def test_import_base_schema(self):
        from schemas.base_schema import AgentBaseOutput, PacketBase, ControlSignal

    def test_import_emily_schema(self):
        from schemas.emily_schema import (
            MacroState, TechnicalSignalState, SectorScore,
            EmilyOutput, EmilyToBobPacket
        )

    def test_import_bob_schema(self):
        from schemas.bob_schema import (
            SimWindow, SimMetrics, CandidateStrategy,
            BobOutput, BobToDavePacket, BobToExecutionPacket
        )

    def test_import_dave_schema(self):
        from schemas.dave_schema import (
            RiskComponents, StressTest, RiskConstraints, DaveOutput
        )

    def test_import_otto_schema(self):
        from schemas.otto_schema import (
            AdaptiveWeights, Allocation, ExecutionPlan,
            OttoOutput, OttoPolicyPacket
        )

    def test_import_meeting_schema(self):
        from schemas.meeting_schema import (
            BullCase, BearCase, DebateResolution,
            ConflictItem, SignalConflictResolution,
            WeeklyMarketReport, WeeklyStrategySet
        )

    def test_import_audit_schema(self):
        from schemas.audit_schema import (
            NodeResult, PropagationAuditLog, CalibrationLog
        )


# ─────────────────────────────────────────────
# 2. Instantiation tests (valid values)
# ─────────────────────────────────────────────

class TestBaseSchema:
    """base_schema 인스턴스화 테스트."""

    def test_agent_base_output_valid(self):
        from schemas.base_schema import AgentBaseOutput
        obj = AgentBaseOutput(agent="TestAgent", date="2026-04-01")
        assert obj.agent == "TestAgent"
        assert obj.date == "2026-04-01"

    def test_packet_base_valid(self):
        from schemas.base_schema import PacketBase
        obj = PacketBase(source_agent="A", target_agent="B", date="2026-04-01")
        assert obj.source_agent == "A"

    def test_control_signal_valid(self):
        from schemas.base_schema import ControlSignal
        obj = ControlSignal(confidence=0.8, uncertainty=0.2)
        assert obj.confidence == 0.8
        assert obj.uncertainty == 0.2
        assert obj.needs_retry is False
        assert obj.retry_reason is None

    def test_control_signal_with_retry(self):
        from schemas.base_schema import ControlSignal
        obj = ControlSignal(
            confidence=0.3, uncertainty=0.7,
            needs_retry=True, retry_reason="low confidence"
        )
        assert obj.needs_retry is True
        assert obj.retry_reason == "low confidence"


class TestEmilySchema:
    """emily_schema 인스턴스화 테스트."""

    def _make_emily_output(self):
        from schemas.emily_schema import (
            MacroState, TechnicalSignalState, SectorScore, EmilyOutput
        )
        return EmilyOutput(
            agent="Emily",
            date="2026-04-01",
            market_regime="risk_on",
            regime_confidence=0.75,
            macro_state=MacroState(
                rates=0.2, inflation=-0.3, growth=0.5,
                liquidity=0.1, risk_sentiment=0.4
            ),
            technical_signal_state=TechnicalSignalState(
                trend_direction="up",
                continuation_strength=0.7,
                reversal_risk=0.2,
                technical_confidence=0.8
            ),
            sector_preference=[SectorScore(sector="tech", score=0.9)],
            bull_catalysts=["Fed pivot", "strong earnings"],
            bear_catalysts=["recession risk"],
            event_sensitivity_map=[{"event": "FOMC", "sensitivity": 0.8}],
            technical_conflict_flags=[],
            risk_flags=["geopolitical tension"],
            uncertainty_reasons=["mixed signals"],
            recommended_market_bias="selective_long"
        )

    def test_emily_output_valid(self):
        obj = self._make_emily_output()
        assert obj.agent == "Emily"
        assert obj.market_regime == "risk_on"

    def test_macro_state_valid(self):
        from schemas.emily_schema import MacroState
        obj = MacroState(rates=0.0, inflation=0.0, growth=0.0, liquidity=0.0, risk_sentiment=0.0)
        assert obj.rates == 0.0

    def test_macro_state_boundary(self):
        from schemas.emily_schema import MacroState
        obj = MacroState(rates=-1.0, inflation=1.0, growth=-1.0, liquidity=1.0, risk_sentiment=0.0)
        assert obj.rates == -1.0
        assert obj.inflation == 1.0

    def test_technical_signal_state_valid(self):
        from schemas.emily_schema import TechnicalSignalState
        obj = TechnicalSignalState(
            trend_direction="down",
            continuation_strength=0.5,
            reversal_risk=0.3,
            technical_confidence=0.6
        )
        assert obj.trend_direction == "down"

    def test_emily_to_bob_packet_valid(self):
        from schemas.emily_schema import EmilyToBobPacket
        obj = EmilyToBobPacket(
            date="2026-04-01",
            regime="mixed",
            regime_confidence=0.6,
            preferred_sectors=["energy", "healthcare"],
            avoid_sectors=["real_estate"],
            market_bias="neutral",
            event_risk_level=0.4,
            market_uncertainty=0.5,
            technical_direction="mixed",
            technical_confidence=0.55,
            reversal_risk=0.3
        )
        assert obj.source_agent == "Emily"
        assert obj.target_agent == "Bob"


class TestBobSchema:
    """bob_schema 인스턴스화 테스트."""

    def _make_candidate_strategy(self):
        from schemas.bob_schema import CandidateStrategy, SimWindow, SimMetrics
        return CandidateStrategy(
            name="momentum_v1",
            type="momentum",
            logic_summary="Follow trend with momentum factor",
            regime_fit=0.8,
            technical_alignment=0.75,
            sim_window=SimWindow(train_start="2023-01-01", train_end="2025-12-31"),
            sim_metrics=SimMetrics(**{"return": 0.12, "sharpe": 1.5, "sortino": 2.0, "mdd": 0.15, "turnover": 0.3, "hit_rate": 0.55}),
            failure_conditions=["regime flip", "liquidity crunch"],
            optimization_suggestions=["reduce turnover"],
            confidence=0.7
        )

    def test_sim_metrics_valid(self):
        from schemas.bob_schema import SimMetrics
        obj = SimMetrics(**{"return": 0.1, "sharpe": 1.2, "sortino": 1.8, "mdd": 0.1, "turnover": 0.2, "hit_rate": 0.6})
        assert obj.return_ == 0.1
        assert obj.sharpe == 1.2

    def test_sim_metrics_alias(self):
        from schemas.bob_schema import SimMetrics
        # populate_by_name=True 이므로 return_ 필드명으로도 접근 가능
        obj = SimMetrics(**{"return": 0.15, "sharpe": 1.0, "sortino": 1.5, "mdd": 0.08, "turnover": 0.25, "hit_rate": 0.58})
        assert obj.return_ == 0.15

    def test_candidate_strategy_valid(self):
        obj = self._make_candidate_strategy()
        assert obj.name == "momentum_v1"
        assert obj.type == "momentum"

    def test_bob_output_valid(self):
        from schemas.bob_schema import BobOutput
        strategy = self._make_candidate_strategy()
        obj = BobOutput(
            agent="Bob",
            date="2026-04-01",
            candidate_strategies=[strategy],
            selected_for_review=["momentum_v1"]
        )
        assert obj.agent == "Bob"
        assert len(obj.candidate_strategies) == 1

    def test_bob_to_dave_packet_valid(self):
        from schemas.bob_schema import BobToDavePacket
        obj = BobToDavePacket(
            date="2026-04-01",
            strategy_name="momentum_v1",
            expected_turnover=0.3,
            sector_bias=["tech", "healthcare"],
            expected_vol_profile=0.15,
            failure_conditions=["regime flip"],
            strategy_confidence=0.7,
            technical_alignment=0.75
        )
        assert obj.source_agent == "Bob"
        assert obj.target_agent == "Dave"

    def test_bob_to_execution_packet_valid(self):
        from schemas.bob_schema import BobToExecutionPacket
        obj = BobToExecutionPacket(
            date="2026-04-01",
            selected_strategy_name="momentum_v1",
            target_posture="long_biased",
            rebalance_urgency=0.6,
            expected_turnover=0.3,
            hedge_preference="light",
            execution_constraints_hint=["no illiquid names"]
        )
        assert obj.source_agent == "Bob"
        assert obj.target_agent == "Execution"


class TestDaveSchema:
    """dave_schema 인스턴스화 테스트."""

    def _make_dave_output(self):
        from schemas.dave_schema import (
            DaveOutput, RiskComponents, StressTest, RiskConstraints
        )
        return DaveOutput(
            agent="Dave",
            date="2026-04-01",
            risk_score=0.6,
            risk_components=RiskComponents(
                beta=1.1, illiquidity=0.2, sector_concentration=0.3, volatility=0.18
            ),
            signal_conflict_risk=0.25,
            stress_test=StressTest(severity_score=0.5, worst_case_drawdown=0.2),
            risk_level="medium",
            recommended_controls=["reduce sector concentration"],
            risk_constraints=RiskConstraints(
                max_single_sector_weight=0.3,
                max_beta=1.5,
                max_gross_exposure=1.0
            ),
            trigger_risk_alert_meeting=False
        )

    def test_dave_output_valid(self):
        obj = self._make_dave_output()
        assert obj.agent == "Dave"
        assert obj.risk_score == 0.6

    def test_risk_components_valid(self):
        from schemas.dave_schema import RiskComponents
        obj = RiskComponents(beta=0.9, illiquidity=0.1, sector_concentration=0.25, volatility=0.15)
        assert obj.beta == 0.9

    def test_stress_test_valid(self):
        from schemas.dave_schema import StressTest
        obj = StressTest(severity_score=0.8, worst_case_drawdown=0.35)
        assert obj.severity_score == 0.8

    def test_risk_constraints_valid(self):
        from schemas.dave_schema import RiskConstraints
        obj = RiskConstraints(max_single_sector_weight=0.25, max_beta=1.2, max_gross_exposure=0.9)
        assert obj.max_single_sector_weight == 0.25

    def test_trigger_risk_alert_high_risk(self):
        from schemas.dave_schema import (
            DaveOutput, RiskComponents, StressTest, RiskConstraints
        )
        # risk_score > 0.75 → trigger_risk_alert_meeting=True
        obj = DaveOutput(
            agent="Dave",
            date="2026-04-01",
            risk_score=0.8,
            risk_components=RiskComponents(beta=1.5, illiquidity=0.4, sector_concentration=0.5, volatility=0.3),
            stress_test=StressTest(severity_score=0.9, worst_case_drawdown=0.4),
            risk_level="critical",
            recommended_controls=["halt trading"],
            risk_constraints=RiskConstraints(max_single_sector_weight=0.2, max_beta=1.0, max_gross_exposure=0.8),
            trigger_risk_alert_meeting=True
        )
        assert obj.trigger_risk_alert_meeting is True


class TestOttoSchema:
    """otto_schema 인스턴스화 테스트."""

    def _make_otto_output(self):
        from schemas.otto_schema import (
            OttoOutput, AdaptiveWeights, Allocation, ExecutionPlan
        )
        return OttoOutput(
            agent="Otto",
            date="2026-04-01",
            candidate_policies=["policy_A", "policy_B"],
            adaptive_weights=AdaptiveWeights(w_sim=0.6, w_real=0.4, lookback_steps=10),
            selected_policy="policy_A",
            allocation=Allocation(equities=0.6, hedge=0.2, cash=0.2),
            execution_plan=ExecutionPlan(
                entry_style="staggered",
                rebalance_frequency="weekly",
                stop_loss=0.08
            ),
            policy_reasoning_summary=["regime is risk_on", "strategy confidence high"],
            approval_status="approved"
        )

    def test_otto_output_valid(self):
        obj = self._make_otto_output()
        assert obj.agent == "Otto"
        assert obj.approval_status == "approved"

    def test_adaptive_weights_valid(self):
        from schemas.otto_schema import AdaptiveWeights
        obj = AdaptiveWeights(w_sim=0.5, w_real=0.5, lookback_steps=5)
        assert obj.lookback_steps == 5

    def test_allocation_valid(self):
        from schemas.otto_schema import Allocation
        obj = Allocation(equities=0.7, hedge=0.1, cash=0.2)
        assert obj.equities == 0.7

    def test_execution_plan_valid(self):
        from schemas.otto_schema import ExecutionPlan
        obj = ExecutionPlan(entry_style="immediate", rebalance_frequency="daily", stop_loss=0.05)
        assert obj.entry_style == "immediate"

    def test_otto_policy_packet_valid(self):
        from schemas.otto_schema import OttoPolicyPacket
        obj = OttoPolicyPacket(
            date="2026-04-01",
            market_regime="risk_on",
            regime_confidence=0.75,
            market_bias="selective_long",
            technical_confidence=0.8,
            reversal_risk=0.2,
            market_uncertainty=0.3,
            selected_strategy_name="momentum_v1",
            strategy_confidence=0.7,
            technical_alignment=0.75,
            failure_conditions=["regime flip"],
            risk_score=0.4,
            risk_level="low",
            risk_constraints={"max_beta": 1.5, "max_gross_exposure": 1.0},
            trigger_risk_alert=False,
            rebalance_urgency=0.5,
            execution_constraints_hint=["avoid illiquid"],
            agent_reliability_summary={"emily": 0.8, "bob": 0.7, "dave": 0.75},
            recent_reward_summary=None
        )
        assert obj.source_agent == "Aggregator"
        assert obj.target_agent == "Otto"

    def test_otto_no_raw_data_fields(self):
        """Otto schema에 raw_news, raw_ohlcv 등 raw data 필드가 없어야 함."""
        from schemas.otto_schema import OttoOutput, OttoPolicyPacket
        otto_fields = set(OttoOutput.model_fields.keys())
        packet_fields = set(OttoPolicyPacket.model_fields.keys())
        forbidden = {"raw_news", "raw_ohlcv", "raw_data", "ohlcv", "news_data", "price_data"}
        assert otto_fields.isdisjoint(forbidden), f"OttoOutput has forbidden raw fields: {otto_fields & forbidden}"
        assert packet_fields.isdisjoint(forbidden), f"OttoPolicyPacket has forbidden raw fields: {packet_fields & forbidden}"


class TestMeetingSchema:
    """meeting_schema 인스턴스화 테스트."""

    def test_bull_case_valid(self):
        from schemas.meeting_schema import BullCase
        obj = BullCase(
            growth_path="earnings acceleration",
            upside_catalysts=["rate cuts", "AI boom"],
            sustainability="6-12 months"
        )
        assert obj.growth_path == "earnings acceleration"

    def test_bear_case_valid(self):
        from schemas.meeting_schema import BearCase
        obj = BearCase(
            downside_risks=["recession", "credit crunch"],
            fragility="high leverage",
            reversal_triggers=["hawkish Fed", "earnings miss"]
        )
        assert len(obj.downside_risks) == 2

    def test_debate_resolution_valid(self):
        from schemas.meeting_schema import DebateResolution, BullCase, BearCase
        obj = DebateResolution(
            bull_case=BullCase(growth_path="steady", upside_catalysts=["pivot"], sustainability="3-6m"),
            bear_case=BearCase(downside_risks=["inflation"], fragility="high", reversal_triggers=["hawkish"]),
            moderator_summary="Balanced outlook with cautious optimism",
            unresolved_issues=["inflation trajectory"],
            regime_confidence_adjustment=0.05
        )
        assert obj.regime_confidence_adjustment == 0.05

    def test_conflict_item_valid(self):
        from schemas.meeting_schema import ConflictItem
        obj = ConflictItem(
            signal_a="macro_bearish",
            signal_b="technical_bullish",
            conflict_type="direction_conflict",
            resolution="technical_overridden_by_macro"
        )
        assert obj.conflict_type == "direction_conflict"

    def test_signal_conflict_resolution_valid(self):
        from schemas.meeting_schema import SignalConflictResolution, ConflictItem
        obj = SignalConflictResolution(
            conflict_matrix=[
                ConflictItem(
                    signal_a="trend_up",
                    signal_b="macro_down",
                    conflict_type="direction_conflict",
                    resolution="macro_takes_priority"
                )
            ]
        )
        assert len(obj.conflict_matrix) == 1

    def test_weekly_market_report_valid(self):
        from schemas.meeting_schema import (
            WeeklyMarketReport, DebateResolution, BullCase, BearCase,
            SignalConflictResolution, ConflictItem
        )
        obj = WeeklyMarketReport(
            date="2026-04-01",
            market_regime="risk_on",
            regime_confidence=0.7,
            preferred_sectors=["tech", "healthcare"],
            avoid_sectors=["real_estate"],
            unresolved_risks=["geopolitical"],
            debate_resolution=DebateResolution(
                bull_case=BullCase(growth_path="steady", upside_catalysts=["AI"], sustainability="long"),
                bear_case=BearCase(downside_risks=["recession"], fragility="medium", reversal_triggers=["rate hike"]),
                moderator_summary="Cautiously optimistic",
                unresolved_issues=[],
                regime_confidence_adjustment=0.1
            ),
            signal_conflict_resolution=SignalConflictResolution(
                conflict_matrix=[
                    ConflictItem(signal_a="a", signal_b="b", conflict_type="regime_mismatch", resolution="a wins")
                ]
            ),
            technical_summary_packet={"trend_direction": "up", "reversal_risk": 0.2}
        )
        assert obj.market_regime == "risk_on"

    def test_weekly_strategy_set_valid(self):
        from schemas.meeting_schema import WeeklyStrategySet
        obj = WeeklyStrategySet(
            date="2026-04-01",
            candidate_strategies=["strat_A", "strat_B"],
            selected_strategies=["strat_A"],
            rejection_reasons={"strat_B": "low regime fit"},
            optimization_notes=["reduce turnover"],
            execution_feasibility_hints=["avoid illiquid"],
            technical_alignment_summary="strong uptrend alignment"
        )
        assert "strat_A" in obj.selected_strategies


class TestAuditSchema:
    """audit_schema 인스턴스화 테스트."""

    def test_node_result_valid(self):
        from schemas.audit_schema import NodeResult
        obj = NodeResult(next="risk_check", confidence=0.9)
        assert obj.next == "risk_check"
        assert obj.retry is False

    def test_node_result_with_retry(self):
        from schemas.audit_schema import NodeResult
        obj = NodeResult(next="emily_rerun", retry=True, retry_reason="low confidence", confidence=0.4)
        assert obj.retry is True

    def test_propagation_audit_log_valid(self):
        from schemas.audit_schema import PropagationAuditLog
        obj = PropagationAuditLog(
            date="2026-04-01",
            source_agent="Emily",
            target_agent="Bob",
            adopted_keyword_rate=0.8,
            dropped_critical_signal_rate=0.1,
            has_contradiction=False,
            semantic_similarity_score=0.75,
            technical_signal_adoption_rate=0.85
        )
        assert obj.adopted_keyword_rate == 0.8

    def test_calibration_log_valid(self):
        from schemas.audit_schema import CalibrationLog
        obj = CalibrationLog(
            date="2026-04-01",
            agent="Emily",
            field_name="regime_confidence",
            raw_value=0.95,
            calibrated_value=0.85,
            method="shrinkage",
            was_shrunk=True
        )
        assert obj.method == "shrinkage"
        assert obj.was_shrunk is True


# ─────────────────────────────────────────────
# 3. Validation error tests
# ─────────────────────────────────────────────

class TestValidationErrors:
    """3 & 4. 필수 필드 누락 및 범위 벗어난 값 ValidationError 테스트."""

    def test_control_signal_missing_required(self):
        from schemas.base_schema import ControlSignal
        with pytest.raises(ValidationError):
            ControlSignal(confidence=0.5)  # uncertainty 누락

    def test_control_signal_confidence_out_of_range(self):
        from schemas.base_schema import ControlSignal
        with pytest.raises(ValidationError):
            ControlSignal(confidence=1.5, uncertainty=0.2)

    def test_control_signal_uncertainty_out_of_range(self):
        from schemas.base_schema import ControlSignal
        with pytest.raises(ValidationError):
            ControlSignal(confidence=0.5, uncertainty=-0.1)

    def test_macro_state_out_of_range(self):
        from schemas.emily_schema import MacroState
        with pytest.raises(ValidationError):
            MacroState(rates=1.5, inflation=0.0, growth=0.0, liquidity=0.0, risk_sentiment=0.0)

    def test_technical_signal_state_invalid_direction(self):
        from schemas.emily_schema import TechnicalSignalState
        with pytest.raises(ValidationError):
            TechnicalSignalState(
                trend_direction="sideways",  # invalid
                continuation_strength=0.5,
                reversal_risk=0.3,
                technical_confidence=0.6
            )

    def test_emily_output_missing_required(self):
        from schemas.emily_schema import EmilyOutput
        with pytest.raises(ValidationError):
            EmilyOutput(agent="Emily", date="2026-04-01")  # 많은 필수 필드 누락

    def test_regime_confidence_out_of_range(self):
        from schemas.emily_schema import EmilyToBobPacket
        with pytest.raises(ValidationError):
            EmilyToBobPacket(
                date="2026-04-01",
                regime="risk_on",
                regime_confidence=1.5,  # 범위 초과
                preferred_sectors=[],
                avoid_sectors=[],
                market_bias="neutral",
                event_risk_level=0.5,
                market_uncertainty=0.5,
                technical_direction="up",
                technical_confidence=0.7,
                reversal_risk=0.3
            )

    def test_sim_metrics_hit_rate_out_of_range(self):
        from schemas.bob_schema import SimMetrics
        with pytest.raises(ValidationError):
            SimMetrics(**{"return": 0.1, "sharpe": 1.2, "sortino": 1.8, "mdd": 0.1, "turnover": 0.2, "hit_rate": 1.5})

    def test_sim_metrics_mdd_negative(self):
        from schemas.bob_schema import SimMetrics
        with pytest.raises(ValidationError):
            SimMetrics(**{"return": 0.1, "sharpe": 1.2, "sortino": 1.8, "mdd": -0.1, "turnover": 0.2, "hit_rate": 0.5})

    def test_risk_score_out_of_range(self):
        from schemas.dave_schema import DaveOutput, RiskComponents, StressTest, RiskConstraints
        with pytest.raises(ValidationError):
            DaveOutput(
                agent="Dave",
                date="2026-04-01",
                risk_score=1.5,  # 범위 초과
                risk_components=RiskComponents(beta=1.0, illiquidity=0.2, sector_concentration=0.3, volatility=0.15),
                stress_test=StressTest(severity_score=0.5, worst_case_drawdown=0.2),
                risk_level="medium",
                recommended_controls=[],
                risk_constraints=RiskConstraints(max_single_sector_weight=0.3, max_beta=1.5, max_gross_exposure=1.0),
                trigger_risk_alert_meeting=False
            )

    def test_otto_output_missing_required(self):
        from schemas.otto_schema import OttoOutput
        with pytest.raises(ValidationError):
            OttoOutput(agent="Otto", date="2026-04-01")  # 많은 필수 필드 누락

    def test_node_result_confidence_out_of_range(self):
        from schemas.audit_schema import NodeResult
        with pytest.raises(ValidationError):
            NodeResult(next="some_node", confidence=1.5)

    def test_propagation_audit_log_rate_out_of_range(self):
        from schemas.audit_schema import PropagationAuditLog
        with pytest.raises(ValidationError):
            PropagationAuditLog(
                date="2026-04-01",
                source_agent="Emily",
                target_agent="Bob",
                adopted_keyword_rate=1.5,  # 범위 초과
                dropped_critical_signal_rate=0.1,
                has_contradiction=False,
                semantic_similarity_score=0.75,
                technical_signal_adoption_rate=0.85
            )

    def test_calibration_log_invalid_method(self):
        from schemas.audit_schema import CalibrationLog
        with pytest.raises(ValidationError):
            CalibrationLog(
                date="2026-04-01",
                agent="Emily",
                field_name="confidence",
                raw_value=0.9,
                calibrated_value=0.8,
                method="unknown_method"  # invalid literal
            )

    def test_debate_resolution_adjustment_out_of_range(self):
        from schemas.meeting_schema import DebateResolution, BullCase, BearCase
        with pytest.raises(ValidationError):
            DebateResolution(
                bull_case=BullCase(growth_path="up", upside_catalysts=[], sustainability="long"),
                bear_case=BearCase(downside_risks=[], fragility="low", reversal_triggers=[]),
                moderator_summary="summary",
                unresolved_issues=[],
                regime_confidence_adjustment=0.9  # 범위 초과 (max 0.5)
            )


# ─────────────────────────────────────────────
# 5. Otto raw data field absence test
# ─────────────────────────────────────────────

class TestOttoNoRawData:
    """5. Otto schema에 raw data 필드 없음 확인."""

    def test_otto_output_no_raw_fields(self):
        from schemas.otto_schema import OttoOutput
        fields = set(OttoOutput.model_fields.keys())
        forbidden = {"raw_news", "raw_ohlcv", "raw_data", "ohlcv", "news_data", "price_data", "market_data"}
        assert fields.isdisjoint(forbidden), f"OttoOutput contains forbidden fields: {fields & forbidden}"

    def test_otto_policy_packet_no_raw_fields(self):
        from schemas.otto_schema import OttoPolicyPacket
        fields = set(OttoPolicyPacket.model_fields.keys())
        forbidden = {"raw_news", "raw_ohlcv", "raw_data", "ohlcv", "news_data", "price_data", "market_data"}
        assert fields.isdisjoint(forbidden), f"OttoPolicyPacket contains forbidden fields: {fields & forbidden}"


# ─────────────────────────────────────────────
# 6. TechnicalSignalState is independent field in EmilyOutput
# ─────────────────────────────────────────────

class TestTechnicalSignalStateIndependence:
    """6. TechnicalSignalState가 EmilyOutput의 독립 필드임 확인."""

    def test_technical_signal_state_is_top_level_field(self):
        from schemas.emily_schema import EmilyOutput, TechnicalSignalState
        # technical_signal_state는 EmilyOutput의 직접 필드여야 함 (macro_state 안에 묻히면 안 됨)
        assert "technical_signal_state" in EmilyOutput.model_fields

    def test_macro_state_does_not_contain_technical_signal(self):
        from schemas.emily_schema import MacroState
        # MacroState 안에 technical_signal_state가 없어야 함
        assert "technical_signal_state" not in MacroState.model_fields
        assert "trend_direction" not in MacroState.model_fields
        assert "technical_confidence" not in MacroState.model_fields

    def test_technical_signal_state_type(self):
        from schemas.emily_schema import EmilyOutput, TechnicalSignalState
        field_info = EmilyOutput.model_fields["technical_signal_state"]
        # 필드 타입이 TechnicalSignalState인지 확인
        assert field_info.annotation is TechnicalSignalState

    def test_emily_output_has_both_macro_and_technical(self):
        """EmilyOutput이 macro_state와 technical_signal_state를 모두 독립적으로 가짐."""
        from schemas.emily_schema import EmilyOutput
        fields = set(EmilyOutput.model_fields.keys())
        assert "macro_state" in fields
        assert "technical_signal_state" in fields
