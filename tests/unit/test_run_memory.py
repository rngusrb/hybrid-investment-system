"""tests/unit/test_run_memory.py — run_memory.py 단위 테스트 (API 호출 없음)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from memory.run_memory import (
    find_prev_dates,
    load_result,
    build_context,
    format_context_for_prompt,
    load_prev_context,
    get_context_prompt,
)


# ─── fixture ─────────────────────────────────────────────────────────────────

def make_result(run_date: str, tickers: list[str],
                actions: dict = None, risk_levels: dict = None) -> dict:
    """테스트용 결과 dict 생성."""
    actions     = actions or {t: "HOLD" for t in tickers}
    risk_levels = risk_levels or {t: "medium" for t in tickers}

    stock_results = []
    for t in tickers:
        stock_results.append({
            "ticker": t,
            "current_price": 100.0,
            "trader":        {"action": actions.get(t, "HOLD"), "confidence": 0.7},
            "risk_manager":  {
                "final_action":          actions.get(t, "HOLD"),
                "risk_level":            risk_levels.get(t, "medium"),
                "action_changed":        False,
                "cash_reserve_pct":      0.1,
                "risk_flags":            [],
                "final_position_size_pct": 0.3,
            },
            "researcher":    {"consensus": "HOLD", "conviction": 0.6},
        })

    allocs = [{"ticker": t, "action": actions.get(t, "HOLD"), "weight": 0.3} for t in tickers]
    return {
        "date":          run_date,
        "tickers":       tickers,
        "stock_results": stock_results,
        "portfolio": {
            "allocations":        allocs,
            "total_equity_pct":   0.6,
            "cash_pct":           0.3,
            "hedge_pct":          0.1,
            "portfolio_risk_level": "medium",
            "market_outlook":     "cautiously optimistic",
        },
        "errors":   [],
        "prev_date": None,
    }


def save_fake_result(tmp_path: Path, run_date: str, data: dict):
    p = tmp_path / run_date / "portfolio.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


# ─── find_prev_dates ─────────────────────────────────────────────────────────

class TestFindPrevDates:
    def test_returns_prev_only(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            save_fake_result(tmp_path, d, {"date": d})
        prev = find_prev_dates("2024-01-19", n=5)
        assert "2024-01-19" not in prev   # current_date 제외
        assert "2024-01-12" in prev
        assert "2024-01-05" in prev

    def test_sorted_newest_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            save_fake_result(tmp_path, d, {"date": d})
        prev = find_prev_dates("2024-01-26", n=5)
        assert prev[0] == "2024-01-19"
        assert prev[1] == "2024-01-12"

    def test_respects_n_limit(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        for d in ["2024-01-05", "2024-01-12", "2024-01-19"]:
            save_fake_result(tmp_path, d, {"date": d})
        prev = find_prev_dates("2024-01-26", n=2)
        assert len(prev) == 2

    def test_no_results_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        assert find_prev_dates("2024-01-05") == []

    def test_point_in_time_safe(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        save_fake_result(tmp_path, "2024-01-20", {"date": "2024-01-20"})
        prev = find_prev_dates("2024-01-19", n=5)
        assert "2024-01-20" not in prev   # 미래 데이터 제외


# ─── build_context ────────────────────────────────────────────────────────────

class TestBuildContext:
    def test_empty_returns_empty(self):
        assert build_context([]) == {}

    def test_basic_fields(self):
        r = make_result("2024-01-12", ["AAPL", "NVDA"],
                        actions={"AAPL": "BUY", "NVDA": "HOLD"})
        ctx = build_context([r])
        assert ctx["prev_date"] == "2024-01-12"
        assert ctx["prev_cash_pct"] == pytest.approx(0.3)
        assert ctx["prev_hedge_pct"] == pytest.approx(0.1)
        assert ctx["prev_risk_level"] == "medium"

    def test_ticker_signals(self):
        r = make_result("2024-01-12", ["AAPL"],
                        actions={"AAPL": "BUY"},
                        risk_levels={"AAPL": "high"})
        ctx = build_context([r])
        sig = ctx["ticker_signals"]["AAPL"]
        assert sig["action"] == "BUY"
        assert sig["risk_level"] == "high"

    def test_consecutive_streak_1(self):
        r = make_result("2024-01-12", ["AAPL"], actions={"AAPL": "BUY"})
        ctx = build_context([r])
        assert ctx["consecutive"]["AAPL"] == 1

    def test_consecutive_streak_2(self):
        r1 = make_result("2024-01-05", ["AAPL"], actions={"AAPL": "BUY"})
        r2 = make_result("2024-01-12", ["AAPL"], actions={"AAPL": "BUY"})
        ctx = build_context([r2, r1])  # 최신 → 과거 순
        assert ctx["consecutive"]["AAPL"] == 2

    def test_consecutive_resets_on_change(self):
        r1 = make_result("2024-01-05", ["AAPL"], actions={"AAPL": "HOLD"})
        r2 = make_result("2024-01-12", ["AAPL"], actions={"AAPL": "BUY"})
        ctx = build_context([r2, r1])
        assert ctx["consecutive"]["AAPL"] == 1

    def test_action_changed_flag(self):
        r = make_result("2024-01-12", ["AAPL"])
        r["stock_results"][0]["risk_manager"]["action_changed"] = True
        ctx = build_context([r])
        assert ctx["ticker_signals"]["AAPL"]["action_changed"] is True

    def test_risk_flags_extracted(self):
        r = make_result("2024-01-12", ["AAPL"])
        r["stock_results"][0]["risk_manager"]["risk_flags"] = ["high_volatility"]
        ctx = build_context([r])
        assert "high_volatility" in ctx["ticker_signals"]["AAPL"]["risk_flags"]


# ─── format_context_for_prompt ───────────────────────────────────────────────

class TestFormatContextForPrompt:
    def test_empty_ctx_returns_empty(self):
        assert format_context_for_prompt({}) == ""

    def test_contains_prev_date(self):
        r = make_result("2024-01-12", ["AAPL"])
        ctx = build_context([r])
        text = format_context_for_prompt(ctx)
        assert "2024-01-12" in text

    def test_contains_tickers(self):
        r = make_result("2024-01-12", ["AAPL", "NVDA"])
        ctx = build_context([r])
        text = format_context_for_prompt(ctx)
        assert "AAPL" in text
        assert "NVDA" in text

    def test_streak_shown_when_gt1(self):
        r1 = make_result("2024-01-05", ["AAPL"], actions={"AAPL": "BUY"})
        r2 = make_result("2024-01-12", ["AAPL"], actions={"AAPL": "BUY"})
        ctx = build_context([r2, r1])
        text = format_context_for_prompt(ctx)
        assert "2주 연속" in text

    def test_risk_flag_shown(self):
        r = make_result("2024-01-12", ["AAPL"])
        r["stock_results"][0]["risk_manager"]["risk_flags"] = ["high_volatility"]
        ctx = build_context([r])
        text = format_context_for_prompt(ctx)
        assert "high_volatility" in text

    def test_action_changed_warning(self):
        r = make_result("2024-01-12", ["AAPL"])
        r["stock_results"][0]["risk_manager"]["action_changed"] = True
        ctx = build_context([r])
        text = format_context_for_prompt(ctx)
        assert "변경" in text

    def test_has_start_end_markers(self):
        r = make_result("2024-01-12", ["AAPL"])
        ctx = build_context([r])
        text = format_context_for_prompt(ctx)
        assert "MEMORY CONTEXT" in text
        assert "END MEMORY CONTEXT" in text


# ─── load_prev_context / get_context_prompt (통합) ───────────────────────────

class TestLoadPrevContext:
    def test_no_prev_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        ctx = load_prev_context("2024-01-05")
        assert ctx == {}

    def test_loads_from_results_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        r = make_result("2024-01-05", ["AAPL"])
        save_fake_result(tmp_path, "2024-01-05", r)
        ctx = load_prev_context("2024-01-12")
        assert ctx["prev_date"] == "2024-01-05"

    def test_get_context_prompt_returns_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        r = make_result("2024-01-05", ["AAPL"])
        save_fake_result(tmp_path, "2024-01-05", r)
        prompt = get_context_prompt("2024-01-12")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_context_prompt_empty_when_no_prev(self, tmp_path, monkeypatch):
        monkeypatch.setattr("memory.run_memory.RESULTS_DIR", tmp_path)
        prompt = get_context_prompt("2024-01-05")
        assert prompt == ""


# ─── build_context validity scoring ──────────────────────────────────────────

class TestBuildContextValidityScoring:
    """build_context()에 as_of + current_regime 전달 시 validity scoring 적용 검증."""

    def test_as_of_none_uses_legacy_behavior(self):
        """as_of=None이면 기존 동작과 동일."""
        r = make_result("2024-01-12", ["AAPL"], actions={"AAPL": "BUY"})
        ctx_legacy = build_context([r], lookback=3)
        ctx_no_asof = build_context([r], lookback=3, as_of=None, current_regime="mixed")
        assert ctx_legacy == ctx_no_asof

    def test_validity_scoring_filters_old_results(self):
        """오래된 결과(recency decay 매우 낮음)는 validity scoring으로 필터링됨."""
        # 최근 결과 (2024-06-01 기준 최근) + r_real로 outcome_reliability 확보
        r_recent = make_result("2024-05-25", ["AAPL"], actions={"AAPL": "BUY"})
        r_recent["portfolio"]["market_outlook"] = "risk_on"
        r_recent["r_real"] = 0.03
        r_recent["r_real_source"] = "polygon_weighted"

        # 매우 오래된 결과 (recency decay → ~0) + r_real 있어도 recency가 0
        r_old = make_result("2020-01-01", ["NVDA"], actions={"NVDA": "HOLD"})
        r_old["portfolio"]["market_outlook"] = "risk_on"
        r_old["r_real"] = 0.05
        r_old["r_real_source"] = "polygon_weighted"

        ctx = build_context(
            [r_old, r_recent], lookback=1,
            as_of="2024-06-01", current_regime="risk_on",
        )
        # lookback=1이므로 1개만 반환, 최근 결과가 선택되어야 함
        assert ctx["prev_date"] == "2024-05-25"

    def test_validity_scoring_prefers_matching_regime(self):
        """동일 regime 결과가 validity score 높아서 우선 선택됨."""
        r_match = make_result("2024-05-20", ["AAPL"], actions={"AAPL": "BUY"})
        r_match["portfolio"]["market_outlook"] = "risk_on"
        r_match["r_real"] = 0.03
        r_match["r_real_source"] = "polygon_weighted"

        r_mismatch = make_result("2024-05-25", ["NVDA"], actions={"NVDA": "HOLD"})
        r_mismatch["portfolio"]["market_outlook"] = "risk_off"
        r_mismatch["r_real"] = 0.03
        r_mismatch["r_real_source"] = "polygon_weighted"

        ctx = build_context(
            [r_mismatch, r_match], lookback=1,
            as_of="2024-06-01", current_regime="risk_on",
        )
        # regime 매치가 높아서 r_match 선택 (날짜는 r_mismatch가 더 최근이지만)
        assert ctx["prev_date"] == "2024-05-20"

    def test_all_below_threshold_falls_back(self):
        """모든 후보가 threshold 미만이면 기존 방식 fallback."""
        # 매우 오래된 결과들만 (validity score 거의 0)
        r1 = make_result("2015-01-01", ["AAPL"], actions={"AAPL": "BUY"})
        r2 = make_result("2015-02-01", ["NVDA"], actions={"NVDA": "HOLD"})

        ctx = build_context(
            [r1, r2], lookback=1,
            as_of="2024-06-01", current_regime="risk_on",
        )
        # fallback이므로 결과가 반환되어야 함 (빈 dict 아님)
        assert ctx != {}
        assert "prev_date" in ctx

    def test_return_format_unchanged(self):
        """validity scoring 적용해도 반환 포맷은 기존과 동일."""
        r = make_result("2024-05-25", ["AAPL"], actions={"AAPL": "BUY"})
        r["portfolio"]["market_outlook"] = "risk_on"

        ctx = build_context(
            [r], lookback=3,
            as_of="2024-06-01", current_regime="risk_on",
        )
        # 기존 반환 포맷의 필수 키 확인
        expected_keys = {
            "prev_date", "prev_allocation", "prev_cash_pct", "prev_hedge_pct",
            "prev_risk_level", "prev_outlook", "ticker_signals", "consecutive",
            "prev_errors", "r_real", "r_real_source",
        }
        assert expected_keys.issubset(set(ctx.keys()))

    def test_verified_result_scores_higher(self):
        """r_real 있는 verified 결과가 validity score에서 유리."""
        r_verified = make_result("2024-05-20", ["AAPL"], actions={"AAPL": "BUY"})
        r_verified["portfolio"]["market_outlook"] = "risk_on"
        r_verified["r_real"] = 0.03
        r_verified["r_real_source"] = "polygon_weighted"

        r_unverified = make_result("2024-05-22", ["NVDA"], actions={"NVDA": "HOLD"})
        r_unverified["portfolio"]["market_outlook"] = "risk_on"

        ctx = build_context(
            [r_unverified, r_verified], lookback=1,
            as_of="2024-06-01", current_regime="risk_on",
        )
        # verified 결과가 outcome reliability 높아서 선택됨
        assert ctx["prev_date"] == "2024-05-20"
