# Hybrid Investment System — Comprehensive Implementation Evaluation Report

**Evaluation Date**: 2026-04-28 (갱신)
**Evaluator**: Code-level synthesis (actual source code analysis, not documentation claims)
**Sources**: CLAUDE.md, DEV_GUIDE.md, CLAUDE_CODE_BRIEFING.md, DESIGN_SPEC_v3.6.md + all primary source files
**Previous Evaluation**: 2026-04-17 (최초 작성)

---

## Executive Summary

The self-reported completion rate in CLAUDE.md (Phases 1–5 all marked `[x]`) previously overstated true implementation quality. Since the 2026-04-17 evaluation, significant integration work has been completed: **Pipeline A agents (Emily, Dave, Otto) are now called from `run_loop.py`** as part of the B/C execution flow. Emily provides SPY macro context, Dave performs portfolio-level risk assessment, and Otto acts as a final approval gate with real `compute_adaptive_weights()` driven by `strategy_memory.json` history.

Agent gating now enforces `hard_gate` (LLM call skip) and `downweight` (score shrinkage) based on reliability state persisted across sessions. MAM produces structured `MAMDebateResolution` output. The dual reward mechanism (`w_real`) parameterizes backtester strategy adjustments.

The LangGraph `orchestrator.py` full graph is still not invoked from `run_loop.py` — instead, individual Pipeline A agents are called as discrete steps within the B/C loop. This is a pragmatic integration rather than the full LangGraph state machine design. Retrieval validity scoring remains disconnected from the B/C path.

**Revised overall implementation rate against v3.6 spec: approximately 62–68%.**

---

## 1. Overall Implementation Rate

### Against CLAUDE_CODE_BRIEFING.md (v3.6 target)

| Spec Area | Claimed | Actual | Notes |
|---|---|---|---|
| Pipeline A (Emily→Bob→Dave→Otto via LangGraph) | Done | **Partial — agents integrated, LangGraph not used** | Emily/Dave/Otto called from `run_loop.py` as discrete steps (TASK-001~005); `orchestrator.py` LangGraph graph still not invoked |
| Pipeline B/C (TradingAgents individual stocks) | Done | **Functional** | Works end-to-end via `stock_pipeline.py` |
| Unified A+B/C integration | Not claimed | **Pragmatic integration done** | Emily→PM context, Dave→portfolio risk, Otto→approval gate all wired in `run_loop.py` (TASK-001~005). Not full LangGraph state machine. |
| LangGraph conditional edges / LLM-driven flow | Done | Partial | Edges call Python heuristic functions, not LLM judgment. LangGraph graph itself not used in main loop. |
| Dual Reward (w_sim * r_sim + w_real * r_real) | Done | **Functional** | `compute_adaptive_weights()` called with real `strategy_memory.json` history in `otto_gate.py` (TASK-003, B-003). `w_real` parameterizes `backtester._adjust_for_r_real()`. |
| Memory 4-layer (market/reports/strategy/decision) | Done | Partial | `strategy_memory` has real write-back + cross-session persistence; others are in-memory (Pipeline A) |
| Retrieval validity scoring | Done | **Partial — B/C path still disconnected** | Code exists in `validity_scorer.py`; not called in B/C path (B-004 진행 중) |
| 3 Meetings with structured debate | Done | **Structured adapter** | `run_mam()` returns `MAMDebateResolution` via `_parse_mam_resolution()` (B-002). Still no LLM debate call, but structured schema output. |
| Calibration with rolling std | Done | **Functional + persistent** | `reliability_state.json` persisted across sessions (TASK-007). EMA history survives process restart. |
| Agent Gating (reliability floor) | Done | **Functional** | `get_current_gating()` → `hard_gate` skips LLM call, `downweight` shrinks scores in `portfolio_pipeline.py` (B-001) |
| r_real feedback loop closing | Done | **Functional** | `outcome_filler.py` fills past results correctly with T+7 guard |

---

## 2. What Is Actually Working

### 2.1 Pipeline B/C End-to-End (the core functional path)
`scripts/stock_pipeline.py` → `scripts/portfolio_pipeline.py` → `run_portfolio_manager()` is genuinely functional. The 7-agent sequence (4 Analysts → Researcher → Trader → Risk Manager → Portfolio Manager) executes with real LLM calls, Pydantic schema validation, and structured output.

### 2.2 Date Loop and Result Persistence
`scripts/run_loop.py` correctly iterates weekly/daily date ranges, saves results to `results/YYYY-MM-DD/portfolio.json`, supports resume and dry-run. **This is solid.**

