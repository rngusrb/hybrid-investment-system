# Sprint 아카이브 — LangGraph B/C 전환 + 에이전트 피드백 루프

**기간**: 2026-04-28
**목표**: B/C 파이프라인을 LangGraph 상태 기계로 전환. MAM LLM 토론, Dave→backtester 피드백, Otto retry loop 구현.

---

## 완료된 태스크

### C-001: MAM LLM 토론 추가
- `meetings/run_meetings.py`: `_build_debate_signals()`, `_run_llm_debate()` 추가
- `run_mam(llm=None)`, `run_all_meetings(llm=None)` 하위 호환 파라미터 추가
- `debate_skipped=False` + `llm` 있을 때만 LLM 호출 (consensus < 0.80)
- LLM 실패 시 heuristic `_parse_mam_resolution()` fallback
- `llm_debate_used` 필드 반환

### C-002B: backtester Dave 리스크 모드
- `simulation/backtester.py`: `_RISK_MODE_PENALTY`, `_adjust_for_risk_mode()` 추가
- `backtest_all(risk_mode="normal")` 파라미터 추가 (하위 호환)
- defensive 모드: momentum -20%, directional -15% Sharpe 패널티
- `risk_mode_adjusted`, `risk_mode` 필드 반환

### C-003: B/C LangGraph 전환
- `graph/bc_state.py`: `SystemStateBC` TypedDict + `make_initial_bc_state()` 신규
- `graph/bc_graph.py`: `build_bc_graph()`, `compile_bc_graph()` 신규
- `graph/nodes/bc_emily.py`: Emily SPY 레짐 분석 노드
- `graph/nodes/bc_stock.py`: 종목별 B 파이프라인 노드
- `graph/nodes/bc_backtester.py`: 전략 백테스트 노드 (emily_context, risk_mode 지원)
- `graph/nodes/bc_meetings.py`: MAM/SDM/RAM 노드 (llm 전달)
- `graph/nodes/bc_calibration.py`: 신뢰도 감사 + gating 갱신 노드
- `graph/nodes/bc_portfolio.py`: Portfolio Manager 노드 (otto_feedback 지원)
- `graph/nodes/bc_dave.py`: Dave 포트폴리오 리스크 노드
- `graph/nodes/bc_otto.py`: Otto 승인 게이트 노드
- `scripts/portfolio_pipeline.py`: `run_portfolio_manager(otto_feedback="")` 파라미터 추가
- `scripts/run_loop.py`: `run_one_cycle()` → `bc_graph.invoke()` 교체

### Conditional edges (핵심)
```
Dave risk_score > 0.7 (최초 1회) → BC_BACKTESTER_DEFENSIVE → BC_PORTFOLIO_MANAGER
Otto rejected + retry < 2        → BC_PORTFOLIO_MANAGER (otto_retry_count++)
```

---

## 테스트 결과
- harness all: **899 passed** (C-001: +7, C-002B: +9 테스트 추가)

## 미완성 / 다음 스프린트 후보
- bc_graph 통합 테스트 없음 (노드 단위 테스트만)
- DEV_GUIDE.md B/C 파이프라인 섹션 LangGraph 반영 필요
- Pipeline A LangGraph(`orchestrator.py`)와 B/C 그래프 통합 가능성 검토
