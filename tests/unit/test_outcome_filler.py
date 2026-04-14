"""tests/unit/test_outcome_filler.py — outcome_filler.py 단위 테스트 (API 호출 없음)."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from memory.outcome_filler import (
    compute_portfolio_r_real,
    fill_pending_outcomes,
    _update_strategy_memory,
)


# ─── 헬퍼 ───────────────────────────────────────────────────────────────────

def make_portfolio(
    decision_date: str,
    allocations: list = None,
    r_real=None,
    r_real_source=None,
) -> dict:
    """테스트용 portfolio.json 내용 생성."""
    allocs = allocations or [
        {"ticker": "AAPL", "weight": 0.3, "action": "BUY"},
        {"ticker": "NVDA", "weight": 0.3, "action": "BUY"},
    ]
    d = {
        "date": decision_date,
        "tickers": [a["ticker"] for a in allocs],
        "portfolio": {
            "allocations": allocs,
            "cash_pct": 0.4,
            "hedge_pct": 0.0,
        },
        "stock_results": [],
        "errors": [],
    }
    if r_real is not None:
        d["r_real"] = r_real
    if r_real_source is not None:
        d["r_real_source"] = r_real_source
    return d


def save_portfolio(tmp_path: Path, decision_date: str, data: dict) -> Path:
    p = tmp_path / decision_date / "portfolio.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False))
    return p


def make_mock_fetcher(return_map: dict):
    """fetch_forward_return 결과를 ticker별로 반환하는 mock fetcher."""
    fetcher = MagicMock()
    # get_ohlcv 호출을 return_map 기반으로 흉내 낸다.
    # 실제로는 compute_portfolio_r_real → fetch_forward_return → fetcher.get_ohlcv 호출
    # fetch_forward_return을 직접 patch 하는 방식 사용.
    return fetcher


# ─── test_skip_already_filled ─────────────────────────────────────────────

class TestSkipAlreadyFilled:
    def test_skip_already_filled(self, tmp_path, monkeypatch):
        """r_real이 이미 있으면 덮어쓰지 않는다."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)
        decision_date = "2024-01-01"
        data = make_portfolio(decision_date, r_real=0.05, r_real_source="polygon_weighted")
        path = save_portfolio(tmp_path, decision_date, data)

        run_date = "2024-01-15"  # +14일 → 평가 가능

        mock_fetcher = MagicMock()
        filled = fill_pending_outcomes(run_date, fetcher=mock_fetcher)

        assert decision_date not in filled

        # 파일 내용 그대로
        saved = json.loads(path.read_text())
        assert saved["r_real"] == 0.05


# ─── test_skip_future_eval_date ──────────────────────────────────────────

class TestSkipFutureEvalDate:
    def test_skip_too_recent(self, tmp_path, monkeypatch):
        """decision_date + 7 > run_date → T+7 미확정이므로 스킵."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)

        run_date_obj = date.fromisoformat("2024-01-10")
        # decision_date = run_date - 6일 → cutoff보다 최근 → 스킵
        decision_date = (run_date_obj - timedelta(days=6)).isoformat()
        data = make_portfolio(decision_date)
        save_portfolio(tmp_path, decision_date, data)

        mock_fetcher = MagicMock()
        filled = fill_pending_outcomes("2024-01-10", fetcher=mock_fetcher)

        assert decision_date not in filled

    def test_exactly_7_days_is_allowed(self, tmp_path, monkeypatch):
        """decision_date + 7 == run_date → 평가 허용."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)

        run_date_obj = date.fromisoformat("2024-01-10")
        decision_date = (run_date_obj - timedelta(days=7)).isoformat()
        data = make_portfolio(decision_date)
        save_portfolio(tmp_path, decision_date, data)

        # fetch_forward_return 패치 — 값 반환
        with patch(
            "memory.outcome_filler.compute_portfolio_r_real",
            return_value=0.03,
        ):
            mock_fetcher = MagicMock()
            filled = fill_pending_outcomes("2024-01-10", fetcher=mock_fetcher)

        assert decision_date in filled


