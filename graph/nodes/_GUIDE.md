# graph/nodes/ — 노드 레이어 가이드

## 역할
LangGraph 그래프의 각 실행 단계. state를 받아 변환하고 반환.
Agent 호출, 데이터 흐름 제어, 로깅을 담당.

---

## 일간 노드 실행 순서
```
ingest → update_market_memory → signal_calibration → agent_reliability
→ risk_check → policy_selection → execution_feasibility → order → logging
```

## 주간 노드 실행 순서
```
weekly_market_analysis → weekly_strategy → propagation_audit → memory_consolidation
```

---

## 핵심 패턴

### state는 항상 dict copy 후 수정
```python
def some_node(state: SystemState) -> SystemState:
    updated = dict(state)   # ← 반드시 복사
    updated["some_field"] = new_value
    return updated
```
원본 state를 직접 수정하면 LangGraph 상태 추적 깨짐.

### next_node 명시
```python
updated["next_node"] = "DAILY_POST_EXECUTION_LOGGING"
```
라우팅은 edges에서 하지만 next_node로 의도를 명시.

### 멀티사이클 전환 시 reset_for_next_cycle() 사용
```python
from graph.state import reset_for_next_cycle
new_state = reset_for_next_cycle(prev_state, next_date)
# 사이클별 필드 초기화 + agent_reliability 등 cross-cycle 필드 보존
```

---

## 금지사항

### ❌ 노드 안에서 utility 공식 직접 구현
```python
# 금지 — policy.py에서 발생했던 이중화 문제
utility = 0.5 - 0.3 * risk_score - ...

# 반드시 utils/utility.py 사용
from utils.utility import compute_utility_from_state
utility = compute_utility_from_state(state, approval_status)
```
**사고 이력**: policy.py와 otto.py 두 곳에 다른 공식 존재 → 어느 게 공식인지 모호.

### ❌ 노드에서 LLM 직접 호출
노드는 orchestration 담당. LLM 호출은 agents/ 레이어에서만.

### ❌ 테스트에서 Orchestrator() 기본값으로 real LLM 호출
```python
# 금지 — 테스트가 실제 Anthropic API 호출해서 AuthenticationError 발생
Orchestrator()  # use_real_llm 기본값=False → 테스트에서는 placeholder

# 실제 실행 시에만
Orchestrator(use_real_llm=True)
```
**사고 이력**: SystemState에 _llm_analyst 추가 후 Orchestrator() 기본값이 real LLM이어서 테스트 전체가 API 호출 시도 → 401 에러.

### ❌ _llm_analyst 등 런타임 주입 키를 SystemState에서 누락
LangGraph는 TypedDict에 없는 키를 state에서 드롭함.
반드시 SystemState에 `_llm_analyst`, `_llm_decision`, `_polygon_fetcher` 선언 필요.
**사고 이력**: 미선언 시 orchestrator가 LLM 주입해도 policy 노드에서 None으로 읽혀 placeholder fallback.

### ❌ state 원본 직접 수정
```python
# 금지
state["risk_score"] = 0.8   # 원본 변경
# 반드시 updated = dict(state) 후 수정
```

### ❌ HARD_GATE agent 출력 그냥 통과시키기
```python
# agent_reliability.py
# HARD_GATE 판정 시 해당 agent output을 None으로 nulling해야 함
# 로그만 남기고 출력 통과시키면 오염된 데이터가 하류로 흐름
```
**사고 이력**: HARD_GATE가 로그만 남기고 실제 차단 안 해서 신뢰도 낮은 agent 출력이 Otto까지 전달.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `ingest.py` | 데이터 ingestion placeholder |
| `signal_calibration.py` | Emily/Bob 출력 calibration |
| `agent_reliability.py` | reliability 업데이트, HARD_GATE 적용 |
| `risk_check.py` | Dave 리스크 평가 실행 |
| `policy.py` | Otto 정책 선택, utility 계산 |
| `execution.py` | 실행 가능성 점수 계산 |
| `order.py` | PositionSizer로 주문 계획 생성 |
| `logging_node.py` | outcome 저장, r_real Polygon 조회 시도 |
| `weekly_strategy.py` | SimulatedTradingEngine + Polygon 연결 |

---

## 하네스

```
tests:
  - tests/integration/test_daily_cycle.py
  - tests/integration/test_e2e_fixes.py
  - tests/integration/test_multicycle.py
  - tests/integration/test_risk_alert.py
```

```bash
python scripts/harness.py graph/nodes/
python scripts/harness.py graph/nodes/policy.py
```

---

## GC 체크 패턴

```
forbidden:
  - pattern: "def.*utility.*=.*reward.*risk"
    files: "graph/nodes/policy.py"
    message: "utility 공식은 utils/utility.py에만 있어야 함"
  - pattern: "state\[.+\]\s*="
    message: "state 원본 직접 수정 금지 — updated = dict(state) 사용"
required:
  - "updated = dict(state)"
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-07 | ingest.py | placeholder → PolygonFetcher 실제 호출 연결 |
| 2026-04-07 | policy.py | placeholder → Emily→Bob→Dave→Otto 실제 에이전트 호출 |
| 2026-04-07 | policy.py | _compute_utility() 제거 → utils/utility.py 위임 |
| 2026-04-07 | order.py | PositionSizer 연결 — 실제 주문 수량/손절가 계산 |
| 2026-04-07 | logging_node.py | r_real Polygon T+1 조회 추가 (fallback: r_sim proxy) |
| 2026-04-06 | agent_reliability.py | HARD_GATE 실제 output nulling 수정 |