### 2.3 Cross-Cycle Memory (run_memory.py)
`memory/run_memory.py` reads prior results, performs point-in-time-safe filtering, builds structured context including action streaks and `r_real` sorting, and returns a formatted prompt string. **Genuinely functional.**

### 2.4 Backtester with 6 Strategy Pool
`simulation/backtester.py` runs 6 strategies on real OHLCV bars, computes Sharpe/Sortino/MDD/win_rate, adjusts scores based on prior `r_real` via `_adjust_for_r_real()`, and persists to `results/strategy_memory.json`. **Working correctly.**

### 2.5 outcome_filler.py — r_real Write-Back
`memory/outcome_filler.py` correctly implements the T+7 point-in-time rule, fetches weighted portfolio returns from Polygon, writes `r_real` back to `portfolio.json` and `strategy_memory.json`. Reliability thresholds (r_real ≥ 0.02 → 1.0, ≥ 0 → 0.85, < 0 → 0.65) match `validity_scorer.py`. **Working.**

### 2.6 Pipeline A+B/C Integration (NEW — 2026-04-21)
`run_loop.py::run_one_cycle()` now calls Pipeline A agents as discrete steps within the B/C flow:
- **Emily** (`integration/emily_context.py`): SPY macro analysis → `emily_context` string injected into Portfolio Manager prompt. Also provides `market_regime` for backtester regime-aware strategy adjustment (`backtester._adjust_for_regime()`).
- **Dave** (`integration/dave_context.py`): Portfolio-level risk assessment after PM decision. Pre-computes `risk_components` (beta, illiquidity, sector_concentration, volatility) with HHI. `risk_score` tolerance ±0.05 enforced in `agents/dave.py::_validate_output()`.
- **Otto** (`integration/otto_gate.py`): Final approval gate. `compute_adaptive_weights()` called with real `strategy_memory.json` reward history. `apply_otto_decision()` adjusts portfolio based on approval status (scale down / hedge up / reject).

### 2.7 Agent Gating — LLM Call Control (NEW — 2026-04-28)
`calibration/run_calibration.py::get_current_gating()` returns per-agent gating decisions based on reliability EMA state. `portfolio_pipeline.py::run_single_stock()` enforces:
- `hard_gate`: Skips LLM call entirely, returns `{}` for that agent role (L76-79).
- `downweight`: Runs LLM call but shrinks scores toward neutral (5.0) with factor 0.5 via `_apply_downweight()` (L37-55).

Gating state persists across sessions via `reliability_state.json` (L59-94).

### 2.8 MAM Structured Output (NEW — 2026-04-28)
`meetings/run_meetings.py::run_mam()` now returns a `"resolution"` key containing a structured `MAMDebateResolution`-compatible dict via `_parse_mam_resolution()`. Fields: `meeting_type`, `date`, `consensus`, `key_risks`, `recommended_bias`, `confidence`. Schema defined in `schemas/meeting_schema.py::MAMDebateResolution`.

### 2.9 LangGraph Graph (Pipeline A) — Compiles and Is Structurally Sound
`graph/builder.py` assembles the full 14-node state machine. `SystemState` TypedDict matches the v3.6 spec. Otto's `_FORBIDDEN_RAW_FIELDS` block is enforced. **Structurally correct; individual agents now integrated via adapters, but full LangGraph graph still not invoked from `run_loop.py`.**

### 2.10 Retrieval Validity Scorer
`memory/retrieval/validity_scorer.py` implements the full 5-factor formula (Sim × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability) with floor-based case rejection. Formula is correct and consistent with spec. **Still not called in B/C path (B-004).**

---

## 3. Critical Gaps

### 3.1 ~~Pipeline A Is Never Called From run_loop.py~~ → RESOLVED (Partial)

**Status: Substantially resolved (2026-04-21, TASK-001~005).**

`run_loop.py::run_one_cycle()` now imports and calls:
- `integration/emily_context.run_emily_for_context()` — Emily SPY macro analysis (L132-147)
- `integration/dave_context.run_dave_for_portfolio()` — Dave portfolio risk (L232-245)
- `integration/otto_gate.run_otto_approval()` + `apply_otto_decision()` — Otto gate (L247-261)

**Still not called** (and this is by design — pragmatic integration over full LangGraph):
- `orchestrator.Orchestrator` / `graph/builder.compile_graph()`
- `meetings/market_analysis.MarketAnalysisMeeting` (Pipeline A debate logic)
- `meetings/strategy_development.StrategyDevelopmentMeeting`
- `meetings/risk_alert.RiskAlertMeeting` (Pipeline A utility-based)
- `ledger/shared_ledger.py`

