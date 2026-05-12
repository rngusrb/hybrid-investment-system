# 스프린트 아카이브: Pipeline A+B/C 통합 + 기술 부채 픽스
**기간**: 2026-04-17 ~ 2026-04-21
**결과**: 11개 태스크 전부 완료, 테스트 862 → 878 passed

---

## 스프린트 목표
run_loop.py가 Pipeline A (Emily/Bob/Dave/Otto)와 Pipeline B/C를 통합 실행하도록 연결.
Pipeline A는 orchestrator.py에만 존재하며 run_loop.py에서 호출되지 않는 dead code 상태였음.

---

## 완료 태스크 요약

### TASK-001: integration/emily_context.py
- Emily SPY 레짐 분석 결과 → Portfolio Manager 컨텍스트 주입
- `run_emily_for_context()`, `format_emily_for_prompt()` 구현
- 테스트: `tests/unit/test_integration_emily.py` (25개)

### TASK-002: integration/dave_context.py
- Portfolio Manager 출력 기반 포트폴리오 리스크 평가
- `build_dave_input()` (HHI sector_concentration, beta proxy, illiquidity), `run_dave_for_portfolio()`
- 테스트: `tests/unit/test_integration_dave.py` (~30개)

### TASK-003: integration/otto_gate.py
- 최종 승인 게이트: approved/approved_with_modification/conditional_approval/rejected
- `apply_otto_decision()` 4가지 분기 구현
- **핵심**: `compute_adaptive_weights()` 최초로 실제 reward_history와 연결 (strategy_memory.json 로드)
- 테스트: `tests/unit/test_integration_otto.py` (~36개)

### TASK-004: portfolio_pipeline.py — emily_context 파라미터 추가
- `run_portfolio_manager()` 시그니처에 `emily_context: str = ""` 추가
- memory_section 뒤, sim_section 앞에 주입

### TASK-005: run_loop.py — Emily/Dave/Otto 통합
- `run_one_cycle()`에 STEP A(Emily), STEP B(Dave), STEP C(Otto) 추가
- 각 스텝 try/except 래핑 — graceful degradation

### TASK-006: backtester.py — regime-aware 전략 선택
- `REGIME_STRATEGY_PREFERENCE` dict: risk_on→momentum, risk_off→defensive 등
- `_adjust_for_regime()`: Emily regime 기반 Sharpe 점수 보정 (±20% 이내)
- reversal_risk > 0.6 → 방어 전략 추가 +5% 보너스
- 테스트: `tests/unit/test_backtester.py` +13개

### TASK-007: Reliability 상태 영속화
- `results/reliability_state.json` 직렬화/복원
- `_skip_file_load` 플래그로 테스트 격리
- 테스트: `tests/unit/test_run_calibration.py` +8개

### TASK-008: Stress Test seed 날짜 기반 동적화
- `meetings/risk_alert.py` — 이미 `hashlib.md5` 날짜 기반 seed 적용됨 확인
- 테스트: `tests/integration/test_risk_alert.py` +2개 (재현성/날짜별 다른 seed 검증)

### TASK-009: Dave risk_score 허용 오차 ±0.05
- `agents/dave.py _validate_output()`: |computed - reported| ≤ 0.05이면 LLM 값 유지, > 0.05이면 overwrite + 경고 로그
- 테스트: `tests/unit/test_agents.py` +3개

### TASK-010: Dave Calibration shrinkage 활성화
- `graph/nodes/calibration.py`: method="clipping" → "shrinkage"
- confidence = `1.0 - stress_severity` (높은 stress = 낮은 confidence = 더 강한 중립 수축)
- 테스트: `tests/unit/test_graph_calibration_node.py` (신규, 4개)

### TASK-011: 증시 휴장일 T0 fallback
- `utils/forward_return.py`: T0 bars 없으면 T-5~T-1 fetch fallback, 직전 거래일 close 사용
- 테스트: `tests/unit/test_forward_return.py` (신규, 7개)

---

## 부수적 작업 (스프린트 중 발견/수정)

- `scripts/harness.py`: `integration/` 폴더 DEFAULT_MAP 추가
- `scripts/harness.py`: `calibration` 중복 키 버그 수정
- `scripts/harness.py`: 등록되지 않은 폴더 경고 메시지 추가

---

## 회고 메모

- TASKS.md 태스크 상세 섹션(테스트 피드백/최종 확인)이 대부분 비어있어 형식적 오버헤드
- 다음 스프린트부터: 완료 태스크는 한 줄 요약만 TASKS.md에 유지, 상세는 이 파일처럼 아카이브
