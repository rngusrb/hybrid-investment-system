"""
tests.unit.test_retrieval - Unit tests for Memory Layer, Retrieval, and Validity Scoring.

Phase 9: Memory Layer, Retrieval, Validity Scoring 구현 검증.
"""

import pytest

from memory.base_memory import BaseMemory
from memory.market_memory import MarketMemory
from memory.retrieval.validity_scorer import (
    compute_recency_decay,
    compute_regime_match,
    compute_data_quality,
    compute_outcome_reliability,
    compute_validity_score,
    DEFAULT_FLOOR,
)
from memory.retrieval.retriever import Retriever
from ledger.shared_ledger import SharedLedger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def market_mem():
    return MarketMemory()


@pytest.fixture
def populated_market_mem():
    mem = MarketMemory()
    # 과거 데이터
    mem.store(
        key="market_2024-01-10",
        value={
            "market_regime": "risk_on",
            "selected_policy": "long_equity",
            "outcome_horizon": 20,
            "rationale": "momentum confirmed",
        },
        date="2024-01-10",
        tags=["policy_decision"],
    )
    mem.store(
        key="market_2024-02-15",
        value={
            "market_regime": "risk_on",
            "selected_policy": "long_equity",
            "outcome_horizon": 20,
            "rationale": "trend continuation",
        },
        date="2024-02-15",
        tags=["policy_decision"],
    )
    # 미래 데이터 (as_of 기준으로 필터링 대상)
    mem.store(
        key="market_2099-01-01",
        value={"market_regime": "risk_on", "selected_policy": "long_equity"},
        date="2099-01-01",
        tags=[],
    )
    return mem


@pytest.fixture
def retriever(populated_market_mem):
    return Retriever(memory=populated_market_mem, floor=0.4, top_k=7)


@pytest.fixture
def ledger():
    return SharedLedger()


# ===========================================================================
# Validity Scorer Tests
# ===========================================================================

class TestValidityScorer:

    # 1. compute_recency_decay — age=0 → 1.0에 가까운 값
    def test_recency_decay_age_zero(self):
        result = compute_recency_decay("2024-06-01", "2024-06-01")
        assert abs(result - 1.0) < 1e-9, f"Expected ~1.0 for age=0, got {result}"

    # 2. compute_recency_decay — age >> halflife → 0에 가까운 값
    def test_recency_decay_old_date(self):
        # 1000일 경과 (halflife=90일) → exp(-ln2 * 1000/90) ≈ 0.0005
        result = compute_recency_decay("2021-01-01", "2023-10-01")
        assert result < 0.01, f"Expected close to 0 for very old date, got {result}"

    # 3. compute_regime_match — 동일 regime → 1.0
    def test_regime_match_identical(self):
        result = compute_regime_match("risk_on", "risk_on")
        assert result == 1.0

    # 4. compute_regime_match — 유사 regime (risk_on, fragile_rebound) → 0.6
    def test_regime_match_similar(self):
        result = compute_regime_match("risk_on", "fragile_rebound")
        assert result == 0.6

    # 5. compute_regime_match — 완전히 다른 regime → 0.2
    def test_regime_match_different(self):
        result = compute_regime_match("risk_on", "risk_off")
        assert result == 0.2

    # 6. compute_data_quality — 필수+optional 필드 모두 있으면 높은 점수
    def test_data_quality_full_fields(self):
        case = {
            "date": "2024-01-01",
            "value": {"foo": "bar"},
            "regime": "risk_on",
            "outcome": 0.05,
            "tags": ["policy_decision"],
        }
        result = compute_data_quality(case)
        # base=0.5, bonus=0.5 → 1.0
        assert result == 1.0, f"Expected 1.0, got {result}"

    # 7. compute_data_quality — 필수 필드 누락 → 0.1
    def test_data_quality_missing_required(self):
        case = {"regime": "risk_on"}  # date, value 모두 없음
        result = compute_data_quality(case)
        assert result == 0.1, f"Expected 0.1, got {result}"

    # 8. compute_outcome_reliability — outcome 없음 → 0.3
    def test_outcome_reliability_no_outcome(self):
        case = {"date": "2024-01-01", "value": {}}
        result = compute_outcome_reliability(case)
        assert result == 0.3, f"Expected 0.3, got {result}"

    # 9. compute_outcome_reliability — horizon_closed=True → 1.0
    def test_outcome_reliability_horizon_closed(self):
        case = {"date": "2024-01-01", "value": {}, "outcome": 0.08, "horizon_closed": True}
        result = compute_outcome_reliability(case)
        assert result == 1.0, f"Expected 1.0, got {result}"

    # 10. compute_validity_score — 모든 factor 높으면 floor 이상 score 반환
    def test_validity_score_high_factors(self):
        query = {"market_regime": "risk_on", "selected_policy": "long_equity"}
        case = {
            "date": "2024-06-01",  # 최근 (recency~1.0)
            "value": {"market_regime": "risk_on", "selected_policy": "long_equity"},
            "regime": "risk_on",
            "outcome": 0.05,
            "horizon_closed": True,
            "tags": ["policy_decision"],
        }
        score = compute_validity_score(
            query=query,
            case=case,
            as_of="2024-06-01",
            current_regime="risk_on",
            floor=0.0,  # floor=0 으로 폐기 없이 확인
        )
        assert score is not None
        assert score > 0.0

    # 11. compute_validity_score — recency 0에 가까우면 → None (폐기)
    def test_validity_score_old_case_discarded(self):
        query = {"market_regime": "risk_on"}
        case = {
            "date": "2000-01-01",  # 매우 오래된 날짜
            "value": {"market_regime": "risk_on"},
            "regime": "risk_on",
            "outcome": 0.05,
            "horizon_closed": True,
            "tags": ["policy_decision"],
        }
        score = compute_validity_score(
            query=query,
            case=case,
            as_of="2024-06-01",
            current_regime="risk_on",
            floor=DEFAULT_FLOOR,
        )
        assert score is None, f"Expected None for very old case, got {score}"

    # 12. compute_validity_score — floor 이하 → None 반환
    def test_validity_score_below_floor_returns_none(self):
        query = {"market_regime": "risk_on"}
        case = {
            "date": "2024-06-01",
            "value": {},  # 비어있어 sim=0
            "regime": "risk_off",  # 다른 regime
            "tags": [],
        }
        score = compute_validity_score(
            query=query,
            case=case,
            as_of="2024-06-01",
            current_regime="risk_on",
            floor=DEFAULT_FLOOR,
        )
        # sim=0 이므로 score=0 → floor(0.4) 이하 → None
        assert score is None


