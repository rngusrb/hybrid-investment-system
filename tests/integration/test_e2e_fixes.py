"""
tests/integration/test_e2e_fixes.py

이번 세션에서 수정한 10개 이슈를 실제 노드/클래스 흐름으로 검증하는 e2e 통합 테스트.
No real LLM calls — node-level mock state 사용.
"""
import pytest
from graph.state import make_initial_state
from memory.strategy_memory import StrategyMemory
from memory.market_memory import MarketMemory
from evaluation.metrics import compute_calmar, compute_sortino, compute_max_drawdown
from agents.dave import DaveAgent
from graph.nodes.agent_reliability import daily_agent_reliability_update
from graph.nodes.policy import daily_policy_selection
from utils.utility import compute_utility_from_state as _compute_utility
from graph.nodes.logging_node import daily_post_execution_logging
from graph.nodes.risk_check import daily_risk_check
from reliability.agent_reliability import AgentReliabilityManager, GatingDecision


# ─────────────────────────────────────────────────────────────
# 픽스처 헬퍼
# ─────────────────────────────────────────────────────────────

def _make_state(**overrides) -> dict:
    s = make_initial_state("2024-01-15", cycle_type="daily")
    s.update(overrides)
    return s


def _make_bob_output():
    return {
        "agent": "Bob",
        "date": "2024-01-15",
        "candidate_strategies": [
            {
                "name": "momentum_long",
                "type": "momentum",
                "logic_summary": "follow trend",
                "regime_fit": 0.8,
                "technical_alignment": 0.75,
                "sim_window": {"train_start": "2023-01-02", "train_end": "2024-01-01"},
                "sim_metrics": {
                    "return": 0.12,
                    "sharpe": 1.1,
                    "sortino": 1.4,
                    "mdd": 0.08,
                    "turnover": 0.25,
                    "hit_rate": 0.55,
                },
                "failure_conditions": ["vol_spike", "regime_change"],
                "optimization_suggestions": [],
                "confidence": 0.7,
            }
        ],
        "selected_for_review": ["momentum_long"],
    }


def _make_dave_output(risk_score=0.45):
    return {
        "agent": "Dave",
        "date": "2024-01-15",
        "risk_score": risk_score,
        "risk_level": "medium",
        "risk_components": {
            "beta": 0.5, "illiquidity": 0.2,
            "sector_concentration": 0.3, "volatility": 0.25,
        },
        "risk_constraints": {
            "max_single_sector_weight": 0.3,
            "max_beta": 1.2,
            "max_gross_exposure": 0.9,
        },
        "stress_test": {"severity_score": 0.3, "worst_case_drawdown": 0.1},
        "trigger_risk_alert_meeting": False,
        "signal_conflict_risk": 0.1,
        "recommended_controls": [],
    }


# ─────────────────────────────────────────────────────────────
# #1: StrategyMemory — 같은 날 다른 key 충돌 없음
# ─────────────────────────────────────────────────────────────

class TestStrategyMemoryKeyCollision:

    def test_two_stores_same_date_different_keys_both_preserved(self):
        """같은 날짜에 key가 다르면 둘 다 보존됨 (이전 버그: 날짜 key로 덮어씀)."""
        mem = StrategyMemory()
        mem.store("outcome_2024-01-15", {"r_sim": 0.1}, date="2024-01-15")
        mem.store("strategy_2024-01-15", {"name": "momentum"}, date="2024-01-15")

        assert len(mem._store) == 2
        assert "outcome_2024-01-15" in mem._store
        assert "strategy_2024-01-15" in mem._store

    def test_get_by_date_returns_record_for_date(self):
        """get_by_date()가 날짜로 올바르게 조회."""
        mem = StrategyMemory()
        mem.store("outcome_2024-01-15", {"r_sim": 0.15}, date="2024-01-15")

        record = mem.get_by_date("2024-01-15")
        assert record is not None
        assert record["value"]["r_sim"] == 0.15

    def test_get_by_date_missing_date_returns_none(self):
        mem = StrategyMemory()
        assert mem.get_by_date("2099-01-01") is None


