"""tests/unit/test_run_loop.py — run_loop.py 단위 테스트 (API 호출 없음)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from scripts.run_loop import (
    generate_dates,
    save_result,
    load_result,
    result_path,
    list_saved_dates,
    print_cycle_summary,
    print_loop_summary,
)


# ─── generate_dates ──────────────────────────────────────────────────────────

class TestGenerateDates:
    def test_weekly_basic(self):
        dates = generate_dates("2024-01-01", "2024-01-31", freq="weekly")
        # 2024-01-05(금), 2024-01-12(금), 2024-01-19(금), 2024-01-26(금)
        assert dates == ["2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26"]

    def test_weekly_all_fridays(self):
        from datetime import date
        dates = generate_dates("2024-01-01", "2024-06-30", freq="weekly")
        for d in dates:
            assert date.fromisoformat(d).weekday() == 4, f"{d}는 금요일이어야 함"

    def test_weekly_start_on_friday(self):
        dates = generate_dates("2024-01-05", "2024-01-19", freq="weekly")
        assert dates[0] == "2024-01-05"

    def test_daily_excludes_weekends(self):
        from datetime import date
        dates = generate_dates("2024-01-01", "2024-01-07", freq="daily")
        # 2024-01-01(월)~01-05(금), 01-06(토)/01-07(일) 제외
        for d in dates:
            assert date.fromisoformat(d).weekday() < 5, f"{d}는 주말이면 안 됨"
        assert "2024-01-01" in dates
        assert "2024-01-05" in dates
        assert "2024-01-06" not in dates
        assert "2024-01-07" not in dates

    def test_weekly_count(self):
        dates = generate_dates("2024-01-01", "2024-03-31", freq="weekly")
        assert len(dates) == 13  # 1월~3월 약 13주

    def test_daily_count(self):
        dates = generate_dates("2024-01-01", "2024-01-05", freq="daily")
        assert len(dates) == 5  # 월~금

    def test_empty_range(self):
        # 범위가 너무 좁아 해당 요일 없을 때
        dates = generate_dates("2024-01-06", "2024-01-06", freq="weekly")  # 토요일
        assert dates == []

    def test_invalid_freq(self):
        with pytest.raises(ValueError):
            generate_dates("2024-01-01", "2024-01-31", freq="monthly")

    def test_dates_sorted_ascending(self):
        dates = generate_dates("2024-01-01", "2024-06-30", freq="weekly")
        assert dates == sorted(dates)

    def test_end_inclusive(self):
        # 종료일이 금요일인 경우 포함되어야 함
        dates = generate_dates("2024-01-01", "2024-01-05", freq="weekly")
        assert "2024-01-05" in dates


# ─── save_result / load_result ───────────────────────────────────────────────

class TestSaveLoadResult:
    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data = {"date": "2024-01-05", "tickers": ["AAPL"], "portfolio": {}, "errors": []}
        path = save_result("2024-01-05", data)
        assert path.exists()

    def test_load_returns_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data = {"date": "2024-01-05", "tickers": ["AAPL"], "portfolio": {"cash_pct": 0.3}}
        save_result("2024-01-05", data)
        loaded = load_result("2024-01-05")
        assert loaded["date"] == "2024-01-05"
        assert loaded["portfolio"]["cash_pct"] == 0.3

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        assert load_result("9999-12-31") is None

    def test_save_overwrites(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        save_result("2024-01-05", {"v": 1})
        save_result("2024-01-05", {"v": 2})
        assert load_result("2024-01-05")["v"] == 2

    def test_json_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data = {
            "date": "2024-01-05",
            "tickers": ["AAPL", "NVDA"],
            "stock_results": [{"ticker": "AAPL", "current_price": 185.5}],
            "portfolio": {"allocations": [{"ticker": "AAPL", "weight": 0.4}]},
            "errors": [],
            "prev_date": None,
        }
        save_result("2024-01-05", data)
        loaded = load_result("2024-01-05")
        assert loaded == data

    def test_result_path_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        path = result_path("2024-01-05")
        assert path.parent.name == "2024-01-05"
        assert path.name == "portfolio.json"

    def test_unicode_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data = {"note": "한글 데이터 테스트"}
        save_result("2024-01-05", data)
        loaded = load_result("2024-01-05")
        assert loaded["note"] == "한글 데이터 테스트"


# ─── list_saved_dates ────────────────────────────────────────────────────────

class TestListSavedDates:
    def test_empty_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        assert list_saved_dates() == []

    def test_returns_sorted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        for d in ["2024-02-02", "2024-01-05", "2024-03-01"]:
            save_result(d, {"date": d})
        saved = list_saved_dates()
        assert saved == ["2024-01-05", "2024-02-02", "2024-03-01"]

    def test_ignores_dirs_without_portfolio_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        # portfolio.json 없는 디렉토리
        (tmp_path / "2024-01-05").mkdir()
        assert list_saved_dates() == []

    def test_no_results_dir(self, tmp_path, monkeypatch):
        nonexistent = tmp_path / "no_such_dir"
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", nonexistent)
        assert list_saved_dates() == []


# ─── 결과 구조 검증 ─────────────────────────────────────────────────────────

class TestResultSchema:
    def test_required_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data = {
            "date": "2024-01-05",
            "tickers": ["AAPL"],
            "stock_results": [],
            "portfolio": {},
            "errors": [],
            "prev_date": None,
        }
        save_result("2024-01-05", data)
        loaded = load_result("2024-01-05")
        for field in ["date", "tickers", "stock_results", "portfolio", "errors", "prev_date"]:
            assert field in loaded, f"필드 누락: {field}"

    def test_prev_date_chaining(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.run_loop.RESULTS_DIR", tmp_path)
        data1 = {"date": "2024-01-05", "tickers": ["AAPL"],
                 "stock_results": [], "portfolio": {}, "errors": [], "prev_date": None}
        data2 = {"date": "2024-01-12", "tickers": ["AAPL"],
                 "stock_results": [], "portfolio": {}, "errors": [], "prev_date": "2024-01-05"}
        save_result("2024-01-05", data1)
        save_result("2024-01-12", data2)
        assert load_result("2024-01-12")["prev_date"] == "2024-01-05"


# ─── 출력 함수 (smoke test) ──────────────────────────────────────────────────

class TestPrintFunctions:
    def test_print_cycle_summary_no_error(self, capsys):
        result = {
            "portfolio": {
                "allocations": [{"ticker": "AAPL", "action": "BUY", "weight": 0.4}],
                "cash_pct": 0.5,
                "hedge_pct": 0.1,
            },
            "errors": [],
        }
        print_cycle_summary("2024-01-05", result, elapsed=42.0)
        out = capsys.readouterr().out
        assert "2024-01-05" in out
        assert "AAPL" in out

    def test_print_cycle_summary_with_errors(self, capsys):
        result = {
            "portfolio": {},
            "errors": [{"ticker": "AAPL", "error": "timeout"}],
        }
        print_cycle_summary("2024-01-05", result, elapsed=5.0)
        out = capsys.readouterr().out
        assert "오류" in out

    def test_print_loop_summary(self, capsys):
        print_loop_summary(
            dates=["2024-01-05", "2024-01-12"],
            successes=["2024-01-05"],
            failures=["2024-01-12"],
            skipped=[],
        )
        out = capsys.readouterr().out
        assert "성공" in out
        assert "실패" in out
