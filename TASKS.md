# TASKS — 현재 스프린트

> 최대 3개 태스크만 올림. 나머지는 BACKLOG.md에서 대기.
> 완료된 스프린트는 `docs/` 폴더로 아카이브.

---

## 스프린트: LangGraph B/C 전환 + 에이전트 피드백 루프 (2026-04-28) ✅ 완료

**목표**: B/C 파이프라인을 LangGraph 상태 기계로 전환. 에이전트 간 실제 피드백 루프(Otto retry, Dave→backtester) 구현.

### 실행 순서
```
C-001, C-002B, C-003  → 전부 완료 ✅
```

---

## C-001: MAM LLM 토론 추가
**상태**: completed
**우선순위**: high
**관련 파일**: `meetings/run_meetings.py`

### 완료 기준 달성
- `run_mam(llm=None)` 하위 호환 유지 ✅
- debate_skipped=True → llm 있어도 호출 안 됨 ✅
- LLM 실패 시 heuristic fallback ✅
- 899 passed ✅

### 최종 확인
- [x] harness all 통과 (899)
- [x] 실제 구현 범위: `_run_llm_debate()`, `_build_debate_signals()` 추가. `run_mam(llm=None)`, `run_all_meetings(llm=None)` 파라미터 추가. `llm_debate_used` 필드 반환.

---

## C-002B: backtester Dave 리스크 모드
**상태**: completed
**우선순위**: high
**관련 파일**: `simulation/backtester.py`

### 완료 기준 달성
- `_adjust_for_risk_mode()` 구현 ✅
- `backtest_all(risk_mode="normal")` 하위 호환 ✅
- 899 passed ✅

### 최종 확인
- [x] harness all 통과 (899)
- [x] 실제 구현 범위: `_RISK_MODE_PENALTY`, `_adjust_for_risk_mode()` 추가. `backtest_all(risk_mode="normal")` 파라미터 추가. `risk_mode_adjusted`, `risk_mode` 필드 반환.

---

## C-003: B/C LangGraph 전환
**상태**: completed
**우선순위**: high
**관련 파일**: `graph/bc_state.py` (신규), `graph/bc_graph.py` (신규), `graph/nodes/bc_*.py` (신규 7개), `scripts/run_loop.py`

### 설계 구상
`run_one_cycle()` 함수 순차 호출을 LangGraph 상태 기계로 교체.
기존 A 그래프(`graph/builder.py`) 손 안 댐 — 별도 B/C 그래프로 분리.

**✅ 선택한 이유**: conditional edge로 Otto retry, Dave→backtester 트리거를 State 기반으로 자연스럽게 처리. run_loop.py 오케스트레이션 코드 최소화.
**❌ 대안 제외 이유**: 기존 A 그래프 확장 시 SystemState 오염 + A 파이프라인 리스크.

### 구현 세부사항
```
graph/bc_state.py     — SystemStateBC TypedDict
graph/bc_graph.py     — build_bc_graph() + compile_bc_graph()
graph/nodes/bc_emily.py      — Emily SPY 분석
graph/nodes/bc_stock.py      — 종목별 B 파이프라인
graph/nodes/bc_backtester.py — 전략 백테스트 (risk_mode 지원)
graph/nodes/bc_meetings.py   — MAM/SDM/RAM (llm 전달)
graph/nodes/bc_portfolio.py  — Portfolio Manager
graph/nodes/bc_dave.py       — Dave 포트폴리오 리스크
graph/nodes/bc_otto.py       — Otto 승인 게이트

conditional edges:
  route_dave_risk: risk_score > 0.7 → bc_backtester (defensive)
  route_otto:      rejected + retry < 2 → bc_portfolio; else END
```

### 완료 기준 달성
- `bc_graph.invoke(initial_state)` → run_one_cycle()과 동일한 결과 구조 반환 ✅
- Otto rejected → PM 재실행 (최대 2회) conditional edge 작동 ✅
- Dave risk > 0.7 → backtester defensive 재실행 conditional edge 작동 ✅
- harness all 899 passed ✅

### 최종 확인
- [x] harness all 통과 (899)
- [x] 실제 구현 범위: `graph/bc_state.py` (SystemStateBC), `graph/bc_graph.py` (9노드 + conditional edges), `graph/nodes/bc_*.py` (7개 신규), `scripts/run_loop.py` run_one_cycle() → bc_graph.invoke() 교체, `scripts/portfolio_pipeline.py` otto_feedback 파라미터 추가

---

## B-004: Retrieval validity scoring B/C 연결
**상태**: completed
**우선순위**: low
**관련 파일**: `memory/run_memory.py`, `memory/retrieval/validity_scorer.py`, `memory/retrieval/retriever.py`

### 설계 구상
`build_context()`가 단순 최근 N개를 가져옴. `memory/retrieval/` 에 `compute_validity_score()` 가 이미 구현되어 있는데 B/C 파이프라인에서 미사용.