# ─── test_skip_zero_weight_allocations ───────────────────────────────────

class TestSkipZeroWeightAllocations:
    def test_all_zero_weight_returns_none(self):
        """모든 weight가 0이면 None 반환."""
        allocations = [
            {"ticker": "AAPL", "weight": 0.0, "action": "BUY"},
            {"ticker": "NVDA", "weight": 0.0, "action": "BUY"},
        ]
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        assert result is None

    def test_zero_and_nonzero_uses_nonzero_only(self, monkeypatch):
        """weight > 0 인 종목만 사용."""
        allocations = [
            {"ticker": "AAPL", "weight": 0.0, "action": "BUY"},
            {"ticker": "NVDA", "weight": 0.5, "action": "BUY"},
        ]

        def mock_fetch(fetcher, ticker, execution_date, lookforward_days=10):
            if ticker == "NVDA":
                return 0.1
            return None

        monkeypatch.setattr("memory.outcome_filler.fetch_forward_return", mock_fetch)
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        # 0.5 * 0.1 / 0.5 = 0.1
        assert result == pytest.approx(0.1)


# ─── test_weighted_return_calculation ────────────────────────────────────

class TestWeightedReturnCalculation:
    def test_weighted_math(self, monkeypatch):
        """weight=0.3 AAPL→0.1, weight=0.2 NVDA→0.2 → (0.3*0.1 + 0.2*0.2) / 0.5 = 0.14"""
        allocations = [
            {"ticker": "AAPL", "weight": 0.3, "action": "BUY"},
            {"ticker": "NVDA", "weight": 0.2, "action": "BUY"},
        ]
        return_map = {"AAPL": 0.1, "NVDA": 0.2}

        def mock_fetch(fetcher, ticker, execution_date, lookforward_days=10):
            return return_map.get(ticker)

        monkeypatch.setattr("memory.outcome_filler.fetch_forward_return", mock_fetch)
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        # (0.3*0.1 + 0.2*0.2) / (0.3+0.2) = (0.03 + 0.04) / 0.5 = 0.14
        assert result == pytest.approx(0.14)

    def test_single_ticker(self, monkeypatch):
        """단일 종목."""
        allocations = [{"ticker": "SPY", "weight": 1.0, "action": "BUY"}]

        def mock_fetch(fetcher, ticker, execution_date, lookforward_days=10):
            return 0.05

        monkeypatch.setattr("memory.outcome_filler.fetch_forward_return", mock_fetch)
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        assert result == pytest.approx(0.05)


# ─── test_sell_allocations_skipped ───────────────────────────────────────

class TestSellAllocationsSkipped:
    def test_sell_skipped(self, monkeypatch):
        """action=SELL 인 종목은 계산에서 제외."""
        allocations = [
            {"ticker": "AAPL", "weight": 0.4, "action": "SELL"},
            {"ticker": "NVDA", "weight": 0.3, "action": "BUY"},
        ]

        def mock_fetch(fetcher, ticker, execution_date, lookforward_days=10):
            return_map = {"AAPL": 0.1, "NVDA": 0.2}
            return return_map.get(ticker)

        monkeypatch.setattr("memory.outcome_filler.fetch_forward_return", mock_fetch)
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        # AAPL(SELL) 제외 → NVDA만 → 0.3*0.2 / 0.3 = 0.2
        assert result == pytest.approx(0.2)

    def test_cash_ticker_skipped(self, monkeypatch):
        """ticker='CASH' 는 제외."""
        allocations = [
            {"ticker": "CASH", "weight": 0.5, "action": "HOLD"},
            {"ticker": "AAPL", "weight": 0.5, "action": "BUY"},
        ]

        def mock_fetch(fetcher, ticker, execution_date, lookforward_days=10):
            return 0.08

        monkeypatch.setattr("memory.outcome_filler.fetch_forward_return", mock_fetch)
        mock_fetcher = MagicMock()
        result = compute_portfolio_r_real(mock_fetcher, allocations, "2024-01-01")
        # CASH 제외, AAPL만 → 0.5*0.08 / 0.5 = 0.08
        assert result == pytest.approx(0.08)