The CLAUDE.md diagram (`Emily → [B/C stocks] → Bob(sim) → Meetings → Calibration → PM → Dave → Otto`) is now **operational**. Bob remains the backtester (not an LLM agent in B/C path).

### 3.2 ~~Dual Reward Is a Schema Field~~ → RESOLVED

**Status: Resolved (2026-04-28, TASK-003 + B-003).**

- `integration/otto_gate.py::run_otto_approval()` calls `compute_adaptive_weights()` with real `strategy_memory.json` reward history (L193-194).
- `run_loop.py` extracts `w_real` from previous Otto output (L116-121) and passes to `backtester.backtest_all(w_real=w_real)` (L171).
- `backtester._adjust_for_r_real()` uses `w_real` to parameterize bonus/penalty strength (L144-145): `w_real=0.5 → ±10/15%`, `w_real=0.7 → ±14/21%`.

**Remaining limitation**: `utils/utility.py::compute_utility_from_state()` still uses heuristic proxy (`0.5`/`0.1`) — but this is only used in the disconnected Pipeline A LangGraph path.

### 3.3 ~~Meetings Are Prompt-Injection Adapters~~ → PARTIALLY RESOLVED

**Status: Structured output added (2026-04-28, B-002).**

`run_mam()` now returns a `"resolution"` key with `MAMDebateResolution`-compatible structure via `_parse_mam_resolution()`. This provides: `consensus`, `key_risks`, `recommended_bias`, `confidence`.

**Remaining limitations**:
- Still no LLM debate call — resolution is derived from heuristic aggregation of stock signals.
- `meetings/market_analysis.MarketAnalysisMeeting` (real debate logic) still only accessible via Pipeline A.
- No ledger recording of debate outcomes.

### 3.4 Retrieval Validity Scoring Is Not Active in B/C Path (UNCHANGED)

`memory/retrieval/validity_scorer.py` and `retriever.py` are called from `graph/nodes/memory_update.py` (Pipeline A only). The B/C path uses flat JSON reads from `results/`, not scored top-k retrieval. **B-004 in backlog.**

### 3.5 LangGraph Is Sequential, Not LLM-Judgment-Driven (UNCHANGED)

All conditional edge functions in `graph/edges/daily_edges.py` and `graph/edges/weekly_edges.py` are Python heuristic functions checking state values like `risk_score > 0.75`. No edge calls an LLM to decide whether to skip or retry a node. **Low priority — LangGraph graph not used in main loop.**

### 3.6 ~~Agent Reliability Gating Does Not Block LLM Calls~~ → RESOLVED

**Status: Resolved (2026-04-28, B-001).**

`calibration/run_calibration.py::get_current_gating()` returns per-agent decisions. `run_loop.py` loads gating at cycle start (L152). `portfolio_pipeline.py::run_single_stock()`:
- `hard_gate`: Skips LLM call entirely (L76-79), returns `{}` for that role.
- `downweight`: Runs LLM call, then shrinks scores toward neutral via `_apply_downweight()` (L82-83).

Researcher role also gated independently (L91-99).

### 3.7 ~~Reliability State Is Session-Ephemeral~~ → RESOLVED

**Status: Resolved (2026-04-21, TASK-007).**

`calibration/run_calibration.py`:
- `_save_reliability_state()` serializes `AgentReliabilityManager` to `results/reliability_state.json` after each `update_bc_reliability()` call (L73-93, L346).
- `_load_reliability_state()` restores state on process start (L59-70, L106-114).
- `_calibrators` (per-ticker rolling history) remain session-ephemeral — only reliability EMA is persisted.

---

## 4. Dead Code / Disconnected Modules

| Module | Status | Why Disconnected |
|---|---|---|
| `orchestrator.py` | Exists, compiles | Never imported from `run_loop.py` (individual agents called via integration adapters instead) |
| `meetings/market_analysis.MarketAnalysisMeeting` | Has real debate logic | Only called from `orchestrator.run_weekly_cycle()` |
| `meetings/strategy_development.StrategyDevelopmentMeeting` | Exists | Pipeline A only |
| `meetings/risk_alert.RiskAlertMeeting` | Has RiskAdjustedUtility formula | Pipeline A only |
| `memory/retrieval/retriever.py` + `validity_scorer.py` | Exists, tested | Only called from `graph/nodes/memory_update.py` (B-004 planned) |
| ~~`agents/emily.py`~~ | **NOW CONNECTED** | Called via `integration/emily_context.py` from `run_loop.py` |
| `agents/bob.py` | Exists | LLM Bob agent not called; backtester serves as Bob proxy in B/C |
| ~~`agents/dave.py`~~ | **NOW CONNECTED** | Called via `integration/dave_context.py` from `run_loop.py` |
| ~~`agents/otto.py`~~ | **NOW CONNECTED** | Called via `integration/otto_gate.py` from `run_loop.py` |
| `graph/` (entire directory) | Compiles | Never invoked from `run_loop.py` (agents called directly via adapters) |
| `ledger/shared_ledger.py` | Exists | Pipeline A only |
| `evaluation/` | Exists | Not called from any entry point |