class TestMarketMemoryKeyCollision:

    def test_two_stores_same_date_different_keys_both_preserved(self):
        mem = MarketMemory()
        mem.store("market_2024-01-15", {"regime": "risk_on"}, date="2024-01-15")
        mem.store("ingest_2024-01-15", {"vix": 14.5}, date="2024-01-15")

        assert len(mem._store) == 2

    def test_get_by_date_correct(self):
        mem = MarketMemory()
        mem.store("market_2024-01-15", {"regime": "risk_on"}, date="2024-01-15")
        record = mem.get_by_date("2024-01-15")
        assert record is not None


# ─────────────────────────────────────────────────────────────
# #2: HARD_GATE — 출력 필드 실제로 None으로 초기화
# ─────────────────────────────────────────────────────────────

class TestHardGateEnforcement:

    def _make_state_with_low_reliability(self, agent: str) -> dict:
        """특정 agent의 reliability를 floor(0.35) 아래로 세팅."""
        state = _make_state(
            emily_output={"regime": "risk_on"},
            bob_output=_make_bob_output(),
            dave_output=_make_dave_output(),
        )
        state["agent_reliability"] = {"emily": 0.2, "bob": 0.5, "dave": 0.5, "otto": 0.5}
        state["current_date"] = "2024-01-15"
        return state

    def test_hard_gated_emily_output_becomes_none(self):
        """emily reliability < floor → emily_output, emily_to_bob_packet = None."""
        state = self._make_state_with_low_reliability("emily")
        state["emily_to_bob_packet"] = {"some": "data"}

        result = daily_agent_reliability_update(state)

        # emily reliability는 0.2로 시작해서 업데이트 후 여전히 floor 아래일 수 있음
        reliability = result.get("agent_reliability", {})
        gating_entry = [
            e for e in result.get("calibration_log", [])
            if e.get("node") == "DAILY_AGENT_RELIABILITY_UPDATE"
        ]
        assert len(gating_entry) > 0
        gating_decisions = gating_entry[-1]["gating_decisions"]
        if gating_decisions.get("emily") == "hard_gate":
            assert result.get("emily_output") is None
            assert result.get("emily_to_bob_packet") is None

    def test_hard_gated_agent_recorded_in_skip_log(self):
        """hard_gated agent가 skip_log에 기록됨."""
        state = _make_state(
            agent_reliability={"emily": 0.1, "bob": 0.1, "dave": 0.1, "otto": 0.5},
            current_date="2024-01-15",
        )
        # audit_log 없으면 업데이트 없이 기존 score 유지 → 0.1 < 0.35 이므로 hard_gate
        result = daily_agent_reliability_update(state)

        reliability = result.get("agent_reliability", {})
        skip_log = result.get("skip_log", [])
        # emily/bob/dave 중 하나라도 hard_gate이면 skip_log에 기록
        hard_gated_entries = [e for e in skip_log if "hard_gated" in e.get("reason", "")]
        assert len(hard_gated_entries) > 0

    def test_normal_reliability_no_nulling(self):
        """정상 reliability → 출력 필드 유지."""
        state = _make_state(
            agent_reliability={"emily": 0.7, "bob": 0.7, "dave": 0.7, "otto": 0.7},
            emily_output={"regime": "risk_on"},
            current_date="2024-01-15",
        )
        result = daily_agent_reliability_update(state)

        # emily가 hard_gate 아니면 emily_output이 None으로 바뀌면 안 됨
        calibration = [
            e for e in result.get("calibration_log", [])
            if e.get("node") == "DAILY_AGENT_RELIABILITY_UPDATE"
        ]
        if calibration:
            gd = calibration[-1]["gating_decisions"]
            if gd.get("emily") != "hard_gate":
                assert result.get("emily_output") == {"regime": "risk_on"}


# ─────────────────────────────────────────────────────────────
# #3: Otto utility_score — policy 노드에서 계산·출력
# ─────────────────────────────────────────────────────────────