# ===========================================================================
# Retriever Tests
# ===========================================================================

class TestRetriever:

    # 13. retrieve() — as_of 이후 데이터 포함 안 됨 (timestamp guard)
    def test_timestamp_guard(self, populated_market_mem):
        retriever = Retriever(memory=populated_market_mem, floor=0.0, top_k=10)
        results = retriever.retrieve(
            query={"market_regime": "risk_on"},
            as_of="2024-06-01",
            current_regime="risk_on",
        )
        case_dates = [r["case_date"] for r in results]
        assert "2099-01-01" not in case_dates, "Future data must not appear in results"

    # 14. retrieve() — validity score floor 이하 case 제외됨
    def test_floor_filtering(self, populated_market_mem):
        # floor=0.99 (매우 높은 floor) → 대부분 폐기
        retriever = Retriever(memory=populated_market_mem, floor=0.99, top_k=10)
        results = retriever.retrieve(
            query={"market_regime": "risk_on"},
            as_of="2024-06-01",
            current_regime="risk_on",
        )
        # 모든 결과는 validity_score >= 0.99 이어야 함
        for r in results:
            assert r["validity_score"] >= 0.99

    # 15. retrieve() — top_k 개수 제한 준수
    def test_top_k_limit(self, populated_market_mem):
        # memory에 데이터 2개 있고 top_k=1 요청
        retriever = Retriever(memory=populated_market_mem, floor=0.0, top_k=10)
        results = retriever.retrieve(
            query={"market_regime": "risk_on", "selected_policy": "long_equity"},
            as_of="2024-06-01",
            current_regime="risk_on",
            top_k=1,
        )
        assert len(results) <= 1

    # 16. retrieve() — 빈 memory → 빈 리스트 반환
    def test_empty_memory_returns_empty_list(self):
        empty_mem = MarketMemory()
        retriever = Retriever(memory=empty_mem, floor=0.0, top_k=7)
        results = retriever.retrieve(
            query={"market_regime": "risk_on"},
            as_of="2024-06-01",
            current_regime="risk_on",
        )
        assert results == []

    # 17. _to_case_summary() — validity_score 포함, 구조화된 형식 확인
    def test_to_case_summary_structure(self, retriever):
        case = {
            "date": "2024-01-10",
            "value": {
                "market_regime": "risk_on",
                "selected_policy": "long_equity",
                "outcome_horizon": 20,
                "rationale": "test rationale",
            },
            "tags": ["policy_decision"],
        }
        summary = retriever._to_case_summary(case, validity_score=0.75, as_of="2024-06-01")
        assert "validity_score" in summary
        assert summary["validity_score"] == 0.75
        assert "case_date" in summary
        assert summary["case_date"] == "2024-01-10"
        assert "as_of" in summary
        assert "regime" in summary
        assert "tags" in summary
        # raw text 전문이 아닌 구조화된 형식 확인
        assert "value" not in summary  # raw value dict가 그대로 노출되면 안 됨