# ─── test_returns_empty_when_no_pending ──────────────────────────────────

class TestReturnsEmptyWhenNoPending:
    def test_no_portfolio_files(self, tmp_path, monkeypatch):
        """portfolio.json 없으면 빈 dict 반환."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)
        mock_fetcher = MagicMock()
        result = fill_pending_outcomes("2024-01-15", fetcher=mock_fetcher)
        assert result == {}

    def test_results_dir_not_exists(self, tmp_path, monkeypatch):
        """RESULTS_DIR가 아예 없으면 빈 dict 반환."""
        non_existent = tmp_path / "nonexistent"
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", non_existent)
        mock_fetcher = MagicMock()
        result = fill_pending_outcomes("2024-01-15", fetcher=mock_fetcher)
        assert result == {}

    def test_all_already_filled(self, tmp_path, monkeypatch):
        """모두 r_real이 있으면 빈 dict."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)
        decision_date = "2024-01-01"
        data = make_portfolio(decision_date, r_real=0.02, r_real_source="polygon_weighted")
        save_portfolio(tmp_path, decision_date, data)

        mock_fetcher = MagicMock()
        result = fill_pending_outcomes("2024-01-15", fetcher=mock_fetcher)
        assert result == {}


# ─── test_fill_writes_back_to_file ───────────────────────────────────────

class TestFillWritesBackToFile:
    def test_writes_r_real_to_file(self, tmp_path, monkeypatch):
        """r_real 계산 성공 시 파일에 기록."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)

        decision_date = "2024-01-01"
        allocations = [{"ticker": "AAPL", "weight": 0.5, "action": "BUY"}]
        data = make_portfolio(decision_date, allocations=allocations)
        path = save_portfolio(tmp_path, decision_date, data)

        run_date = "2024-01-15"  # +14일

        with patch(
            "memory.outcome_filler.compute_portfolio_r_real",
            return_value=0.07,
        ):
            mock_fetcher = MagicMock()
            filled = fill_pending_outcomes(run_date, fetcher=mock_fetcher)

        assert decision_date in filled
        assert filled[decision_date] == pytest.approx(0.07)

        saved = json.loads(path.read_text())
        assert saved["r_real"] == pytest.approx(0.07)
        assert saved["r_real_source"] == "polygon_weighted"
        assert saved["r_real_eval_date"] == run_date

    def test_returns_only_newly_filled(self, tmp_path, monkeypatch):
        """이미 채워진 날짜는 반환값에서 제외."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)

        # 이미 채워진 날짜
        date1 = "2024-01-01"
        data1 = make_portfolio(date1, r_real=0.01, r_real_source="polygon_weighted")
        save_portfolio(tmp_path, date1, data1)

        # 새로 채울 날짜
        date2 = "2024-01-05"
        data2 = make_portfolio(date2)
        save_portfolio(tmp_path, date2, data2)

        run_date = "2024-01-20"

        with patch(
            "memory.outcome_filler.compute_portfolio_r_real",
            return_value=0.03,
        ):
            mock_fetcher = MagicMock()
            filled = fill_pending_outcomes(run_date, fetcher=mock_fetcher)

        assert date1 not in filled
        assert date2 in filled

    def test_compute_returns_none_skips_write(self, tmp_path, monkeypatch):
        """compute_portfolio_r_real이 None 반환하면 파일 수정 없음."""
        monkeypatch.setattr("memory.outcome_filler.RESULTS_DIR", tmp_path)

        decision_date = "2024-01-01"
        data = make_portfolio(decision_date)
        path = save_portfolio(tmp_path, decision_date, data)

        run_date = "2024-01-15"

        with patch(
            "memory.outcome_filler.compute_portfolio_r_real",
            return_value=None,
        ):
            mock_fetcher = MagicMock()
            filled = fill_pending_outcomes(run_date, fetcher=mock_fetcher)

        assert filled == {}
        saved = json.loads(path.read_text())
        assert "r_real" not in saved


# ─── test_update_strategy_memory ────────────────────────────────────────