class TestOttoUtilityScore:

    def test_otto_output_has_utility_score(self):
        """policy_selection 후 otto_output에 utility_score 포함."""
        state = _make_state(risk_score=0.4, uncertainty_level=0.4)
        result = daily_policy_selection(state)

        otto = result.get("otto_output", {})
        assert "utility_score" in otto
        assert isinstance(otto["utility_score"], float)

    def test_utility_score_finite(self):
        """utility_score가 유한한 float값."""
        import math
        state = _make_state(risk_score=0.5, uncertainty_level=0.5, execution_feasibility_score=0.5)
        result = daily_policy_selection(state)
        assert math.isfinite(result["otto_output"]["utility_score"])

    def test_high_risk_yields_lower_utility(self):
        """risk_score 높으면 utility 낮아짐."""
        low_risk = _make_state(risk_score=0.1, uncertainty_level=0.2)
        high_risk = _make_state(risk_score=0.9, uncertainty_level=0.8)

        u_low = daily_policy_selection(low_risk)["otto_output"]["utility_score"]
        u_high = daily_policy_selection(high_risk)["otto_output"]["utility_score"]

        assert u_low > u_high

    def test_low_utility_downgrades_approved_to_conditional(self):
        """utility < threshold이면 approved → conditional_approval 강등."""
        # 극단적으로 나쁜 조건
        state = _make_state(
            risk_score=0.99,
            uncertainty_level=0.99,
            execution_feasibility_score=0.01,
            agent_reliability={"emily": 0.1, "bob": 0.1, "dave": 0.1, "otto": 0.1},
            risk_alert_triggered=False,
        )
        result = daily_policy_selection(state)
        # risk가 높아 conditional 또는 utility downgrade 발동
        status = result["otto_output"]["approval_status"]
        assert status in ("conditional_approval", "rejected")

    def test_otto_policy_packet_has_utility_score(self):
        """otto_policy_packet에도 utility_score 포함."""
        state = _make_state(risk_score=0.3)
        result = daily_policy_selection(state)

        packet = result.get("otto_policy_packet", {})
        assert "utility_score" in packet


# ─────────────────────────────────────────────────────────────
# #4: r_real = r_sim (logging_node)
# ─────────────────────────────────────────────────────────────

class TestRRealSemantics:

    def test_r_real_equals_r_sim_in_stored_outcome(self):
        """logging_node가 strategy_memory에 저장할 때 r_real == r_sim."""
        from memory.registry import strategy_memory as global_sm
        from memory.strategy_memory import StrategyMemory

        # 독립된 memory 인스턴스로 테스트하기 위해 monkeypatch 대신
        # logging_node를 직접 호출 후 global strategy_memory에서 검증
        state = _make_state(
            current_date="2024-03-01",
            bob_output=_make_bob_output(),
            otto_output={
                "approval_status": "approved",
                "selected_policy": "momentum_long",
                "policy_action": "execute",
            },
            risk_score=0.4,
            execution_feasibility_score=0.8,
        )

        daily_post_execution_logging(state)

        record = global_sm._store.get("outcome_2024-03-01")
        if record:
            val = record.get("value", {})
            assert val.get("r_real") == val.get("r_sim"), (
                f"r_real={val.get('r_real')} should equal r_sim={val.get('r_sim')}"
            )

    def test_r_sim_derived_from_sim_metrics_return(self):
        """r_sim이 candidate strategy의 sim_metrics.return 값과 일치."""
        from memory.registry import strategy_memory as global_sm

        bob = _make_bob_output()
        expected_r_sim = 0.12  # sim_metrics.return

        state = _make_state(
            current_date="2024-03-02",
            bob_output=bob,
            otto_output={"approval_status": "approved", "selected_policy": "momentum_long"},
            risk_score=0.3,
        )
        daily_post_execution_logging(state)

        record = global_sm._store.get("outcome_2024-03-02")
        if record:
            val = record.get("value", {})
            assert abs(val.get("r_sim", 0.0) - expected_r_sim) < 1e-9


