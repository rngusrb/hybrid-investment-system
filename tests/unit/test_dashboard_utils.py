"""tests/unit/test_dashboard_utils.py — dashboard/utils 단위 테스트."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dashboard.utils.formatters as fmts
from dashboard.utils.formatters import (
    action_icon, risk_icon, pct_str, price_str,
    agent_flow_steps, extract_articles_table,
    extract_ohlcv_table, build_allocation_rows,
    build_pipeline_trace,
    list_bc_dates, load_bc_result, load_eval_results,
    format_approval_badge, format_reliability_rows,
)


class TestFormatters:
    def test_action_icon_buy(self):
        assert action_icon("BUY") == "🟢 BUY"

    def test_action_icon_sell(self):
        assert action_icon("SELL") == "🔴 SELL"

    def test_action_icon_hold(self):
        assert action_icon("HOLD") == "🟡 HOLD"

    def test_action_icon_unknown(self):
        assert "⚪" in action_icon("UNKNOWN")

    def test_risk_icon_levels(self):
        assert risk_icon("low") == "🟢"
        assert risk_icon("moderate") == "🟡"
        assert risk_icon("high") == "🔴"
        assert risk_icon("extreme") == "🔴"

    def test_pct_str(self):
        assert pct_str(0.08) == "8.0%"
        assert pct_str(0.0) == "0.0%"
        assert pct_str(1.0) == "100.0%"
        assert pct_str(0.333) == "33.3%"

    def test_price_str(self):
        assert price_str(185.92) == "$185.92"
        assert price_str(None) == "N/A"
        assert price_str(1000.0) == "$1,000.00"

    def test_price_str_none(self):
        assert price_str(None) == "N/A"


class TestAgentFlowSteps:
    def test_returns_list(self):
        steps = agent_flow_steps()
        assert isinstance(steps, list)

    def test_has_required_agents(self):
        steps = agent_flow_steps()
        ids = [s["id"] for s in steps]
        for required in ["data", "fundamental", "sentiment", "news",
                         "technical", "researcher", "trader", "risk", "portfolio"]:
            assert required in ids

    def test_each_step_has_label_and_desc(self):
        for step in agent_flow_steps():
            assert "label" in step
            assert "desc" in step
            assert len(step["label"]) > 0
            assert len(step["desc"]) > 0


class TestExtractArticlesTable:
    def _make_article(self, title, date, pub_name):
        return {
            "title": title,
            "published_utc": date + "T00:00:00Z",
            "publisher": {"name": pub_name},
            "article_url": "https://example.com",
        }

    def test_basic(self):
        arts = [self._make_article("Apple rises", "2024-01-15", "Reuters")]
        rows = extract_articles_table(arts)
        assert len(rows) == 1
        assert rows[0]["날짜"] == "2024-01-15"
        assert rows[0]["제목"] == "Apple rises"
        assert rows[0]["출처"] == "Reuters"

    def test_empty(self):
        assert extract_articles_table([]) == []

    def test_missing_fields(self):
        rows = extract_articles_table([{}])
        assert rows[0]["날짜"] == ""
        assert rows[0]["제목"] == ""


class TestExtractOhlcvTable:
    def test_basic(self):
        bars = [{"date": "2024-01-15", "open": 180, "high": 190,
                 "low": 178, "close": 185, "volume": 1000000}]
        rows = extract_ohlcv_table(bars)
        assert len(rows) == 1
        assert rows[0]["close"] == 185
        assert rows[0]["date"] == "2024-01-15"

    def test_empty(self):
        assert extract_ohlcv_table([]) == []


class TestBuildAllocationRows:
    def _make_portfolio(self):
        return {
            "allocations": [
                {"ticker": "NVDA", "weight": 0.25, "action": "BUY",  "rationale": "Strong AI"},
                {"ticker": "AAPL", "weight": 0.08, "action": "HOLD", "rationale": "Mixed signals"},
                {"ticker": "TSLA", "weight": 0.00, "action": "SELL", "rationale": "Overvalued"},
            ],
            "cash_pct": 0.60,
            "hedge_pct": 0.07,
            "hedge_instrument": "put_option",
        }

    def test_row_count(self):
        rows = build_allocation_rows(self._make_portfolio())
        # 3 stocks + cash + hedge = 5
        assert len(rows) == 5

    def test_cash_row_present(self):
        rows = build_allocation_rows(self._make_portfolio())
        tickers = [r["종목"] for r in rows]
        assert any("현금" in t for t in tickers)

    def test_hedge_row_present(self):
        rows = build_allocation_rows(self._make_portfolio())
        tickers = [r["종목"] for r in rows]
        assert any("헤지" in t for t in tickers)

    def test_no_hedge_row_when_zero(self):
        portfolio = self._make_portfolio()
        portfolio["hedge_pct"] = 0.0
        rows = build_allocation_rows(portfolio)
        tickers = [r["종목"] for r in rows]
        assert not any("헤지" in t for t in tickers)

    def test_action_icons_applied(self):
        rows = build_allocation_rows(self._make_portfolio())
        buy_row = next(r for r in rows if "NVDA" in r["종목"])
        assert "🟢" in buy_row["결정"]


class TestBuildPipelineTrace:
    def _make_result(self):
        return {
            "ticker": "AAPL", "current_price": 185.92,
            "bars": [{}] * 124, "articles": [{}] * 30, "financials": [{}] * 2,
            "fundamental": {"fundamental_score": 0.78, "intrinsic_value_signal": "undervalued",
                            "pe_ratio": 16.4, "key_strengths": ["s1"], "key_risks": ["r1"]},
            "sentiment":   {"sentiment_score": 0.42, "dominant_emotion": "optimism",
                            "uncertainty": 0.3, "key_themes": ["AI"]},
            "news":        {"macro_impact": 0.2, "event_risk_level": 0.4,
                            "company_events": ["e1"], "catalyst_signals": ["c1"]},
            "technical":   {"technical_score": 0.35, "trend_direction": "down",
                            "rsi": 42.3, "macd_signal": "bearish", "entry_signal": "sell",
                            "support_level": 181.0, "resistance_level": 186.5},
            "researcher":  {"consensus": "neutral", "conviction": 0.52,
                            "bull_thesis": "Bull...", "bear_thesis": "Bear...",
                            "key_debate_points": ["pt1"], "risk_reward_ratio": 1.2},
            "trader":      {"action": "HOLD", "confidence": 0.52,
                            "position_size_pct": 0.0, "target_price": 195.0,
                            "stop_loss_price": 178.0, "reasoning": ["r1", "r2"]},
            "risk_manager": {"final_action": "HOLD", "action_changed": False,
                             "final_position_size_pct": 0.0, "cash_reserve_pct": 0.2,
                             "risk_level": "moderate", "risk_flags": ["flag1"],
                             "aggressive_view": "Agg...", "conservative_view": "Con...",
                             "neutral_view": "Neu...", "consensus_reasoning": "Cons..."},
        }

    def test_returns_8_steps(self):
        trace = build_pipeline_trace(self._make_result())
        assert len(trace) == 8  # steps 0~7

    def test_step_numbers_sequential(self):
        trace = build_pipeline_trace(self._make_result())
        steps = [t["step"] for t in trace]
        assert steps == list(range(8))

    def test_each_step_has_required_keys(self):
        trace = build_pipeline_trace(self._make_result())
        for t in trace:
            assert "label" in t
            assert "emoji" in t
            assert "input_summary" in t
            assert "output_summary" in t
            assert "meeting_lines" in t
            assert "key_output" in t

    def test_researcher_meeting_has_bull_bear(self):
        trace = build_pipeline_trace(self._make_result())
        researcher_step = next(t for t in trace if t["step"] == 5)
        speakers = [line[0] for line in researcher_step["meeting_lines"]]
        assert any("Bull" in s for s in speakers)
        assert any("Bear" in s for s in speakers)

    def test_risk_manager_meeting_has_3_personas(self):
        trace = build_pipeline_trace(self._make_result())
        risk_step = next(t for t in trace if t["step"] == 7)
        speakers = [line[0] for line in risk_step["meeting_lines"]]
        assert any("Rick" in s or "Aggressive" in s for s in speakers)
        assert any("Clara" in s or "Conservative" in s for s in speakers)
        assert any("Nathan" in s or "Neutral" in s for s in speakers)

    def test_data_collection_step(self):
        trace = build_pipeline_trace(self._make_result())
        data_step = trace[0]
        assert data_step["step"] == 0
        assert "124" in data_step["output_summary"]  # bars count
        assert "30" in data_step["output_summary"]   # articles count

    def test_empty_result_no_crash(self):
        trace = build_pipeline_trace({})
        assert len(trace) == 8  # 항상 8단계


class TestListBcDates:
    def test_returns_sorted_list(self, tmp_path, monkeypatch):
        (tmp_path / "2024-01-12").mkdir()
        (tmp_path / "2024-01-12" / "portfolio.json").write_text("{}")
        (tmp_path / "2024-01-05").mkdir()
        (tmp_path / "2024-01-05" / "portfolio.json").write_text("{}")
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        dates = list_bc_dates()
        assert dates == ["2024-01-05", "2024-01-12"]

    def test_excludes_dirs_without_portfolio_json(self, tmp_path, monkeypatch):
        (tmp_path / "2024-01-05").mkdir()  # no portfolio.json
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        assert list_bc_dates() == []

    def test_returns_empty_when_results_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path / "nonexistent")
        assert list_bc_dates() == []


class TestLoadBcResult:
    def test_loads_json(self, tmp_path, monkeypatch):
        d = tmp_path / "2024-01-05"
        d.mkdir()
        (d / "portfolio.json").write_text(json.dumps({"date": "2024-01-05", "tickers": ["AAPL"]}))
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        result = load_bc_result("2024-01-05")
        assert result["date"] == "2024-01-05"
        assert result["tickers"] == ["AAPL"]

    def test_returns_none_for_missing_date(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        assert load_bc_result("2024-99-99") is None

    def test_returns_none_when_results_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path / "nonexistent")
        assert load_bc_result("2024-01-05") is None


class TestLoadEvalResults:
    def test_loads_all_eval_files(self, tmp_path, monkeypatch):
        (tmp_path / "eval_2024-01-05.json").write_text(json.dumps({"period": "A"}))
        (tmp_path / "eval_2024-03-22.json").write_text(json.dumps({"period": "B"}))
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        results = load_eval_results()
        assert len(results) == 2
        periods = [r["period"] for r in results]
        assert "A" in periods and "B" in periods

    def test_returns_empty_when_no_eval_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path)
        assert load_eval_results() == []

    def test_returns_empty_when_results_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fmts, "_RESULTS_DIR", tmp_path / "nonexistent")
        assert load_eval_results() == []


class TestFormatApprovalBadge:
    def test_approved(self):
        assert format_approval_badge("approved") == "✅ APPROVED"

    def test_rejected(self):
        assert format_approval_badge("rejected") == "❌ REJECTED"

    def test_conditional(self):
        assert format_approval_badge("conditional_approval") == "⚠️ CONDITIONAL"

    def test_unknown_status(self):
        badge = format_approval_badge("pending")
        assert "pending" in badge
        assert "❓" in badge


class TestFormatReliabilityRows:
    def test_gated_below_floor(self):
        rows = format_reliability_rows({"fundamental": 0.30})
        assert rows[0]["상태"] == "🔴 GATED"
        assert rows[0]["신뢰도"] == "0.300"

    def test_low_between_floor_and_threshold(self):
        rows = format_reliability_rows({"sentiment": 0.50})
        assert rows[0]["상태"] == "🟡 LOW"

    def test_ok_above_threshold(self):
        rows = format_reliability_rows({"technical": 0.80})
        assert rows[0]["상태"] == "🟢 OK"

    def test_multiple_agents(self):
        rel = {"fundamental": 0.30, "sentiment": 0.50, "technical": 0.80}
        rows = format_reliability_rows(rel)
        assert len(rows) == 3
        agents = [r["에이전트"] for r in rows]
        assert "fundamental" in agents
