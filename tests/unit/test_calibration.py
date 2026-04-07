"""
tests.unit.test_calibration - Unit tests for Phase 7: Calibration Layer + Propagation Audit.
"""

import pytest
from calibration.calibrator import AgentCalibrator
from audit.propagation_audit import audit_emily_to_bob, audit_bob_to_dave, audit_to_otto
from schemas.audit_schema import CalibrationLog, PropagationAuditLog


# ---------------------------------------------------------------------------
# Calibrator Tests
# ---------------------------------------------------------------------------

class TestCalibratorRollingStd:
    """rolling_std method 관련 테스트."""

    def test_rolling_std_no_history_returns_raw_value(self):
        """history 없을 때 rolling_std → raw_value 그대로 반환 (no-op)."""
        cal = AgentCalibrator(agent_name="Emily")
        val, log = cal.calibrate("score", 0.7, "2026-04-01", method="rolling_std")
        assert val == pytest.approx(0.7)

    def test_rolling_std_two_history_returns_raw_value(self):
        """history 2개일 때도 변환 없음 (최소 3개 필요)."""
        cal = AgentCalibrator(agent_name="Emily")
        cal.calibrate("score", 0.5, "2026-04-01", method="rolling_std")
        cal.calibrate("score", 0.6, "2026-04-01", method="rolling_std")
        # 3번째 호출 시 history는 아직 2개 (이전 2개만 존재)
        val, log = cal.calibrate("score", 0.7, "2026-04-01", method="rolling_std")
        # history가 2개이므로 no-op → raw_value 반환
        assert val == pytest.approx(0.7)

    def test_rolling_std_sigmoid_range_when_history_enough(self):
        """history 3개 이상이면 sigmoid 변환 후 [0,1] 범위 내에 있어야 함."""
        cal = AgentCalibrator(agent_name="Emily")
        # history를 3개 먼저 쌓기
        for v in [0.4, 0.5, 0.6]:
            cal.calibrate("score", v, "2026-04-01", method="rolling_std")
        # 4번째 호출: history 3개 → sigmoid 변환 적용
        val, log = cal.calibrate("score", 0.8, "2026-04-01", method="rolling_std")
        assert 0.0 <= val <= 1.0
        # sigmoid(z-score) 이므로 raw_value와 다른 값이어야 함
        assert val != pytest.approx(0.8)

    def test_rolling_std_result_in_01_range(self):
        """rolling_std 변환 결과는 항상 [0, 1] 범위."""
        cal = AgentCalibrator(agent_name="Emily")
        values = [0.1, 0.2, 0.3, 0.9, 0.95, 1.0, 0.0]
        for v in values:
            val, log = cal.calibrate("score", v, "2026-04-01", method="rolling_std")
            assert 0.0 <= val <= 1.0, f"Value {val} out of [0,1] for input {v}"


class TestCalibratorShrinkage:
    """shrinkage method 관련 테스트."""

    def test_shrinkage_confidence_zero_pulls_to_neutral(self):
        """confidence=0.0이면 shrinkage_factor 최대 → neutral(0.5)에 가까워짐."""
        cal = AgentCalibrator(agent_name="Emily", shrinkage_factor=0.3, neutral_value=0.5)
        val, log = cal.calibrate("score", 1.0, "2026-04-01", confidence=0.0, method="shrinkage")
        # shrink = 0.3 * (1 - 0.0) = 0.3
        # calibrated = 1.0 * 0.7 + 0.5 * 0.3 = 0.7 + 0.15 = 0.85
        expected = 1.0 * (1.0 - 0.3) + 0.5 * 0.3
        assert val == pytest.approx(expected, abs=1e-6)
        # neutral(0.5)보다 원래 값(1.0)에 더 가깝지만, 확실히 이동했음
        assert val < 1.0
        assert log.was_shrunk is True

    def test_shrinkage_confidence_zero_extreme_value(self):
        """confidence=0.0, raw=0.0일 때 neutral 방향으로 이동."""
        cal = AgentCalibrator(agent_name="Emily", shrinkage_factor=0.3, neutral_value=0.5)
        val, log = cal.calibrate("score", 0.0, "2026-04-01", confidence=0.0, method="shrinkage")
        # shrink = 0.3, calibrated = 0.0 * 0.7 + 0.5 * 0.3 = 0.15
        assert val == pytest.approx(0.15, abs=1e-6)
        assert val > 0.0  # neutral 방향으로 이동

    def test_shrinkage_confidence_one_no_shrinkage(self):
        """confidence=1.0이면 shrinkage 없음 → raw_value 그대로."""
        cal = AgentCalibrator(agent_name="Emily", shrinkage_factor=0.3)
        val, log = cal.calibrate("score", 0.8, "2026-04-01", confidence=1.0, method="shrinkage")
        assert val == pytest.approx(0.8)
        assert log.was_shrunk is False

    def test_shrinkage_was_shrunk_flag(self):
        """was_shrunk 플래그가 올바르게 설정됨."""
        cal = AgentCalibrator(agent_name="Emily", shrinkage_factor=0.3)
        _, log_no_shrink = cal.calibrate("s", 0.5, "2026-04-01", confidence=1.0, method="shrinkage")
        _, log_shrunk = cal.calibrate("s", 0.5, "2026-04-01", confidence=0.0, method="shrinkage")
        assert log_no_shrink.was_shrunk is False
        assert log_shrunk.was_shrunk is True