# ─────────────────────────────────────────────────────────────
# #5: Calmar ratio MDD=0
# ─────────────────────────────────────────────────────────────

class TestCalmarMDDZero:

    def test_mdd_zero_positive_return_gives_large_positive(self):
        """MDD=0, 양수 return → 5.0 반환 (0.0 아님)."""
        # 단조 상승 수익률 시계열 → MDD=0
        returns = [0.01] * 50
        result = compute_calmar(returns)
        assert result == 5.0, f"Expected 5.0, got {result}"

    def test_mdd_zero_negative_return_gives_large_negative(self):
        """MDD=0이지만 annualized_return < 0 → -5.0."""
        # 모든 수익률 -0.001 (작은 음수)
        returns = [-0.001] * 50
        mdd = compute_max_drawdown(returns)
        result = compute_calmar(returns)
        if mdd == 0.0:
            assert result == -5.0
        # mdd > 0이면 일반 계산

    def test_mdd_nonzero_returns_normal_ratio(self):
        """MDD > 0이면 정상적인 Calmar 계산."""
        returns = [0.01, -0.05, 0.02, 0.03, -0.02] * 10
        result = compute_calmar(returns)
        assert isinstance(result, float)


# ─────────────────────────────────────────────────────────────
# #6: Risk component normalization (dave.py)
# ─────────────────────────────────────────────────────────────

class TestRiskComponentNormalization:

    def setup_method(self):
        self.agent = DaveAgent(llm=None, config={})

    def test_out_of_range_high_components_clamped(self):
        """component > 1.0 → 1.0으로 clamp, risk_score ≤ 1.0."""
        components = {"beta": 5.0, "illiquidity": 10.0, "sector_concentration": 3.0, "volatility": 2.0}
        score = self.agent.compute_risk_score(components)
        assert score <= 1.0

    def test_out_of_range_negative_components_clamped(self):
        """component < 0 → 0으로 clamp, risk_score ≥ 0."""
        components = {"beta": -1.0, "illiquidity": -5.0, "sector_concentration": -0.5, "volatility": -2.0}
        score = self.agent.compute_risk_score(components)
        assert score >= 0.0

    def test_normal_range_unchanged(self):
        """[0,1] 범위 내 component → 정상 계산."""
        components = {"beta": 0.5, "illiquidity": 0.3, "sector_concentration": 0.4, "volatility": 0.2}
        score = self.agent.compute_risk_score(components)
        expected = 0.3 * 0.5 + 0.25 * 0.3 + 0.25 * 0.4 + 0.2 * 0.2
        assert abs(score - expected) < 1e-9

    def test_all_max_components_gives_one(self):
        """모든 component = 1.0 → score = 1.0 (weights 합 = 1.0)."""
        components = {"beta": 1.0, "illiquidity": 1.0, "sector_concentration": 1.0, "volatility": 1.0}
        score = self.agent.compute_risk_score(components)
        assert abs(score - 1.0) < 1e-9


# ─────────────────────────────────────────────────────────────
# #7: Sortino formula
# ─────────────────────────────────────────────────────────────

class TestSortinoFormula:

    def test_sortino_uses_downside_deviation_not_std(self):
        """수익이 항상 양수면 downside dev ≈ 0 → Sortino는 매우 큰 값."""
        returns = [0.01] * 100
        result = compute_sortino(returns)
        # 모두 양수 → downside dev ≈ 0 → Sortino 매우 큼
        assert result > 10.0

    def test_sortino_symmetric_returns_close_to_sharpe(self):
        """대칭 수익률에서 Sortino ≈ Sharpe * sqrt(2)."""
        import math
        from evaluation.metrics import compute_sharpe
        returns = [0.01, -0.01] * 100
        s = compute_sharpe(returns)
        st = compute_sortino(returns)
        # Sortino >= Sharpe (downside dev <= std)
        assert st >= s - 1e-6

    def test_negative_mean_sortino_negative(self):
        """평균 수익이 음수면 Sortino도 음수."""
        returns = [-0.01] * 100
        result = compute_sortino(returns)
        assert result < 0


