"""
tests/integration/test_bc_graph.py — bc_graph 전체 흐름 통합 테스트

검증 대상:
  1. 정상 경로: Dave(risk≤0.7) → Otto(approved) → END
  2. conditional edge 단위: route_after_dave / route_after_otto / route_after_backtester
  3. Dave risk>0.7 분기: BC_BACKTESTER_DEFENSIVE 경유 → dave_rerun_triggered=True
  4. Otto rejected 분기: PM 재실행 → otto_retry_count 증가 → approved → END
  5. Otto rejected 반복: retry_count > 2 이면 END 탈출 (무한루프 방지)

모든 노드: mock stub — LLM/API 호출 없음.
"""
import pytest
from unittest.mock import patch
from langgraph.graph import END

from graph.bc_graph import (
    compile_bc_graph,
    route_after_dave,
    route_after_otto,
    route_after_backtester,
)
from graph.bc_state import make_initial_bc_state


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _base_state(**overrides) -> dict:
    s = make_initial_bc_state(
        current_date="2024-01-15",
        tickers=["AAPL"],
        llm_analyst=None,
        llm_decision=None,
    )
    s.update(overrides)
    return s


# bc_graph.py 내 모듈 수준 이름 패치 (add_node 시점에 stub 등록)
_NOOP_PATCHES = {
    "graph.bc_graph.bc_emily_node":              lambda s: {"emily_output": {}, "emily_context": ""},
    "graph.bc_graph.bc_stock_node":              lambda s: {"stock_results": [], "sim_results": {}, "sim_context": ""},
    "graph.bc_graph.bc_backtester_node":         lambda s: {"sim_results": {}},
    "graph.bc_graph.bc_meetings_node":           lambda s: {"meetings": {}, "meetings_context": ""},
    "graph.bc_graph.bc_calibration_node":        lambda s: {"calibration": {}, "calibration_context": ""},
    "graph.bc_graph.bc_reliability_update_node": lambda s: {"reliability_summary": {}},
    "graph.bc_graph.bc_portfolio_node":          lambda s: {"portfolio": {"equities": 0.6, "cash": 0.4}},
}


# ── conditional edge 단위 테스트 ─────────────────────────────────────────────

class TestConditionalEdges:
    """route_after_dave / route_after_otto / route_after_backtester 직접 검증."""

    # route_after_dave
    def test_dave_high_risk_first_time_goes_defensive(self):
        s = _base_state(dave_output={"risk_score": 0.8}, dave_rerun_triggered=False)
        assert route_after_dave(s) == "BC_BACKTESTER_DEFENSIVE"

    def test_dave_high_risk_already_rerun_goes_otto(self):
        s = _base_state(dave_output={"risk_score": 0.8}, dave_rerun_triggered=True)
        assert route_after_dave(s) == "BC_OTTO"

    def test_dave_low_risk_goes_otto(self):
        s = _base_state(dave_output={"risk_score": 0.5})
        assert route_after_dave(s) == "BC_OTTO"

    def test_dave_boundary_0_7_goes_otto(self):
        """경계값: risk_score == 0.7 은 > 0.7 조건 미충족 → Otto."""
        s = _base_state(dave_output={"risk_score": 0.7})
        assert route_after_dave(s) == "BC_OTTO"

    # route_after_otto
    def test_otto_rejected_retry0_goes_pm(self):
        s = _base_state(otto_output={"approval_status": "rejected"}, otto_retry_count=0)
        assert route_after_otto(s) == "BC_PORTFOLIO_MANAGER"

    def test_otto_rejected_retry2_still_goes_pm(self):
        """retry_count == 2 은 <= 2 조건 충족 → PM 재실행 허용."""
        s = _base_state(otto_output={"approval_status": "rejected"}, otto_retry_count=2)
        assert route_after_otto(s) == "BC_PORTFOLIO_MANAGER"

    def test_otto_rejected_retry3_goes_end(self):
        """retry_count == 3 → END (무한루프 방지)."""
        s = _base_state(otto_output={"approval_status": "rejected"}, otto_retry_count=3)
        assert route_after_otto(s) == END

    def test_otto_approved_goes_end(self):
        s = _base_state(otto_output={"approval_status": "approved"})
        assert route_after_otto(s) == END

    # route_after_backtester
    def test_backtester_dave_rerun_true_goes_pm(self):
        s = _base_state(dave_rerun_triggered=True)
        assert route_after_backtester(s) == "BC_PORTFOLIO_MANAGER"

    def test_backtester_normal_goes_meetings(self):
        s = _base_state(dave_rerun_triggered=False)
        assert route_after_backtester(s) == "BC_MEETINGS"


# ── 전체 그래프 흐름 통합 테스트 ─────────────────────────────────────────────

