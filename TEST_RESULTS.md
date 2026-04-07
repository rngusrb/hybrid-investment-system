# 테스트 결과 보고서

**기준일**: 2026-04-06
**총 테스트**: 452개 passed / 0 failed
**실행 시간**: ~1.7s

---

## 전체 테스트 현황

| 파일 | 분류 | 테스트 수 | 결과 |
|------|------|-----------|------|
| `tests/unit/test_schemas.py` | Unit | 65 | ✅ PASS |
| `tests/unit/test_tools.py` | Unit | 58 | ✅ PASS |
| `tests/unit/test_llm_providers.py` | Unit | 48 | ✅ PASS |
| `tests/unit/test_simulation.py` | Unit | 40 | ✅ PASS |
| `tests/unit/test_calibration.py` | Unit | 39 | ✅ PASS |
| `tests/unit/test_data.py` | Unit | 35 | ✅ PASS |
| `tests/unit/test_agents.py` | Unit | 30 | ✅ PASS |
| `tests/unit/test_retrieval.py` | Unit | 28 | ✅ PASS |
| `tests/unit/test_transforms.py` | Unit | 27 | ✅ PASS |
| `tests/unit/test_reliability.py` | Unit | 19 | ✅ PASS |
| `tests/integration/test_e2e_fixes.py` | **E2E** | **31** | ✅ PASS |
| `tests/integration/test_daily_cycle.py` | Integration | 13 | ✅ PASS |
| `tests/integration/test_weekly_cycle.py` | Integration | 12 | ✅ PASS |
| `tests/integration/test_risk_alert.py` | Integration | 7 | ✅ PASS |
| **합계** | | **452** | ✅ **ALL PASS** |

---

## 이번 세션 수정 이슈 & E2E 검증 결과

| # | 심각도 | 이슈 | 수정 파일 | E2E 검증 테스트 | 결과 |
|---|--------|------|-----------|-----------------|------|
| 1 | Critical | StrategyMemory/MarketMemory 날짜 key 충돌 — 같은 날 다른 key 저장 시 덮어쓰기 | `memory/strategy_memory.py`<br>`memory/market_memory.py` | `TestStrategyMemoryKeyCollision` (3개)<br>`TestMarketMemoryKeyCollision` (2개) | ✅ |
| 2 | Critical | HARD_GATE 로그만 남기고 agent 출력 실제 차단 안 함 | `graph/nodes/agent_reliability.py` | `TestHardGateEnforcement` (3개) | ✅ |
| 3 | High | Otto `compute_utility()` 데드코드 — policy 결정에 미반영 | `graph/nodes/policy.py` | `TestOttoUtilityScore` (5개) | ✅ |
| 4 | High | `r_real = execution_feasibility - 0.5` — return과 무관한 값 사용 | `graph/nodes/logging_node.py` | `TestRRealSemantics` (2개) | ✅ |
| 5 | High | `outcome_alignment` 하드코딩 0.5 — 실제 결과 미반영 | `graph/nodes/agent_reliability.py` | `TestOutcomeAlignmentKeyLookup` (3개) | ✅ |
| 6 | Medium | Calmar ratio MDD=0 → 0.0 반환 (분모 0 처리 오류) | `evaluation/metrics.py` | `TestCalmarMDDZero` (3개) | ✅ |
| 7 | Medium | Risk component [0,1] 보장 없음 — 가중합 범위 초과 가능 | `agents/dave.py` | `TestRiskComponentNormalization` (4개) | ✅ |
| 8 | Medium | Sortino 공식 오류 — `std(negative)` 사용 | `evaluation/metrics.py` | `TestSortinoFormula` (3개) | ✅ |
| 9 | Medium | Mean-reversion z-score self-reference (lookahead) | `simulation/strategy_executor.py` | `tests/unit/test_simulation.py` (기존) | ✅ |
| 10 | Medium | `data_source` 필드 누락 — synthetic/real 구분 불가 | `simulation/trading_engine.py`<br>`agents/bob.py` | `tests/unit/test_simulation.py` (기존) | ✅ |

### 노드 연결 흐름 e2e 테스트

| 시나리오 | 테스트 | 결과 |
|----------|--------|------|
| risk_check → policy_selection → logging 연속 실행 | `test_risk_check_to_policy_to_logging_no_error` | ✅ |
| risk_score > 0.75 → risk_alert → policy = rejected | `test_risk_alert_triggers_rejected_policy` | ✅ |
| 3일 연속 logging → strategy_memory 3개 기록 (덮어쓰기 없음) | `test_three_day_strategy_memory_accumulates` | ✅ |

---

## 테스트 범위 한계 (미검증 영역)

| 영역 | 이유 | 비고 |
|------|------|------|
| 실제 LLM 호출 (Emily/Bob/Dave/Otto agents) | API key 필요, 비결정적 출력 | Mock/placeholder 로직으로 대체 검증 |
| 실제 Polygon API 데이터 수신 | 네트워크 의존, 실시간 데이터 | `config/system_config.yaml`에 key 설정됨, `test_simulation.py`에서 synthetic으로 검증 |
| LangGraph 전체 그래프 라우팅 | `orchestrator.run_daily_cycle()` 통합 테스트로 커버 | `test_daily_cycle.py` 13개 |
| `r_real` 실제 forward return 업데이트 | T+1 deferred 구현 미완 (TODO 명시) | 현재 r_real = r_sim proxy 사용 |
| 주간/일간 복합 멀티사이클 실행 | 상태 격리 필요, 복잡도 높음 | 향후 구현 가능 |

---

## 수정된 파일 목록

```
evaluation/metrics.py           — Sortino 공식, Calmar MDD=0 처리
simulation/strategy_executor.py — mean_reversion z-score 윈도우 수정
simulation/trading_engine.py    — data_source 필드 추가
agents/bob.py                   — sim_note synthetic 경고, data_source 처리
agents/dave.py                  — compute_risk_score component clamp 추가
graph/nodes/agent_reliability.py — HARD_GATE 출력 nulling, outcome_alignment key 수정
graph/nodes/policy.py           — compute_utility() 연결, utility_score 출력, downgrade 로직
graph/nodes/logging_node.py     — r_real = r_sim proxy
transforms/all_to_otto.py       — reward_history strategy_memory 자동 조회
memory/strategy_memory.py       — _store[key] 수정, get_by_date() 수정
memory/market_memory.py         — 동일 수정
config/system_config.yaml       — Polygon API key 추가
graph/nodes/weekly_strategy.py  — _make_trading_engine() Polygon fetcher 주입
meetings/risk_alert.py          — stress test seed 날짜 기반 변경
graph/nodes/calibration.py      — Dave confidence 동적 계산
memory/retrieval/validity_scorer.py — optional_fields bonus 수정
```