class TestCalibratorClipping:
    """clipping method 관련 테스트."""

    def test_clipping_above_max(self):
        """1.5 → 1.0으로 clip됨, was_clipped=True."""
        cal = AgentCalibrator(agent_name="Emily", clip_range=(0.0, 1.0))
        val, log = cal.calibrate("score", 1.5, "2026-04-01", method="clipping")
        assert val == pytest.approx(1.0)
        assert log.was_clipped is True

    def test_clipping_below_min(self):
        """-0.5 → 0.0으로 clip됨."""
        cal = AgentCalibrator(agent_name="Emily", clip_range=(0.0, 1.0))
        val, log = cal.calibrate("score", -0.5, "2026-04-01", method="clipping")
        assert val == pytest.approx(0.0)
        assert log.was_clipped is True

    def test_clipping_within_range_not_clipped(self):
        """범위 내 값은 그대로, was_clipped=False."""
        cal = AgentCalibrator(agent_name="Emily", clip_range=(0.0, 1.0))
        val, log = cal.calibrate("score", 0.7, "2026-04-01", method="clipping")
        assert val == pytest.approx(0.7)
        assert log.was_clipped is False

    def test_clipping_boundary_values(self):
        """경계값 0.0, 1.0은 clip되지 않음."""
        cal = AgentCalibrator(agent_name="Emily", clip_range=(0.0, 1.0))
        val0, log0 = cal.calibrate("score", 0.0, "2026-04-01", method="clipping")
        val1, log1 = cal.calibrate("score", 1.0, "2026-04-01", method="clipping")
        assert val0 == pytest.approx(0.0)
        assert val1 == pytest.approx(1.0)
        assert log0.was_clipped is False
        assert log1.was_clipped is False


class TestCalibrationLog:
    """CalibrationLog 반환 확인."""

    def test_calibration_log_all_fields(self):
        """CalibrationLog 반환 시 모든 필드 포함 확인."""
        cal = AgentCalibrator(agent_name="TestAgent")
        val, log = cal.calibrate("my_score", 0.75, "2026-04-01", confidence=0.8, method="clipping")
        assert isinstance(log, CalibrationLog)
        assert log.date == "2026-04-01"
        assert log.agent == "TestAgent"
        assert log.field_name == "my_score"
        assert log.raw_value == pytest.approx(0.75)
        assert log.calibrated_value == pytest.approx(val)
        assert log.method == "clipping"
        assert isinstance(log.was_clipped, bool)
        assert isinstance(log.was_shrunk, bool)

    def test_calibration_log_method_field_matches(self):
        """log.method 필드가 호출 시 지정한 method와 일치."""
        cal = AgentCalibrator(agent_name="Bob")
        for method in ("rolling_std", "shrinkage", "clipping", "sector_relative"):
            _, log = cal.calibrate("f", 0.5, "2026-04-01", method=method)
            assert log.method == method


