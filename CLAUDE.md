# Hybrid Investment System — Claude 작업 지침

## 필독
작업 시작 전 반드시 읽을 것:
- **DEV_GUIDE.md** — 코드 작성 프로토콜, 데이터 흐름 지도, 전역 금지사항
- **해당 폴더/_GUIDE.md** — 폴더별 패턴, 금지사항, 하네스

## 완료된 것 (2026-04-07)

- [x] 파이프라인 A: Emily→Bob→Dave→Otto (LangGraph, SPY 고정)
- [x] 파이프라인 B: 4 Analysts→Researcher→Trader→RiskManager (개별 종목)
- [x] 파이프라인 C: B×N + Portfolio Manager (멀티 종목)
- [x] schemas/stock_schemas.py + portfolio_schemas.py
- [x] prompts/ (fundamental/sentiment/news/technical/researcher/trader/risk_manager/portfolio_manager)
- [x] scripts/_GUIDE.md + harness 전체 폴더 연결
- [x] 재무제표 룩어헤드 이중 필터 (period_of_report_date_lte + _financials_available)
- [x] live_e2e_bc_test.py (파이프라인 B/C 실제 실행 검증)
- [x] dashboard/ (app.py + 3 pages + formatters.py)

## 다음 목표 — 단계별 구현 (2026-04-14)

### 설계 기반
- **1.pdf TradingAgents**: 역할 분업 + 토론 구조 → 파이프라인 B/C가 이미 구현
- **2.pdf QuantAgents**: 루프 + 메모리 + Bob 시뮬레이션 → 미구현
- **CLAUDE_CODE_BRIEFING.md**: v3.6 최종 설계 목표 (Emily/Bob/Dave/Otto + 3 Meetings + Memory + LangGraph)

### Phase 1 — 루프 ✅ 완료 (2026-04-14)
- [x] `scripts/run_loop.py` — 날짜 범위 반복 실행 + `results/YYYY-MM-DD/portfolio.json` 저장
- [x] `tests/unit/test_run_loop.py` — 26개 단위 테스트 (날짜 생성 / 저장-로드 / 스키마)
- weekly(금요일) / daily(영업일) / resume / dry-run 지원

### Phase 2 — 메모리 ✅ 완료 (2026-04-14)
- [x] `memory/run_memory.py` — results/ 기반 영속 메모리 (find_prev_dates / build_context / format_for_prompt)
- [x] `portfolio_pipeline.run_portfolio_manager()` — memory_context 파라미터 추가
- [x] `run_loop.run_one_cycle()` — 메모리 자동 로드 + Portfolio Manager에 주입
- [x] `tests/unit/test_run_memory.py` — 24개 단위 테스트 (point-in-time 안전, 연속 streak, 컨텍스트 포맷)

### Phase 3 — Bob (시뮬레이션) ✅ 완료 (2026-04-14)
- [x] `simulation/backtester.py` — bars 기반 6개 전략 Pool 백테스트 (추가 API 호출 없음)
- [x] `results/strategy_memory.json` — 전략 성과 영속 저장 (point-in-time 안전)
- [x] `run_loop.run_one_cycle()` — backtester 자동 실행 + sim_context → Portfolio Manager 주입
- [x] `portfolio_pipeline.run_portfolio_manager()` — sim_context 파라미터 추가
- [x] `tests/unit/test_backtester.py` — 30개 단위 테스트 (close=0 falsy 버그 포함)

### Phase 4 — 3 Meetings ✅ 완료 (2026-04-14)
- [x] `meetings/run_meetings.py` — Pipeline B/C용 MAM/SDM/RAM 어댑터 (LLM 추가 호출 없음)
- [x] `run_loop.run_one_cycle()` — meetings 자동 실행 + meetings_context → Portfolio Manager 주입
- [x] `portfolio_pipeline.run_portfolio_manager()` — meetings_context 파라미터 추가
- [x] `tests/unit/test_run_meetings.py` — 40개 단위 테스트
- MAM: Bull/Bear 집계 + 시그널 충돌 감지 (action_changed / tech-fund 괴리)
- SDM: 전략 Pool 실행 힌트 (high_turnover / low_sharpe / high_mdd)
- RAM: 이벤트 기반 (max_risk > 0.75) 긴급 조치 결정