# ===========================================================================
# Memory Tests
# ===========================================================================

class TestMarketMemory:

    # 18. store() + retrieve() — 저장 후 조회
    def test_store_and_retrieve(self, market_mem):
        market_mem.store(
            key="test_key",
            value={"market_regime": "mixed", "close": 100},
            date="2024-03-01",
            tags=["daily"],
        )
        results = market_mem.retrieve(query={}, as_of="2024-12-31")
        assert len(results) == 1
        assert results[0]["date"] == "2024-03-01"

    # 19. retrieve() — as_of 이전 데이터만 반환
    def test_retrieve_only_past_data(self, market_mem):
        market_mem.store("k1", {"x": 1}, date="2024-01-01")
        market_mem.store("k2", {"x": 2}, date="2024-06-01")
        market_mem.store("k3", {"x": 3}, date="2025-01-01")  # 미래

        results = market_mem.retrieve(query={}, as_of="2024-06-01")
        dates = [r["date"] for r in results]
        assert "2025-01-01" not in dates
        assert "2024-01-01" in dates
        assert "2024-06-01" in dates

    # 20. _enforce_point_in_time() — 미래 날짜 False
    def test_enforce_point_in_time_future_returns_false(self, market_mem):
        result = market_mem._enforce_point_in_time("2099-12-31", "2024-06-01")
        assert result is False

    def test_enforce_point_in_time_past_returns_true(self, market_mem):
        result = market_mem._enforce_point_in_time("2020-01-01", "2024-06-01")
        assert result is True

    def test_enforce_point_in_time_same_date_returns_true(self, market_mem):
        result = market_mem._enforce_point_in_time("2024-06-01", "2024-06-01")
        assert result is True


# ===========================================================================
# Shared Ledger Tests
# ===========================================================================

class TestSharedLedger:

    # 21. record() — 허용 타입 저장 성공
    def test_record_allowed_type_succeeds(self, ledger):
        ledger.record(
            entry_type="final_market_report",
            content={"summary": "Bullish week"},
            date="2024-06-01",
            agent="emily",
        )
        entries = ledger.get_all()
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "final_market_report"

    # 22. record() — FORBIDDEN 타입 → ValueError
    def test_record_forbidden_type_raises(self, ledger):
        with pytest.raises(ValueError, match="raw_chain_of_thought"):
            ledger.record(
                entry_type="raw_chain_of_thought",
                content={"thought": "step 1: ..."},
                date="2024-06-01",
            )

    # 23. record() — 알 수 없는 타입 → ValueError
    def test_record_unknown_type_raises(self, ledger):
        with pytest.raises(ValueError, match="unknown_type_xyz"):
            ledger.record(
                entry_type="unknown_type_xyz",
                content={"data": "something"},
                date="2024-06-01",
            )

    # 24. get_entries_by_type() — 필터링 확인
    def test_get_entries_by_type_filters_correctly(self, ledger):
        ledger.record("final_market_report", {"r": 1}, date="2024-01-01", agent="emily")
        ledger.record("final_market_report", {"r": 2}, date="2024-01-02", agent="emily")
        ledger.record("execution_plan", {"plan": "buy"}, date="2024-01-01", agent="otto")

        reports = ledger.get_entries_by_type("final_market_report")
        assert len(reports) == 2
        plans = ledger.get_entries_by_type("execution_plan")
        assert len(plans) == 1

    # 25. get_latest() — 최신 entry 반환
    def test_get_latest_returns_last_entry(self, ledger):
        ledger.record("final_market_report", {"r": 1}, date="2024-01-01")
        ledger.record("final_market_report", {"r": 2}, date="2024-01-02")

        latest = ledger.get_latest("final_market_report")
        assert latest is not None
        assert latest["content"]["r"] == 2

    def test_get_latest_empty_returns_none(self, ledger):
        result = ledger.get_latest("final_market_report")
        assert result is None