class TestCalibratePacket:
    """calibrate_packet method 테스트."""

    def test_calibrate_packet_multiple_fields(self):
        """여러 score 필드를 한 번에 calibration."""
        cal = AgentCalibrator(agent_name="Emily", clip_range=(0.0, 1.0))
        packet = {"score_a": 1.5, "score_b": -0.2, "label": "test"}
        result, logs = cal.calibrate_packet(
            packet, "2026-04-01",
            score_fields=["score_a", "score_b"],
            method="clipping",
        )
        assert result["score_a"] == pytest.approx(1.0)
        assert result["score_b"] == pytest.approx(0.0)
        assert result["label"] == "test"  # 비 score 필드 유지
        assert len(logs) == 2
        assert all(isinstance(l, CalibrationLog) for l in logs)

    def test_calibrate_packet_empty_score_fields(self):
        """비어있는 score_fields → 변환 없음."""
        cal = AgentCalibrator(agent_name="Emily")
        packet = {"score_a": 0.8, "score_b": 0.3}
        result, logs = cal.calibrate_packet(
            packet, "2026-04-01",
            score_fields=[],
            method="clipping",
        )
        assert result["score_a"] == pytest.approx(0.8)
        assert result["score_b"] == pytest.approx(0.3)
        assert logs == []

    def test_calibrate_packet_missing_field_ignored(self):
        """packet에 없는 score_fields 항목은 무시됨."""
        cal = AgentCalibrator(agent_name="Emily")
        packet = {"score_a": 0.5}
        result, logs = cal.calibrate_packet(
            packet, "2026-04-01",
            score_fields=["score_a", "nonexistent_field"],
            method="clipping",
        )
        assert "nonexistent_field" not in result
        assert len(logs) == 1

    def test_calibrate_packet_returns_new_dict(self):
        """calibrate_packet은 원본 packet을 수정하지 않고 새 dict 반환."""
        cal = AgentCalibrator(agent_name="Emily")
        original = {"score": 1.5}
        result, _ = cal.calibrate_packet(original, "2026-04-01", ["score"], method="clipping")
        assert original["score"] == pytest.approx(1.5)  # 원본 불변
        assert result["score"] == pytest.approx(1.0)


class TestHistoryAccumulation:
    """history 누적 및 reset 테스트."""

    def test_history_accumulates_across_calls(self):
        """같은 field에 여러 번 calibrate 호출 시 history 쌓임."""
        cal = AgentCalibrator(agent_name="Emily", rolling_window=20)
        for i in range(5):
            cal.calibrate("score", float(i) * 0.1, "2026-04-01", method="rolling_std")
        # history가 쌓였으므로 5개의 값이 있어야 함
        assert len(cal._history["score"]) == 5

    def test_history_respects_rolling_window(self):
        """rolling_window 초과 시 오래된 값이 제거됨."""
        cal = AgentCalibrator(agent_name="Emily", rolling_window=5)
        for i in range(10):
            cal.calibrate("score", float(i) * 0.1, "2026-04-01", method="rolling_std")
        assert len(cal._history["score"]) == 5

    def test_reset_history_specific_field(self):
        """특정 field history 초기화."""
        cal = AgentCalibrator(agent_name="Emily")
        cal.calibrate("score_a", 0.5, "2026-04-01", method="clipping")
        cal.calibrate("score_b", 0.6, "2026-04-01", method="clipping")
        cal.reset_history("score_a")
        assert "score_a" not in cal._history
        assert "score_b" in cal._history

    def test_reset_history_all(self):
        """전체 history 초기화."""
        cal = AgentCalibrator(agent_name="Emily")
        cal.calibrate("score_a", 0.5, "2026-04-01", method="clipping")
        cal.calibrate("score_b", 0.6, "2026-04-01", method="clipping")
        cal.reset_history()
        assert len(cal._history) == 0


# ---------------------------------------------------------------------------
# Propagation Audit Tests
# ---------------------------------------------------------------------------

