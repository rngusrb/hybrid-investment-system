# SPRINT 2026-05-12 — 시스템 안정성 픽스 4종

**날짜**: 2026-05-12
**상태**: completed
**테스트**: 978 passed / 0 failed

---

## 배경

E-001~E-004 구현 이후 발견된 시스템적 관측/정합성 문제 4개를 사전 수정.
E-005 통합 테스트 전 안정화 목적.

---

## 완료 항목

### F-001: run_loop.py 반환 누락 필드 추가
**파일**: `scripts/run_loop.py`
**문제**: `run_one_cycle()` 반환 dict에 E-001~E-004에서 추가된 필드 3개 누락.
**수정**: `reliability_summary`, `execution_feasibility`, `uncertainty_mode` 추가.

### F-002: bc_backtester defensive 모드 uncertainty 충돌 방지
**파일**: `graph/nodes/bc_backtester.py`
**문제**: `risk_mode="defensive"` (Dave risk>0.7 재실행)에도 Emily confidence가 낮으면 `uncertainty_mode=True`/`lookback=30`이 적용되는 설계 충돌.
**수정**: `risk_mode == "defensive"` 시 `uncertainty_mode=False`, `lookback=20` 강제.

### F-003: bc_otto execution_feasibility stale 문제 해소
**파일**: `graph/nodes/bc_otto.py`, `tests/integration/test_execution_feasibility.py`, `tests/integration/test_uncertainty_propagation.py`
**문제**: bc_portfolio가 Dave 실행 전에 feasibility를 계산 → bc_otto가 읽는 값은 구버전 dave_output 기준.
**수정**: bc_otto 내에서 `_compute_execution_feasibility(portfolio, sim_results, dave_output)` 직접 재산출. 영향 테스트 2개 헬퍼 갱신.

### F-004: run_loop.py docstring 갱신
**파일**: `scripts/run_loop.py`
**문제**: 실행 순서 docstring에 `BC_RELIABILITY_UPDATE` 노드 누락.
**수정**: `ReliabilityUpdate` 추가.

---

## 완료 기준

- [x] 978 passed / 0 failed
- [x] _GUIDE.md 금지사항 위반 없음
