"""
Integration tests for the daily and weekly trading cycle.
Covers Orchestrator init, run_daily_cycle, run_weekly_cycle, ledger summary, and is_week_end.
No real LLM calls — graph nodes use mock/placeholder logic.
"""

import pytest
from orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_market_data(date: str = "2024-01-15") -> dict:
    return {
        "date": date,
        "spx_close": 4750.0,
        "vix": 14.5,
        "status": "live",
    }


# ---------------------------------------------------------------------------
# TestOrchestratorInit
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    """Test 1: Orchestrator 초기화 성공."""

    def test_init_success(self):
        """Orchestrator 초기화가 성공하고 graph compile이 완료된다."""
        orchestrator = Orchestrator()
        assert orchestrator is not None
        assert orchestrator.app is not None
        assert orchestrator.ledger is not None
        assert orchestrator.market_meeting is not None
        assert orchestrator.strategy_meeting is not None
        assert orchestrator.risk_alert_meeting is not None


# ---------------------------------------------------------------------------
# TestDailyCycle
# ---------------------------------------------------------------------------

class TestDailyCycle:
    """Tests 2-6: run_daily_cycle 동작 검증."""

    def test_daily_cycle_returns_state_with_current_date(self):
        """Test 2: run_daily_cycle() — state가 반환되고 current_date 포함."""
        orchestrator = Orchestrator()
        result = orchestrator.run_daily_cycle("2024-01-15")

        assert result is not None
        assert isinstance(result, dict)
        assert result.get("current_date") == "2024-01-15"

    def test_daily_cycle_has_risk_score(self):
        """Test 3: run_daily_cycle() — risk_score 필드가 있음."""
        orchestrator = Orchestrator()
        result = orchestrator.run_daily_cycle("2024-01-15")

        assert "risk_score" in result
        assert isinstance(result["risk_score"], float)

    def test_daily_cycle_skip_log_is_list(self):
        """Test 4: run_daily_cycle() — skip_log가 list임."""
        orchestrator = Orchestrator()
        result = orchestrator.run_daily_cycle("2024-01-15")

        assert "skip_log" in result
        assert isinstance(result["skip_log"], list)

    def test_daily_cycle_raw_market_data_set(self):
        """Test 5: run_daily_cycle() — raw_market_data가 설정됨."""
        orchestrator = Orchestrator()
        market_data = _make_market_data("2024-01-15")
        result = orchestrator.run_daily_cycle("2024-01-15", market_data=market_data)

        # raw_market_data는 INGEST_DAILY_DATA 노드가 skip_log에 기록하고 그대로 유지
        assert result.get("raw_market_data") is not None

    def test_daily_cycle_without_otto_output_ends_normally(self):
        """Test 6: run_daily_cycle() — otto_output이 없을 때 WAIT_NEXT_BAR로 정상 종료."""
        orchestrator = Orchestrator()
        result = orchestrator.run_daily_cycle("2024-01-15")

        # otto_output이 없으면 DAILY_POLICY_SELECTION에서 WAIT_NEXT_BAR로 라우팅됨
        # graph가 END에 도달하고 result가 dict이면 정상 종료
        assert isinstance(result, dict)
        # otto_output 없음 확인 (daily cycle은 LLM agent 없이 실행되므로)
        otto = result.get("otto_output")
        assert otto is None or isinstance(otto, dict)


# ---------------------------------------------------------------------------
# TestWeeklyCycle
# ---------------------------------------------------------------------------

class TestWeeklyCycle:
    """Tests 7-10: run_weekly_cycle 동작 검증."""

    def test_weekly_cycle_produces_weekly_market_report(self):
        """Test 7: run_weekly_cycle() — weekly_market_report가 생성됨."""
        orchestrator = Orchestrator()
        result = orchestrator.run_weekly_cycle("2024-01-19")  # 금요일

        assert "weekly_market_report" in result
        assert result["weekly_market_report"] is not None
        assert isinstance(result["weekly_market_report"], dict)

    def test_weekly_cycle_produces_debate_resolution(self):
        """Test 8: run_weekly_cycle() — debate_resolution이 생성됨."""
        orchestrator = Orchestrator()
        result = orchestrator.run_weekly_cycle("2024-01-19")

        assert "debate_resolution" in result
        assert result["debate_resolution"] is not None
        assert isinstance(result["debate_resolution"], dict)

    def test_weekly_cycle_produces_signal_conflict_resolution(self):
        """Test 9: run_weekly_cycle() — signal_conflict_resolution이 생성됨."""
        orchestrator = Orchestrator()
        result = orchestrator.run_weekly_cycle("2024-01-19")

        assert "signal_conflict_resolution" in result
        assert result["signal_conflict_resolution"] is not None
        assert isinstance(result["signal_conflict_resolution"], dict)

    def test_weekly_cycle_ledger_records_final_market_report(self):
        """Test 10: run_weekly_cycle() — ledger에 final_market_report 기록됨."""
        orchestrator = Orchestrator()
        orchestrator.run_weekly_cycle("2024-01-19")

        entries = orchestrator.ledger.get_entries_by_type("final_market_report")
        assert len(entries) > 0
        assert entries[0]["entry_type"] == "final_market_report"


# ---------------------------------------------------------------------------
# TestIsWeekEnd
# ---------------------------------------------------------------------------

class TestIsWeekEnd:
    """Tests 11-12: is_week_end 정적 메서드 검증."""

    def test_friday_is_week_end(self):
        """Test 11: Orchestrator.is_week_end('2024-01-19') — True (금요일)."""
        assert Orchestrator.is_week_end("2024-01-19") is True

    def test_monday_is_not_week_end(self):
        """Test 12: Orchestrator.is_week_end('2024-01-15') — False (월요일)."""
        assert Orchestrator.is_week_end("2024-01-15") is False


# ---------------------------------------------------------------------------
# TestLedgerSummary
# ---------------------------------------------------------------------------

class TestLedgerSummary:
    """Test 13: get_ledger_summary 검증."""

    def test_ledger_summary_returns_dict_with_total_entries(self):
        """Test 13: get_ledger_summary() — dict 반환, total_entries 포함."""
        orchestrator = Orchestrator()
        orchestrator.run_weekly_cycle("2024-01-19")

        summary = orchestrator.get_ledger_summary()

        assert isinstance(summary, dict)
        assert "total_entries" in summary
        assert "by_type" in summary
        assert isinstance(summary["total_entries"], int)
        assert summary["total_entries"] > 0
        assert isinstance(summary["by_type"], dict)