class TestAuditEmilyToBob:
    """audit_emily_to_bob 테스트."""

    def _make_emily_packet(self, **kwargs):
        base = {
            "regime": "bull",
            "market_bias": "bullish",
            "technical_direction": "up",
            "technical_confidence": 0.8,
            "reversal_risk": 0.3,
        }
        base.update(kwargs)
        return base

    def _make_bob_output(self, candidates=None):
        if candidates is None:
            candidates = [
                {
                    "type": "directional",
                    "technical_alignment": 0.8,
                    "logic_summary": "bull up regime",
                    "regime_fit": 0.5,
                }
            ]
        return {"candidate_strategies": candidates}

    def test_technical_fields_all_present_high_adoption_rate(self):
        """technical_fields 모두 있으면 technical_signal_adoption_rate 높음."""
        emily = self._make_emily_packet()
        bob = self._make_bob_output(candidates=[
            {"type": "directional", "technical_alignment": 0.9, "logic_summary": "bull", "regime_fit": 0.5}
        ])
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        # 모든 technical_fields 존재 + candidate가 tech_aligned → rate 높음
        assert log.technical_signal_adoption_rate > 0.5

    def test_reversal_risk_high_no_hedge_dropped_critical(self):
        """reversal_risk > 0.6인데 hedged strategy 없으면 dropped_critical_signal_rate = 1.0."""
        emily = self._make_emily_packet(reversal_risk=0.8)
        bob = self._make_bob_output(candidates=[
            {"type": "directional", "technical_alignment": 0.5, "logic_summary": "test", "regime_fit": 0.4}
        ])
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        assert log.dropped_critical_signal_rate == pytest.approx(1.0)

    def test_reversal_risk_high_with_hedge_not_dropped(self):
        """reversal_risk > 0.6이지만 hedged strategy 있으면 dropped_critical_signal_rate = 0.0."""
        emily = self._make_emily_packet(reversal_risk=0.8)
        bob = self._make_bob_output(candidates=[
            {"type": "hedged", "technical_alignment": 0.5, "logic_summary": "hedge", "regime_fit": 0.4}
        ])
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        assert log.dropped_critical_signal_rate == pytest.approx(0.0)

    def test_contradiction_defensive_directional_high_regime_fit(self):
        """Emily defensive, Bob에 directional high regime_fit → has_contradiction = True."""
        emily = self._make_emily_packet(market_bias="defensive")
        bob = self._make_bob_output(candidates=[
            {"type": "directional", "technical_alignment": 0.5, "logic_summary": "long", "regime_fit": 0.8}
        ])
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        assert log.has_contradiction is True

    def test_no_contradiction_when_not_defensive(self):
        """Emily가 defensive가 아니면 contradiction 없음."""
        emily = self._make_emily_packet(market_bias="bullish")
        bob = self._make_bob_output(candidates=[
            {"type": "directional", "technical_alignment": 0.5, "logic_summary": "long", "regime_fit": 0.9}
        ])
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        assert log.has_contradiction is False

    def test_returns_propagation_audit_log(self):
        """PropagationAuditLog 반환 확인."""
        emily = self._make_emily_packet()
        bob = self._make_bob_output()
        log = audit_emily_to_bob(emily, bob, "2026-04-01")
        assert isinstance(log, PropagationAuditLog)
        assert log.source_agent == "Emily"
        assert log.target_agent == "Bob"
        assert log.date == "2026-04-01"
        assert 0.0 <= log.adopted_keyword_rate <= 1.0
        assert 0.0 <= log.dropped_critical_signal_rate <= 1.0
        assert 0.0 <= log.semantic_similarity_score <= 1.0
        assert 0.0 <= log.technical_signal_adoption_rate <= 1.0


class TestAuditBobToDave:
    """audit_bob_to_dave 테스트."""

    def _make_bob_packet(self, **kwargs):
        base = {
            "strategy_name": "momentum_long",
            "strategy_confidence": 0.7,
            "technical_alignment": 0.8,
            "failure_conditions": ["volatility spike", "trend reversal"],
        }
        base.update(kwargs)
        return base

    def _make_dave_output(self, **kwargs):
        base = {
            "risk_level": "medium",
            "recommended_controls": ["stop loss", "position sizing"],
        }
        base.update(kwargs)
        return base

    def test_low_confidence_low_risk_level_contradiction(self):
        """strategy_confidence < 0.4, risk_level 'low' → has_contradiction = True."""
        bob = self._make_bob_packet(strategy_confidence=0.3)
        dave = self._make_dave_output(risk_level="low")
        log = audit_bob_to_dave(bob, dave, "2026-04-01")
        assert log.has_contradiction is True

    def test_high_confidence_low_risk_no_contradiction(self):
        """strategy_confidence >= 0.4이면 risk_level 'low'여도 contradiction 없음."""
        bob = self._make_bob_packet(strategy_confidence=0.8)
        dave = self._make_dave_output(risk_level="low")
        log = audit_bob_to_dave(bob, dave, "2026-04-01")
        assert log.has_contradiction is False

    def test_failure_conditions_keywords_adopted(self):
        """failure_conditions 키워드가 Dave output에 있으면 adopted_keyword_rate 높음."""
        bob = self._make_bob_packet(failure_conditions=["volatility", "drawdown"])
        dave = self._make_dave_output()
        # dave_output에 failure_condition 단어를 포함시킴
        dave["recommended_controls"] = ["monitor volatility", "limit drawdown exposure"]
        log = audit_bob_to_dave(bob, dave, "2026-04-01")
        assert log.adopted_keyword_rate > 0.5

    def test_failure_conditions_not_adopted_low_rate(self):
        """failure_conditions 키워드가 Dave output에 없으면 adopted_keyword_rate 낮음."""
        bob = self._make_bob_packet(failure_conditions=["xyzunique1", "xyzunique2"])
        dave = self._make_dave_output()
        dave["recommended_controls"] = ["standard controls"]
        log = audit_bob_to_dave(bob, dave, "2026-04-01")
        assert log.adopted_keyword_rate == pytest.approx(0.0)

    def test_returns_propagation_audit_log(self):
        """PropagationAuditLog 반환 확인."""
        bob = self._make_bob_packet()
        dave = self._make_dave_output()
        log = audit_bob_to_dave(bob, dave, "2026-04-01")
        assert isinstance(log, PropagationAuditLog)
        assert log.source_agent == "Bob"
        assert log.target_agent == "Dave"
        assert log.date == "2026-04-01"
        assert 0.0 <= log.adopted_keyword_rate <= 1.0
        assert 0.0 <= log.dropped_critical_signal_rate <= 1.0
        assert 0.0 <= log.semantic_similarity_score <= 1.0
        assert 0.0 <= log.technical_signal_adoption_rate <= 1.0