class TestUpdateStrategyMemory:
    def _make_strategy_mem(self, tmp_path: Path, entries: dict) -> Path:
        p = tmp_path / "strategy_memory.json"
        p.write_text(json.dumps(entries, ensure_ascii=False))
        return p

    def test_positive_large_return_sets_reliability_1(self, tmp_path, monkeypatch):
        """r_real >= 0.02 → outcome_reliability=1.0."""
        mem_path = self._make_strategy_mem(tmp_path, {
            "AAPL_2024-01-01": {"ticker": "AAPL", "as_of": "2024-01-01", "r_real": None},
        })
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", mem_path)

        _update_strategy_memory("2024-01-01", 0.05, ["AAPL"])

        result = json.loads(mem_path.read_text())
        entry = result["AAPL_2024-01-01"]
        assert entry["r_real"] == pytest.approx(0.05)
        assert entry["outcome_reliability"] == 1.0
        assert entry["performance_score"] == pytest.approx(0.05)
        assert entry["r_real_source"] == "polygon_weighted"

    def test_small_positive_return_sets_reliability_085(self, tmp_path, monkeypatch):
        """0 <= r_real < 0.02 → outcome_reliability=0.85."""
        mem_path = self._make_strategy_mem(tmp_path, {
            "NVDA_2024-01-01": {"ticker": "NVDA", "as_of": "2024-01-01", "r_real": None},
        })
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", mem_path)

        _update_strategy_memory("2024-01-01", 0.01, ["NVDA"])

        result = json.loads(mem_path.read_text())
        assert result["NVDA_2024-01-01"]["outcome_reliability"] == pytest.approx(0.85)

    def test_negative_return_sets_reliability_065(self, tmp_path, monkeypatch):
        """r_real < 0 → outcome_reliability=0.65."""
        mem_path = self._make_strategy_mem(tmp_path, {
            "AAPL_2024-02-16": {"ticker": "AAPL", "as_of": "2024-02-16", "r_real": None},
        })
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", mem_path)

        _update_strategy_memory("2024-02-16", -0.04, ["AAPL"])

        result = json.loads(mem_path.read_text())
        assert result["AAPL_2024-02-16"]["outcome_reliability"] == pytest.approx(0.65)

    def test_updates_multiple_tickers(self, tmp_path, monkeypatch):
        """여러 티커 모두 업데이트."""
        mem_path = self._make_strategy_mem(tmp_path, {
            "AAPL_2024-01-05": {"ticker": "AAPL", "as_of": "2024-01-05", "r_real": None},
            "NVDA_2024-01-05": {"ticker": "NVDA", "as_of": "2024-01-05", "r_real": None},
        })
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", mem_path)

        _update_strategy_memory("2024-01-05", 0.03, ["AAPL", "NVDA"])

        result = json.loads(mem_path.read_text())
        assert result["AAPL_2024-01-05"]["r_real"] == pytest.approx(0.03)
        assert result["NVDA_2024-01-05"]["r_real"] == pytest.approx(0.03)

    def test_missing_key_silently_skipped(self, tmp_path, monkeypatch):
        """strategy_memory에 없는 키는 조용히 스킵."""
        mem_path = self._make_strategy_mem(tmp_path, {
            "AAPL_2024-01-01": {"ticker": "AAPL", "r_real": None},
        })
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", mem_path)

        # TSLA는 strategy_memory에 없음
        _update_strategy_memory("2024-01-01", 0.05, ["AAPL", "TSLA"])

        result = json.loads(mem_path.read_text())
        assert "TSLA_2024-01-01" not in result
        assert result["AAPL_2024-01-01"]["r_real"] == pytest.approx(0.05)

    def test_no_strategy_memory_file_does_nothing(self, tmp_path, monkeypatch):
        """strategy_memory.json이 없으면 오류 없이 종료."""
        non_existent = tmp_path / "strategy_memory.json"
        monkeypatch.setattr("memory.outcome_filler.STRATEGY_MEM_PATH", non_existent)

        # 오류 없이 종료되면 OK
        _update_strategy_memory("2024-01-01", 0.05, ["AAPL"])