---

## 5. Data Flow Integrity: r_real End-to-End

### In Pipeline B/C (active path): ✅ Functional with closed-loop adaptive weighting

```
Polygon API → fetch_data() → run_single_stock() (with gating: hard_gate/downweight)
→ run_portfolio_manager() → portfolio.json (r_real = None initially)
→ [next cycle] outcome_filler.fill_pending_outcomes()
→ portfolio.json (r_real = weighted Polygon return, T+7 guard) ✅
→ strategy_memory.json (r_real, outcome_reliability updated) ✅
→ backtester._adjust_for_r_real(w_real=...) (Sharpe ±10~21% adjustment, w_real-parameterized) ✅
→ otto_gate.compute_adaptive_weights(reward_history) → w_sim/w_real 계산 ✅ (NEW)
→ otto_gate.apply_otto_decision() → portfolio allocation 조정 ✅ (NEW)
→ run_loop extracts w_real from otto_output → next cycle backtester ✅ (NEW)
→ format_meetings_for_prompt() (text string to Portfolio Manager LLM) ✅
```

**r_real now flows through a complete closed loop**: outcome_filler → strategy_memory → compute_adaptive_weights → w_real → backtester adjustment → next cycle portfolio.

### In Pipeline A (LangGraph path): ⚠️ Still disconnected

```
logging_node.py: r_real stored in in-memory strategy_memory object
→ [process restart: all state lost]
→ compute_adaptive_weights() never called from LangGraph nodes
```

Note: The LangGraph path is now effectively superseded by the B/C integration path for production use.

---

## 6. Verdict Per Phase

| Phase | CLAUDE.md Claim | Actual Score (Apr-17) | Actual Score (Apr-28) | Key Change |
|---|---|---|---|---|
| Phase 1 — Loop | Complete ✅ | **9/10** | **9/10** | Emily/Dave/Otto integration added to loop |
| Phase 2 — Memory | Complete ✅ | **6/10** | **7/10** | Reliability state now persists via JSON; retrieval still flat (B-004) |
| Phase 3 — Bob Simulation | Complete ✅ | **7/10** | **8/10** | `w_real` parameterization + Emily regime-aware Sharpe adjustment |
| Phase 4 — 3 Meetings | Complete ✅ | **3/10** | **5/10** | MAMDebateResolution structured output; still no LLM debate |
| Phase 5 — Calibration | Complete ✅ | **4/10** | **7/10** | Gating enforced (hard_gate/downweight); reliability persists across sessions |
| Pipeline A+B/C Integration | Not claimed | **0/10** | **7/10** | Emily→PM context, Dave→risk, Otto→gate all wired (TASK-001~005) |
| Dual Reward Loop | Claimed | **2/10** | **7/10** | compute_adaptive_weights() with real history; w_real closed loop |

**Overall composite: ~62–68% against full v3.6 spec** (up from 42–48%)

---

## 7. Priority Fix List

### ~~Fix 1: Connect Pipeline A to run_loop.py~~ → RESOLVED
**Resolved (TASK-001~005, 2026-04-21).** Emily/Dave/Otto integrated via adapter pattern. Full LangGraph orchestrator not used — pragmatic approach documented.

### ~~Fix 2: Persist Reliability State Across Sessions~~ → RESOLVED
**Resolved (TASK-007, 2026-04-21).** `reliability_state.json` saved/loaded in `calibration/run_calibration.py`.

### ~~Fix 3: Wire compute_adaptive_weights() Into Policy Selection~~ → RESOLVED
**Resolved (TASK-003, 2026-04-21).** `integration/otto_gate.py` loads `strategy_memory.json` reward history and calls `compute_adaptive_weights()`.

### ~~Fix 4: Enforce Gating Before LLM Calls~~ → RESOLVED
**Resolved (B-001, 2026-04-28).** `portfolio_pipeline.py` enforces `hard_gate` (skip) and `downweight` (shrink scores).

### ~~Fix 5: Structured MAM Output~~ → RESOLVED
**Resolved (B-002, 2026-04-28).** `MAMDebateResolution` schema + `_parse_mam_resolution()` in `run_meetings.py`.

---

### Remaining Fix List (2026-04-28)