class TestAuditToOtto:
    """audit_to_otto 테스트."""

    def _make_otto_packet(self, **kwargs):
        base = {
            "risk_score": 0.4,
            "reversal_risk": 0.3,
            "market_regime": "bull",
            "selected_strategy_name": "momentum_long",
            "technical_confidence": 0.7,
            "trigger_risk_alert": False,
        }
        base.update(kwargs)
        return base

    def _make_otto_output(self, **kwargs):
        base = {
            "approval_status": "approved",
            "allocation": {"equities": 0.6, "bonds": 0.3, "cash": 0.1},
            "notes": "standard allocation",
        }
        base.update(kwargs)
        return base

    def test_high_risk_approved_contradiction(self):
        """risk_score > 0.75, approval_status 'approved' → has_contradiction = True."""
        packet = self._make_otto_packet(risk_score=0.9)
        otto_out = self._make_otto_output(approval_status="approved")
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert log.has_contradiction is True

    def test_high_risk_rejected_no_contradiction(self):
        """risk_score > 0.75이지만 approval_status가 'approved'가 아니면 contradiction 없음."""
        packet = self._make_otto_packet(risk_score=0.9)
        otto_out = self._make_otto_output(approval_status="rejected")
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert log.has_contradiction is False

    def test_low_risk_approved_no_contradiction(self):
        """risk_score <= 0.75이면 approved여도 contradiction 없음."""
        packet = self._make_otto_packet(risk_score=0.5)
        otto_out = self._make_otto_output(approval_status="approved")
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert log.has_contradiction is False

    def test_reversal_risk_high_equities_high_dropped_critical(self):
        """reversal_risk > 0.6, equities > 0.7 → dropped_critical_signal_rate = 1.0."""
        packet = self._make_otto_packet(reversal_risk=0.8)
        otto_out = self._make_otto_output(
            approval_status="rejected",
            allocation={"equities": 0.8, "bonds": 0.1, "cash": 0.1},
        )
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert log.dropped_critical_signal_rate == pytest.approx(1.0)

    def test_reversal_risk_high_equities_low_not_dropped(self):
        """reversal_risk > 0.6이지만 equities <= 0.7이면 dropped_critical_signal_rate = 0.0."""
        packet = self._make_otto_packet(reversal_risk=0.8)
        otto_out = self._make_otto_output(
            approval_status="rejected",
            allocation={"equities": 0.5, "bonds": 0.3, "cash": 0.2},
        )
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert log.dropped_critical_signal_rate == pytest.approx(0.0)

    def test_returns_propagation_audit_log(self):
        """PropagationAuditLog 반환 확인."""
        packet = self._make_otto_packet()
        otto_out = self._make_otto_output()
        log = audit_to_otto(packet, otto_out, "2026-04-01")
        assert isinstance(log, PropagationAuditLog)
        assert log.source_agent == "Aggregator"
        assert log.target_agent == "Otto"
        assert log.date == "2026-04-01"
        assert 0.0 <= log.adopted_keyword_rate <= 1.0
        assert 0.0 <= log.dropped_critical_signal_rate <= 1.0
        assert 0.0 <= log.semantic_similarity_score <= 1.0
        assert 0.0 <= log.technical_signal_adoption_rate <= 1.0
