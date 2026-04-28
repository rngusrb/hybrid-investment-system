# Hybrid Investment System — Claude 작업 지침

## 문서 계층 구조

| 파일 | 역할 |
|------|------|
| **CLAUDE.md** (이 파일) | 작업 규칙, 워크플로우 요약, 완료 이력 |
| **DEV_GUIDE.md** | 전체 아키텍처 지도, 데이터 흐름, 금지사항 색인 |
| **WORKFLOW.md** | 멀티에이전트 워크플로우 프로토콜 상세 |
| **TASKS.md** | 현재 스프린트 태스크 목록 (최대 3개) |
| **BACKLOG.md** | 발견된 이슈 + 다음 스프린트 대기 태스크 |
| **각폴더/_GUIDE.md** | 폴더별 패턴, 금지사항, 최근 변경 이력 |
| **docs/** | 감사 보고서, 로그, 결과 아카이브 |

**작업 시작 전 반드시 읽을 것**: DEV_GUIDE.md → TASKS.md → 해당 폴더/_GUIDE.md

---

## 멀티에이전트 워크플로우 (요약)

복잡한 구현 작업은 Claude Code Agent Teams로 진행. 상세는 **WORKFLOW.md** 참조.

```
팀 리드  →  TASKS.md 검토 + 팀 구성 지시
     ↓
구현 팀원 × N  →  태스크별 병렬 구현
     ↓
테스트 팀원  →  harness 실행 + TASKS.md 피드백 기록
     ↓
최종 확인 팀원  →  harness all + 체크리스트 + 문서 업데이트
```

**태스크 스키마**: 설계 구상 / 구현 세부사항 / 완료 기준 / 제약사항 / 테스트 피드백 / 최종 확인 체크리스트

---

## 현재 스프린트

→ **TASKS.md** 참조

현재 작업: **LangGraph B/C 전환 + 에이전트 피드백 루프 (C-001~003, 완료)**

BACKLOG: D-001 (bc_graph 통합 테스트), D-002 (DEV_GUIDE.md B/C 섹션 갱신) 대기 중.

---

## 완료된 것

### 기반 시스템 (2026-04-07)
- [x] 파이프라인 A: Emily→Bob→Dave→Otto (LangGraph, SPY 고정)
- [x] 파이프라인 B: 4 Analysts→Researcher→Trader→RiskManager (개별 종목)
- [x] 파이프라인 C: B×N + Portfolio Manager (멀티 종목)
- [x] schemas/stock_schemas.py + portfolio_schemas.py
- [x] prompts/ (7개 에이전트 시스템 프롬프트)
- [x] scripts/harness.py + 전체 폴더 연결
- [x] 재무제표 룩어헤드 이중 필터
- [x] live_e2e_bc_test.py
- [x] dashboard/ (app.py + 3 pages)

### Phase 1–6 (2026-04-14)
- [x] **Phase 1**: run_loop.py — 날짜 범위 루프 (weekly/daily/resume/dry-run)
- [x] **Phase 2**: memory/run_memory.py — results/ 기반 영속 메모리
- [x] **Phase 3**: simulation/backtester.py — 6개 전략 Pool 백테스트
- [x] **Phase 4**: meetings/run_meetings.py — MAM/SDM/RAM 어댑터
- [x] **Phase 5**: calibration/run_calibration.py — Calibration+Audit+Reliability
- [x] **Phase 6**: memory/outcome_filler.py — r_real T+7 피드백 루프

### r_real 학습 루프 (2026-04-17)
- [x] portfolio_manager_system.md — Historical Performance Context 섹션
- [x] backtester._adjust_for_r_real() — r_real 기반 전략 가중치 조정
- [x] meetings/run_meetings.py — r_real 주입 + prior_performance 반환
- [x] run_loop.py — prev_r_real 추출 → meetings에 전달
- [x] portfolio_pipeline.py — silent exception 로깅

### LangGraph B/C 전환 + 에이전트 피드백 루프 (2026-04-28)
- [x] meetings/run_meetings.py — `_run_llm_debate()`, `_build_debate_signals()` 추가, `llm_debate_used` 반환 (C-001)
- [x] simulation/backtester.py — `_adjust_for_risk_mode()`, `_RISK_MODE_PENALTY` 추가 (C-002B)
- [x] graph/bc_state.py — `SystemStateBC` TypedDict + `make_initial_bc_state()` 신규 (C-003)
- [x] graph/bc_graph.py — `build_bc_graph()`, conditional edges (Dave risk>0.7, Otto retry) (C-003)
- [x] graph/nodes/bc_*.py — 7개 신규 노드 (emily/stock/backtester/meetings/calibration/portfolio/dave/otto) (C-003)
- [x] scripts/run_loop.py — run_one_cycle() → bc_graph.invoke() 교체 (C-003)
- [x] scripts/portfolio_pipeline.py — otto_feedback 파라미터 추가 (C-003)

### Retrieval 강화 + 감사 보고서 갱신 (2026-04-28)
- [x] memory/run_memory.py — build_context() validity scoring 적용 (B-004)
- [x] docs/SYSTEM_AUDIT_REPORT_v2.md — 전면 갱신, 구현율 62~68% (B-005)

### 학습 루프 완성 + 품질 강화 (2026-04-28)
- [x] calibration/run_calibration.py — get_current_gating() 추가 (B-001)
- [x] scripts/portfolio_pipeline.py — gating 파라미터, hard_gate/downweight 분기 (B-001)
- [x] scripts/run_loop.py — gating 로드 연결 + otto w_real 추출 → backtester 전달 (B-001, B-003)
- [x] schemas/meeting_schema.py — MAMDebateResolution 클래스 추가 (B-002)
- [x] meetings/run_meetings.py — _parse_mam_resolution() + run_mam() "resolution" 키 (B-002)
- [x] simulation/backtester.py — _adjust_for_r_real() w_real 파라미터화 (B-003)

### Pipeline A+B/C 통합 + 기술 부채 픽스 (2026-04-21)
- [x] integration/emily_context.py — Emily SPY 레짐 → PM 컨텍스트 주입
- [x] integration/dave_context.py — Dave 포트폴리오 리스크 평가
- [x] integration/otto_gate.py — Otto 최종 승인 게이트 + adaptive_weights 실제 연결
- [x] scripts/portfolio_pipeline.py — emily_context 파라미터 추가
- [x] scripts/run_loop.py — Emily→Dave→Otto 통합 실행
- [x] simulation/backtester.py — Emily regime-aware 전략 Sharpe 보정
- [x] calibration/run_calibration.py — reliability_state.json 영속화
- [x] agents/dave.py — risk_score tolerance ±0.05 (TASK-009)
- [x] graph/nodes/calibration.py — Dave shrinkage 활성화, stress_severity 기반 confidence (TASK-010)
- [x] utils/forward_return.py — 증시 휴장일 T0 fallback (TASK-011)

---

## 작업 기본값

- 테스트 수반 작업: **전부 통과할 때까지 루프 반복** (max 10회)
- 중간 확인 요청 금지 — 막히면 `_GUIDE.md` 규칙 갱신 후 재시도
- 10회 초과 시에만 현황 보고 후 대기
- 단순 버그 수정/개선은 해당 폴더 `_GUIDE.md`에만 기록 — CLAUDE.md 건드리지 않음
- **Silent Failure 의무 체크**: `except Exception: pass/continue`, 빈 dict 반환, 로그 없는 fallback은 반드시 로깅 추가
- **"완료" 선언 기준**: 테스트 통과 + 실제 구현 범위 기록 (단순화된 것 있으면 명시) + _GUIDE.md 업데이트

---

## 작업 프로토콜 (단순 작업용)

단일 파일 수정, 버그 픽스 등 간단한 작업:

```
1. DEV_GUIDE.md + 해당 폴더 _GUIDE.md 확인
2. python scripts/harness.py <폴더>/ 실행 (현재 상태 파악)
3. 코드 수정
4. python scripts/harness.py <폴더>/ 재실행
5. 실패 시 → 원인 파악 → 수정 → _GUIDE.md 금지사항 갱신 → 4번으로
6. 통과 시 → _GUIDE.md 최근변경 업데이트 → 완료
```

복잡한 작업 → WORKFLOW.md 멀티에이전트 프로토콜 사용.

> **프로토콜 권위**: 단일 파일 수정/버그픽스 → CLAUDE.md 작업 프로토콜 적용. 멀티 파일·신규 모듈·파이프라인 변경 → WORKFLOW.md 멀티에이전트 프로토콜 적용. (DEV_GUIDE.md ★대규칙은 코드 작성 규칙, 실행 절차는 이 두 프로토콜이 우선)

---

## CLAUDE.md 업데이트 원칙

| 섹션 | 업데이트 시점 |
|------|-------------|
| `현재 스프린트` | TASKS.md와 동기화 (스프린트 완료/전환 시) |
| `완료된 것 [x]` | 스프린트 완료 시 |
| `작업 기본값/프로토콜` | 워크플로우 자체가 바뀔 때만 |

> 단순 버그 수정, 코드 개선 → 해당 폴더 `_GUIDE.md`에만 기록.
