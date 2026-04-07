"""
tests/integration/test_multicycle.py

멀티사이클 state 격리 검증.
- 사이클 간 state 오염이 없는지 확인
- agent_reliability 등 cross-cycle 필드가 올바르게 전달되는지 확인
- StrategyMemory가 날짜별로 독립 저장되는지 확인
"""
import pytest
from graph.state import make_initial_state, reset_for_next_cycle, _CROSS_CYCLE_KEYS
from graph.nodes.policy import daily_policy_selection
from graph.nodes.logging_node import daily_post_execution_logging
from graph.nodes.risk_check import daily_risk_check
from memory.strategy_memory import StrategyMemory


# ─────────────────────────────────────────────────────────────────────────────
# reset_for_next_cycle 격리 테스트
# ─────────────────────────────────────────────────────────────────────────────

class TestResetForNextCycle:
    def test_date_is_updated(self):
        s1 = make_initial_state("2024-01-01")
        s2 = reset_for_next_cycle(s1, "2024-01-02")
        assert s2["current_date"] == "2024-01-02"
        assert s1["current_date"] == "2024-01-01"  # 원본 불변

    def test_cycle_specific_fields_are_reset(self):
        s1 = make_initial_state("2024-01-01")
        s1["emily_output"] = {"market_regime": "risk_on"}
        s1["bob_output"] = {"candidate_strategies": [{"name": "MomStrat"}]}
        s1["dave_output"] = {"risk_score": 0.4}
        s1["otto_output"] = {"approval_status": "approved"}
        s1["raw_market_data"] = {"close": 500.0}
        s1["risk_score"] = 0.8
        s1["risk_alert_triggered"] = True
        s1["execution_plan"] = {"entry_style": "immediate"}
        s1["skip_log"] = [{"node": "X"}]
        s1["retry_log"] = [{"agent": "Bob"}]

        s2 = reset_for_next_cycle(s1, "2024-01-02")

        # 사이클별 필드 초기화 확인
        assert s2["emily_output"] is None
        assert s2["bob_output"] is None
        assert s2["dave_output"] is None
        assert s2["otto_output"] is None
        assert s2["raw_market_data"] is None
        assert s2["risk_score"] == 0.0
        assert s2["risk_alert_triggered"] is False
        assert s2["execution_plan"] is None
        assert s2["skip_log"] == []
        assert s2["retry_log"] == []

    def test_agent_reliability_persists(self):
        s1 = make_initial_state("2024-01-01")
        s1["agent_reliability"] = {"emily": 0.85, "bob": 0.72, "dave": 0.91, "otto": 0.68}

        s2 = reset_for_next_cycle(s1, "2024-01-02")
        assert s2["agent_reliability"] == {"emily": 0.85, "bob": 0.72, "dave": 0.91, "otto": 0.68}

    def test_calibration_log_persists(self):
        s1 = make_initial_state("2024-01-01")
        s1["calibration_log"] = [{"date": "2024-01-01", "node": "AGENT_RELIABILITY"}]

        s2 = reset_for_next_cycle(s1, "2024-01-02")
        assert len(s2["calibration_log"]) == 1
        assert s2["calibration_log"][0]["date"] == "2024-01-01"

    def test_polygon_fetcher_persists(self):
        s1 = make_initial_state("2024-01-01")
        mock_fetcher = object()  # 임의 객체
        s1["_polygon_fetcher"] = mock_fetcher

        s2 = reset_for_next_cycle(s1, "2024-01-02")
        assert s2["_polygon_fetcher"] is mock_fetcher

    def test_independent_state_objects(self):
        """두 사이클의 리스트 필드는 독립된 객체여야 함 (aliasing 없음)."""
        s1 = make_initial_state("2024-01-01")
        s2 = reset_for_next_cycle(s1, "2024-01-02")

        s1["skip_log"].append({"test": "only_s1"})
        assert s2["skip_log"] == []  # s2에 영향 없어야 함

    def test_five_day_cycle_type_is_preserved(self):
        s1 = make_initial_state("2024-01-01")
        s2 = reset_for_next_cycle(s1, "2024-01-02", cycle_type="weekly", is_week_end=True)
        assert s2["cycle_type"] == "weekly"
        assert s2["is_week_end"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 5일 연속 policy + logging — state 오염 없는지 검증
# ─────────────────────────────────────────────────────────────────────────────

class TestFiveDaySequentialCycle:
    DATES = ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"]

    def _run_day(self, state: dict, date: str, risk_score: float = 0.4) -> dict:
        """단일 날짜 policy + logging 실행."""
        state = dict(state)
        state["current_date"] = date
        state["risk_score"] = risk_score
        state["bob_output"] = {
            "selected_for_review": [f"strategy_{date}"],
            "candidate_strategies": [{
                "name": f"strategy_{date}",
                "sim_metrics": {"return": 0.01 * (self.DATES.index(date) + 1)},
            }],
        }
        state["otto_output"] = {
            "approval_status": "approved",
            "selected_policy": f"strategy_{date}",
        }
        state = daily_post_execution_logging(state)
        return state

    def test_five_days_no_previous_date_in_current(self):
        """각 사이클의 current_date가 이전 날짜로 오염되지 않아야 함."""
        state = make_initial_state(self.DATES[0])
        seen_dates = []
        for i, date in enumerate(self.DATES):
            if i > 0:
                state = reset_for_next_cycle(state, date)
            assert state["current_date"] == date
            state = self._run_day(state, date)
            seen_dates.append(state["current_date"])
        assert seen_dates == self.DATES

    def test_agent_reliability_accumulates_across_cycles(self):
        """agent_reliability가 사이클마다 업데이트되어 누적되어야 함."""
        state = make_initial_state(self.DATES[0])
        state["agent_reliability"] = {"emily": 0.5, "bob": 0.5, "dave": 0.5, "otto": 0.5}

        for i, date in enumerate(self.DATES):
            if i > 0:
                state = reset_for_next_cycle(state, date)
            # 매 사이클 reliability 업데이트 시뮬레이션
            rel = dict(state["agent_reliability"])
            rel["emily"] = min(1.0, rel["emily"] + 0.05)
            state["agent_reliability"] = rel

        # 5사이클 후 emily reliability = 0.5 + 5*0.05 = 0.75
        assert abs(state["agent_reliability"]["emily"] - 0.75) < 0.001

    def test_bob_output_from_prev_day_not_leaked(self):
        """이전 날의 bob_output이 다음 날 사이클에 누출되지 않아야 함."""
        state = make_initial_state(self.DATES[0])
        state["bob_output"] = {
            "selected_for_review": ["OldStrategy"],
            "candidate_strategies": [{"name": "OldStrategy", "sim_metrics": {"return": 0.99}}],
        }
        state = reset_for_next_cycle(state, self.DATES[1])
        assert state["bob_output"] is None

    def test_risk_alert_resets_each_cycle(self):
        """risk_alert_triggered가 사이클마다 초기화되어야 함."""
        state = make_initial_state(self.DATES[0])
        state["risk_alert_triggered"] = True
        state["risk_score"] = 0.9

        state = reset_for_next_cycle(state, self.DATES[1])
        assert state["risk_alert_triggered"] is False
        assert state["risk_score"] == 0.0

    def test_strategy_memory_independent_per_date(self):
        """StrategyMemory는 날짜별로 독립 저장, 동일 키 덮어쓰기 없음."""
        mem = StrategyMemory()
        for date in self.DATES:
            mem.store(
                key=f"outcome_{date}",
                value={"r_sim": 0.01, "date": date},
                date=date,
                tags=["outcome"],
            )
        # 모든 날짜가 독립 저장됐는지 확인
        for date in self.DATES:
            result = mem.get_by_date(date)
            assert result is not None
            assert result.get("value", {}).get("date") == date

    def test_calibration_log_grows_across_cycles(self):
        """calibration_log가 사이클 간 누적되어야 함."""
        state = make_initial_state(self.DATES[0])
        for i, date in enumerate(self.DATES):
            if i > 0:
                state = reset_for_next_cycle(state, date)
            state["current_date"] = date
            state["otto_output"] = {"approval_status": "approved", "selected_policy": "S"}
            state["bob_output"] = {
                "selected_for_review": ["S"],
                "candidate_strategies": [{"name": "S", "sim_metrics": {"return": 0.01}}],
            }
            state = daily_post_execution_logging(state)

        # 5사이클 후 calibration_log에 최소 5개 항목
        assert len(state["calibration_log"]) >= 5