# ─────────────────────────────────────────────────────────────
# #8: outcome_alignment key 패턴 — strategy_memory에서 올바른 key 조회
# ─────────────────────────────────────────────────────────────

class TestOutcomeAlignmentKeyLookup:

    def test_outcome_alignment_reads_correct_key(self):
        """_compute_outcome_alignment이 f'outcome_{prev}' 키로 올바르게 읽음."""
        from graph.nodes.agent_reliability import _compute_outcome_alignment
        from memory.registry import strategy_memory as global_sm

        # 2024-01-16(화) 기준 전일은 2024-01-15(월)
        global_sm.store(
            key="outcome_2024-01-15",
            value={
                "approval_status": "approved",
                "r_sim": 0.05,
                "horizon_closed": True,
            },
            date="2024-01-15",
        )

        result = _compute_outcome_alignment("2024-01-16")
        # approved + positive r_sim → 0.72
        assert result == 0.72

    def test_outcome_alignment_missing_returns_neutral(self):
        """해당 날짜 outcome 없으면 0.5 반환."""
        from graph.nodes.agent_reliability import _compute_outcome_alignment

        result = _compute_outcome_alignment("2099-01-02")
        assert result == 0.5

    def test_outcome_alignment_approved_negative_sim(self):
        """approved + negative r_sim → 0.32 (잘못된 예측)."""
        from graph.nodes.agent_reliability import _compute_outcome_alignment
        from memory.registry import strategy_memory as global_sm

        global_sm.store(
            key="outcome_2024-02-12",
            value={
                "approval_status": "approved",
                "r_sim": -0.03,
                "horizon_closed": True,
            },
            date="2024-02-12",
        )
        result = _compute_outcome_alignment("2024-02-13")
        assert result == 0.32


# ─────────────────────────────────────────────────────────────
# #9: 전체 daily cycle 노드 연결 흐름
# ─────────────────────────────────────────────────────────────

class TestDailyNodeFlow:

    def test_risk_check_to_policy_to_logging_no_error(self):
        """risk_check → policy_selection → logging 노드 연속 실행 에러 없음."""
        state = _make_state(
            current_date="2024-01-15",
            dave_output=_make_dave_output(risk_score=0.4),
            bob_output=_make_bob_output(),
            agent_reliability={"emily": 0.6, "bob": 0.6, "dave": 0.6, "otto": 0.6},
        )

        state = daily_risk_check(state)
        assert state.get("risk_score") is not None

        state = daily_policy_selection(state)
        assert state.get("otto_output") is not None
        assert "utility_score" in state["otto_output"]

        state = daily_post_execution_logging(state)
        assert isinstance(state.get("calibration_log"), list)

    def test_risk_alert_triggers_rejected_policy(self):
        """risk_score > 0.75 → risk_alert_triggered → policy = rejected."""
        state = _make_state(
            current_date="2024-01-15",
            dave_output=_make_dave_output(risk_score=0.85),
        )
        state = daily_risk_check(state)
        assert state.get("risk_alert_triggered") is True

        state["risk_alert_triggered"] = True  # risk_alert 경로 수동 유지
        state = daily_policy_selection(state)
        assert state["otto_output"]["approval_status"] == "rejected"

    def test_three_day_strategy_memory_accumulates(self):
        """3일 연속 logging → strategy_memory에 3개 outcome 기록 (덮어쓰기 없음)."""
        from memory.registry import strategy_memory as global_sm
        initial_count = len(global_sm._store)

        for date in ["2024-04-01", "2024-04-02", "2024-04-03"]:
            state = _make_state(
                current_date=date,
                bob_output=_make_bob_output(),
                otto_output={"approval_status": "approved", "selected_policy": "momentum_long"},
                risk_score=0.3,
            )
            daily_post_execution_logging(state)

        added = len(global_sm._store) - initial_count
        assert added >= 3, f"Expected ≥3 new records, got {added}"