### Fix 6: Connect Retrieval Validity Scoring to B/C Path

**Impact: Medium.** `validity_scorer.py` is functional but only called from Pipeline A's `graph/nodes/memory_update.py`. The B/C path in `memory/run_memory.py` reads flat JSON without scoring. Wiring scored retrieval would improve memory quality for Portfolio Manager context.

**Entry point**: `memory/run_memory.py::get_context_prompt()` — replace flat JSON reads with `retriever.retrieve()` calls.
**Status**: B-004 in backlog.

### Fix 7: LLM-Based Meeting Debates

**Impact: Medium.** MAM now has structured output but still uses heuristic aggregation. Adding optional LLM debate calls (even 1 per meeting) would substantially improve signal quality. The `MarketAnalysisMeeting` class in `meetings/market_analysis.py` has the debate logic — it just needs an adapter to work with B/C stock_results.

**Entry point**: `meetings/run_meetings.py::run_mam()`

### Fix 8: Ledger Recording for B/C Path

**Impact: Low-Medium.** `ledger/shared_ledger.py` exists but is only used in Pipeline A. Recording meeting resolutions and Otto decisions in the ledger would enable audit trail and future analysis.

**Entry point**: `ledger/shared_ledger.py` + `run_loop.py`

### Fix 9: Per-Ticker Calibrator Persistence

**Impact: Low.** `_calibrators` (rolling score history per ticker) are still session-ephemeral. Only reliability EMA is persisted. For multi-session backtesting, per-ticker calibration history should also be saved.

**Entry point**: `calibration/run_calibration.py::_get_calibrator()`

---

## Appendix: Architecture Disconnect Diagram

```
DESIGNED (CLAUDE_CODE_BRIEFING.md target):
  run_loop.py
    └─ Orchestrator
         ├─ [Daily] Emily → Bob → Dave → Otto (LangGraph)
         │         ↑ retrieval from memory (validity-scored)
         │         ↑ reliability gating active
         ├─ [Weekly] MAM (debate) → SDM → RAM (utility-based)
         └─ [T+7] outcome_filler → r_real → adaptive weights

ACTUAL (what runs — updated 2026-04-28):
  run_loop.py
    ├─ outcome_filler.fill_pending_outcomes()       ← real, T+7 safe ✅
    ├─ get_current_gating()                         ← reliability-based gating ✅ (NEW)
    ├─ Emily (integration/emily_context.py)         ← SPY macro → PM context ✅ (NEW)
    ├─ run_single_stock() × N (Pipeline B/C)        ← real LLM calls, gated ✅ (UPDATED)
    │   └─ hard_gate: skip LLM | downweight: shrink scores
    ├─ backtester.backtest_all(w_real=...)           ← real, 6 strategies, w_real param ✅ (UPDATED)
    ├─ run_all_meetings()                           ← structured MAMDebateResolution ✅ (UPDATED)
    ├─ run_calibration_audit()                      ← persistent reliability state ✅ (UPDATED)
    ├─ run_portfolio_manager()                      ← real LLM, receives 5 context strings ✅
    ├─ Dave (integration/dave_context.py)            ← portfolio risk assessment ✅ (NEW)
    └─ Otto (integration/otto_gate.py)              ← approval gate + adaptive weights ✅ (NEW)
        └─ compute_adaptive_weights(real history) → w_real → next cycle

  orchestrator.py [STILL NOT CALLED — superseded by adapter pattern]
    └─ LangGraph: full state machine + real meetings + retrieval + ledger
```

The codebase has evolved from two parallel systems to a pragmatic integration: Pipeline A agents (Emily, Dave, Otto) are called individually within the B/C loop via adapter modules (`integration/`). The full LangGraph state machine remains available but is superseded for production use. **The core integration work is done; remaining gaps are retrieval scoring (B-004) and LLM-based meeting debates.**

---

*Generated by code-level analysis of all primary source files. Not based on documentation claims.*

---

## 갱신 이력

| 날짜 | 갱신 내용 |
|------|---------|
| 2026-04-17 | 최초 작성. 전체 구현율 42~48% 평가. Pipeline A/B/C 분리 문제, 5개 Critical Gap 식별. |
| 2026-04-28 | TASK-001~011, B-001~003 반영. Pipeline A+B/C 통합 (Emily/Dave/Otto adapter 연결), Gating 실제 LLM 호출 차단, Dual Reward w_real 폐쇄 루프, MAM 구조화 출력, Reliability 영속화 완료. 구현율 62~68%로 상향. 5개 Critical Gap 중 4개 해결, 신규 Remaining Fix 4개 추가. |
