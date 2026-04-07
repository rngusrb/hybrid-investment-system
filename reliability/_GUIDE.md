# reliability/ — 에이전트 신뢰도 레이어 가이드

## 역할
각 agent의 신뢰도를 5차원 EMA로 추적. 신뢰도에 따라 출력 가중치 조정 또는 완전 차단.

---

## 핵심 패턴

### 5차원 ReliabilityState (EMA decay=0.9)
```
decision_usefulness    30%  — 실제 결정에 도움이 됐는가
contradiction_penalty  20%  — 모순 신호 발생 빈도
propagation_adoption   20%  — 하위 agent가 얼마나 채택했는가
outcome_alignment      20%  — 실제 결과와 얼마나 일치했는가
noise_penalty          10%  — 노이즈 신호 비율
```

### Gating 3단계
```python
FULL       (score >= floor+0.1 = 0.45) → weight = 1.0
DOWNWEIGHT (floor ~ floor+0.1)          → weight = score / 0.5
HARD_GATE  (score < floor = 0.35)       → weight = 0.0, output nulled
```

### HARD_GATE는 출력을 실제로 null 처리
```python
# agent_reliability.py
if decision == GatingDecision.HARD_GATE:
    state[f"{agent}_output"] = None   # 실제 nulling
```
**사고 이력**: 이전에 로그만 남기고 output 통과시켜서 신뢰도 낮은 agent 출력이 Otto까지 전달됨.

### outcome_alignment는 실제 결과 key로 조회
```python
# strategy_memory에서 실제 outcome 조회
outcome = strategy_memory.get_by_date(date)
r_real = outcome.get("value", {}).get("r_real", 0.5)
```
**사고 이력**: 하드코딩 0.5로 되어 있던 버그 수정됨.

---

## 금지사항

### ❌ HARD_GATE 판정 후 output 그냥 통과
반드시 해당 agent output을 None으로 설정.

### ❌ floor 값 코드에 하드코딩
```python
# 금지
if score < 0.35:   # 하드코딩

# 반드시 config에서
floor = config.get("reliability_floor", 0.35)
```

### ❌ cold start 시 reliability 0으로 초기화
cold start 기본값은 0.5. 0으로 시작하면 첫 번째 agent가 즉시 HARD_GATE됨.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `agent_reliability.py` | ReliabilityState, AgentReliabilityManager, GatingDecision |

---

## 하네스

```
tests:
  - tests/unit/test_reliability.py
```

```bash
python scripts/harness.py reliability/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | agent_reliability.py | HARD_GATE output nulling 수정, outcome_alignment key 수정 |