### Phase 5 — Calibration / Audit / Reliability ✅ 완료 (2026-04-14)
- [x] `calibration/run_calibration.py` — Pipeline B/C용 Calibration+Audit+Reliability 통합 어댑터
- [x] `run_loop.run_one_cycle()` — cal 자동 실행 + calibration_context → Portfolio Manager 주입
- [x] `portfolio_pipeline.run_portfolio_manager()` — calibration_context 파라미터 추가
- [x] `calibration/_GUIDE.md` 신규 생성
- [x] `tests/unit/test_run_calibration.py` — 36개 단위 테스트
- Calibration: 0~10 점수 → rolling std 정규화 (drift 방지)
- Propagation Audit: tech/consensus 신호 채택률 추적 (dropped_signal_count)
- Reliability: 5차원 EMA — action_changed / confidence / prop_score 기반 신뢰도 갱신 + Gating

### Phase 6 — 메모리 루프 닫기 ✅ 완료 (2026-04-14)
- [x] `memory/outcome_filler._update_strategy_memory()` — r_real 채워질 때 `results/strategy_memory.json`도 업데이트 (r_real, performance_score, outcome_reliability)
- [x] `memory/retrieval/validity_scorer.compute_outcome_reliability()` — r_real_source 기반 신뢰도 + r_real 크기 기반 성과 반영 (r_sim_proxy→0.5, <0→0.65, 0~2%→0.85, ≥2%→1.0)
- [x] `memory/run_memory._sort_results_verified_first()` — verified(polygon_weighted) 케이스 우선 + r_real 내림차순 정렬 (이미 구현됨)
- [x] `tests/unit/test_outcome_filler.py` — 6개 테스트 추가 (TestUpdateStrategyMemory)
- 완료 기준 달성: r_real ≠ r_sim이 실제로 출력됨 (예: 2024-01-05 r_real=0.0643)
- 전략 성과 기반 메모리 품질 정렬 동작 확인

### 목표 구조 (최종)
```
[run_loop.py] 날짜 범위 실행
  ↓
매 주기: fetch → Emily → Bob(시뮬) → Dave → Otto
  ↓                            ↑
  └── results/ 저장 → memory/ 로드 ──┘
  ↓
주간: MAM → SDM → (RAM 조건부)
  ↓
T+7 후: outcome_filler → r_real 채우기 → strategy_memory 업데이트
```

## CLAUDE.md 업데이트 원칙

| 섹션 | 업데이트 시점 |
|------|-------------|
| `완료된 것 [x]` | 기능/마일스톤 완료 시 체크 |
| `현재 업그레이드 목표` | 새 목표 추가 또는 목표 변경 시 |
| `작업 프로토콜` | 워크플로우 자체가 바뀔 때 |

> 단순 버그 수정, 코드 개선은 해당 폴더 `_GUIDE.md`에만 기록. CLAUDE.md는 건드리지 않음.

## 작업 기본값
- 테스트 수반 작업: **전부 통과할 때까지 루프 반복** (max 10회)
- 중간 확인 요청 금지 — 막히면 `_GUIDE.md` 규칙 갱신 후 재시도
- 10회 초과 시에만 현황 보고 후 대기

## 작업 프로토콜 (매 작업마다)
```
1. DEV_GUIDE.md 확인
2. 해당 폴더 _GUIDE.md 확인
3. python scripts/harness.py <폴더>/ 실행 (현재 상태 파악)
4. 코드 수정
5. python scripts/harness.py <폴더>/ 재실행 (검증)
6. 실패 시 → 원인 파악 → 코드 수정 → _GUIDE.md 금지사항 갱신 → 5번으로
7. 통과 시 → _GUIDE.md 최근변경 업데이트 → 완료
```

> 6번에서 _GUIDE.md 갱신 없이 "완료" 선언 금지.