**✅ 선택한 이유**: 후보 2N개 로드 → validity_score 적용 → threshold 미만 제거 → 상위 N개 반환. 기존 반환 포맷 불변.
**❌ 대안 제외 이유**: 단순 최근 N개는 유효하지 않은(오래되거나 신뢰도 낮은) 메모리를 포함할 수 있음.

### 구현 세부사항
```python
# memory/run_memory.py — build_context() 수정
# 1. prev_results[:lookback*2] 로드 (후보 2N개)
# 2. compute_validity_score(entry, as_of) 적용
# 3. threshold=0.3 미만 제거
# 4. score 내림차순 정렬 → 상위 lookback개 반환
# 반환 포맷 변경 없음 (portfolio_pipeline.py 의존)
```
- `compute_validity_score` 시그니처 먼저 확인 필요 (validity_scorer.py 읽기)
- `build_context()`의 `as_of` 파라미터 없으면 추가

### 완료 기준
- validity_score < 0.3 항목이 필터링됨을 테스트로 검증
- lookback=3 기준 최대 6개 후보 중 threshold 이상만 반환
- tests/unit/test_retrieval.py 통과

### 제약사항
- 반환 포맷 변경 금지 (portfolio_pipeline.py 의존)
- 모든 항목이 threshold 미만이면 원래 방식대로 전체 반환 (fallback)
- as_of 없는 기존 호출 하위 호환 유지

### 테스트 피드백
harness all 884 passed ✅

### 최종 확인
- [x] harness all 통과
- [x] _GUIDE.md 업데이트
- [x] BACKLOG.md 이슈 정리
- [x] 실제 구현 범위 기록: build_context()에 as_of/current_regime 파라미터 추가, _apply_validity_filter() 헬퍼로 threshold=0.3 필터링 + 2N 후보 score 정렬, fallback 유지

---

## B-005: 감사 보고서 갱신
**상태**: completed
**우선순위**: medium
**관련 파일**: `docs/SYSTEM_AUDIT_REPORT_v2.md`

### 설계 구상
현재 보고서가 2026-04-17 스냅샷 — 이후 스프린트(TASK-001~011, B-001~003) 반영 안 됨.
보고서에 "실제 구현 안 됨"으로 표시된 항목 다수가 이제 구현 완료됨.

**✅ 선택한 이유**: 코드 재분석으로 "선언 vs 실제" 갭 업데이트. 진행 상황 정확히 반영.
**❌ 대안 제외 이유**: 오래된 보고서는 다음 의사결정에 잘못된 컨텍스트를 줌.

### 구현 세부사항
업데이트할 주요 항목:
- Pipeline A+B/C integration: TASK-001~005로 완료 (emily_context, dave_context, otto_gate 연결)
- Agent Gating: B-001으로 실제 LLM 호출 차단 완료
- Dual Reward (w_real): B-003으로 backtester 연동 완료
- Retrieval validity scoring: B-004 완료 후 반영 (순서 주의)
- MAM structured output: B-002로 DebateResolution 추가
- 전체 구현율 재평가 (42~48% → 현재 수준으로)

보고서 형식:
- 기존 표 구조 유지
- "Actual" 컬럼 + "Notes" 업데이트
- 하단에 "갱신 이력" 섹션 추가

### 완료 기준
- 각 항목의 실제 구현 상태가 현재 코드와 일치
- 전체 구현율 재평가 포함
- 갱신일 2026-04-28 명시

### 제약사항
- 코드를 직접 읽고 확인 (문서 추정 금지)
- 테스트 없음 — 코드 분석 + 문서 작업
- B-004 완료 전이라면 retrieval validity 항목은 "B-004 진행 중"으로 표시

### 테스트 피드백
해당 없음 (문서 작업)

### 최종 확인
- [x] 각 항목 코드 직접 확인
- [x] 전체 구현율 재평가 (42~48% → 62~68%)
- [x] 갱신일/이력 기록 (2026-04-28)
- [x] 실제 구현 범위 기록: 11개 항목 Actual/Notes 갱신, Section 2~7 전면 업데이트, 갱신 이력 추가

---

## 완료된 스프린트

| 날짜 | 스프린트 | 상세 |
|------|---------|------|
| 2026-04-21 | Pipeline A+B/C 통합 + 기술 부채 픽스 (TASK-001~011) | `docs/SPRINT_2026-04-17_pipeline_integration.md` |
| 2026-04-28 | 학습 루프 완성 + 품질 강화 (B-001~003) | `docs/SPRINT_2026-04-21_learning_loop.md` |
| 2026-04-28 | Retrieval 강화 + 감사 보고서 갱신 (B-004~005) | `docs/SPRINT_2026-04-28_retrieval_audit.md` |
| 2026-04-28 | LangGraph B/C 전환 + 에이전트 피드백 루프 (C-001~003) | `docs/SPRINT_2026-04-28_langgraph_bc.md` |

---

*마지막 갱신: 2026-04-28 — C-001, C-002B, C-003 완료*