class TestBcGraphFlow:
    """compile_bc_graph().invoke() 전체 실행 — stub 노드로 LLM/API 없음."""

    def _run(self, dave_stub, otto_stub, backtester_stub=None, pm_stub=None):
        """공통 실행 헬퍼: 지정 stub만 교체, 나머지는 noop."""
        patches = dict(_NOOP_PATCHES)
        patches["graph.bc_graph.bc_dave_node"] = dave_stub
        patches["graph.bc_graph.bc_otto_node"] = otto_stub
        if backtester_stub:
            patches["graph.bc_graph.bc_backtester_node"] = backtester_stub
        if pm_stub:
            patches["graph.bc_graph.bc_portfolio_node"] = pm_stub

        ctx = [patch(k, new=v) for k, v in patches.items()]
        for c in ctx:
            c.start()
        try:
            bc = compile_bc_graph()
            return bc.invoke(_base_state())
        finally:
            for c in ctx:
                c.stop()

    # ── 1. 정상 경로 ──────────────────────────────────────────────────────────

    def test_happy_path_ends_cleanly(self):
        """Dave risk≤0.7, Otto approved → errors 없이 정상 종료."""
        result = self._run(
            dave_stub=lambda s: {"dave_output": {"risk_score": 0.4}},
            otto_stub=lambda s: {
                "otto_output": {"approval_status": "approved", "selected_policy": "p1"},
                "portfolio":   s.get("portfolio") or {"equities": 0.6, "cash": 0.4},
            },
        )
        assert result["dave_output"]["risk_score"] == 0.4
        assert result["otto_output"]["approval_status"] == "approved"
        assert result.get("errors", []) == []

    # ── 2. Dave risk>0.7 분기 ─────────────────────────────────────────────────

    def test_dave_high_risk_triggers_defensive_and_reruns(self):
        """
        Dave risk>0.7 (최초) → BC_BACKTESTER_DEFENSIVE 경유
        → dave_rerun_triggered=True → Dave 2회 호출 검증.
        """
        dave_calls = []

        def dave_stub(state):
            dave_calls.append(state.get("dave_rerun_triggered", False))
            # 첫 호출: high risk / 두 번째 호출(rerun 후): low risk
            if len(dave_calls) == 1:
                return {"dave_output": {"risk_score": 0.85}}
            return {"dave_output": {"risk_score": 0.35}}

        def backtester_stub(state):
            return {"sim_results": {}, "risk_mode": state.get("risk_mode", "normal")}

        result = self._run(
            dave_stub=dave_stub,
            otto_stub=lambda s: {
                "otto_output": {"approval_status": "approved"},
                "portfolio":   s.get("portfolio") or {},
            },
            backtester_stub=backtester_stub,
        )

        assert len(dave_calls) == 2, f"Dave 2회 호출 기대, 실제: {len(dave_calls)}"
        # 두 번째 Dave 호출 시 dave_rerun_triggered=True
        assert dave_calls[1] is True, "두 번째 Dave 호출 시 dave_rerun_triggered=True여야 함"
        assert result["dave_rerun_triggered"] is True
        assert result.get("errors", []) == []

    # ── 3. Otto rejected → PM 재실행 ─────────────────────────────────────────

    def test_otto_rejected_retries_pm_then_approved(self):
        """
        Otto rejected (1회) → PM 재실행 → Otto approved → END.
        Otto 2회 호출, PM 2회 호출 검증.
        """
        otto_calls = []
        pm_calls = []

        def otto_stub(state):
            otto_calls.append(state.get("otto_retry_count", 0))
            if len(otto_calls) == 1:
                return {
                    "otto_output":      {"approval_status": "rejected"},
                    "otto_feedback":    "리스크 과다",
                    "otto_retry_count": 1,
                }
            return {
                "otto_output": {"approval_status": "approved", "selected_policy": "conservative"},
                "portfolio":   state.get("portfolio") or {},
            }

        def pm_stub(state):
            pm_calls.append(1)
            return {"portfolio": {"equities": 0.4, "cash": 0.6}}

        result = self._run(
            dave_stub=lambda s: {"dave_output": {"risk_score": 0.3}},
            otto_stub=otto_stub,
            pm_stub=pm_stub,
        )

        assert len(otto_calls) == 2, f"Otto 2회 호출 기대, 실제: {len(otto_calls)}"
        assert len(pm_calls) == 2, f"PM 2회 호출 기대, 실제: {len(pm_calls)}"
        assert result["otto_output"]["approval_status"] == "approved"

    # ── 4. Otto retry 한도 초과 → END 탈출 ───────────────────────────────────

    def test_otto_rejected_exceeds_limit_exits_without_infinite_loop(self):
        """
        Otto가 계속 rejected 반환 시 retry_count > 2 에서 END 탈출.
        무한루프 없이 테스트가 완료되면 성공.
        """
        def otto_stub(state):
            current = state.get("otto_retry_count", 0)
            return {
                "otto_output":      {"approval_status": "rejected"},
                "otto_feedback":    "지속 거부",
                "otto_retry_count": current + 1,
            }

        result = self._run(
            dave_stub=lambda s: {"dave_output": {"risk_score": 0.3}},
            otto_stub=otto_stub,
        )

        # retry_count가 3 이상이면 END로 탈출한 것
        assert result.get("otto_retry_count", 0) >= 3
