# schemas/ — Pydantic 스키마 가이드

## 역할
시스템 전체의 데이터 계약(contract). Agent 출력, 변환 패킷, 감사 로그의
구조를 Pydantic v2로 정의. 스키마가 바뀌면 프롬프트도 반드시 같이 바꿔야 함.

---

## 핵심 패턴

### 상속 구조
```
AgentBaseOutput (base_schema.py)
  ├── EmilyOutput
  ├── BobOutput
  ├── DaveOutput
  └── OttoOutput

PacketBase (base_schema.py)
  ├── EmilyToBobPacket
  ├── BobToDavePacket
  ├── BobToExecutionPacket
  └── OttoPolicyPacket
```

### Literal 타입 사용 원칙
LLM이 자유롭게 쓸 수 없도록 Literal로 명시적 제약:
```python
market_regime: Literal["risk_on", "risk_off", "mixed", "fragile_rebound", "transition"]
trend_direction: Literal["up", "down", "mixed"]
approval_status: Literal["approved", "approved_with_modification", "conditional_approval", "rejected"]
```

### float 범위 제약
```python
risk_score: float = Field(ge=0.0, le=1.0)
mdd: float = Field(ge=0.0, le=1.0)   # 양수 소수 (0.08 = 8%)
macro_state.rates: float = Field(ge=-1.0, le=1.0)
```

---

## 금지사항

### ❌ 스키마만 바꾸고 프롬프트 안 바꾸기
```
schemas/bob_schema.py 변경
→ prompts/bob_system.md 도 반드시 동시에 수정
→ agents/bob.py _validate_output() alias도 확인
```
**사고 이력**: 스키마에 hit_rate 추가했는데 프롬프트엔 win_rate만 있어서
LLM이 win_rate 반환 → _SIM_METRICS_ALIASES로 교정 코드 추가해야 했음.

### ❌ OttoOutput에 raw data 관련 필드 추가
Otto는 공식 패킷만 받아야 함. raw_news, raw_ohlcv 등 절대 금지.
frozenset(_FORBIDDEN_RAW_FIELDS)에 추가하는 것도 금지.

### ❌ Optional 남발
필드가 실제로 없을 수 있는 게 아니면 Optional 쓰지 말 것.
LLM이 "없어도 되나보다"고 판단해 누락시킴.

### ❌ AgentBaseOutput의 date 필드 제거
모든 output에 date가 있어야 audit trail 추적 가능. 제거 금지.

---

## 파일 구조

| 파일 | 주요 클래스 |
|------|------------|
| `base_schema.py` | AgentBaseOutput, PacketBase, ControlSignal |
| `emily_schema.py` | EmilyOutput, TechnicalSignalState, EmilyToBobPacket |
| `bob_schema.py` | BobOutput, CandidateStrategy, SimMetrics, BobToDavePacket |
| `dave_schema.py` | DaveOutput, RiskComponents, StressTest, RiskConstraints |
| `otto_schema.py` | OttoOutput, AdaptiveWeights, Allocation, ExecutionPlan |
| `audit_schema.py` | NodeResult, PropagationAuditLog |
| `meeting_schema.py` | DebateResolution, WeeklyMarketReport 등 |

---

## 하네스

```
tests:
  - tests/unit/test_schemas.py
  - tests/unit/test_agents.py
```

```bash
python scripts/harness.py schemas/
```

---

## GC 체크 패턴

```
forbidden:
  - pattern: "raw_news|raw_ohlcv|raw_market_data"
    files: "schemas/otto_schema.py"
    message: "OttoOutput에 raw data 필드 금지"
required_sync:
  - source: "schemas/bob_schema.py"
    target: "prompts/bob_system.md"
    message: "스키마-프롬프트 동기화 필요"
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-07 | otto_schema.py | AdaptiveWeights.lookback_steps int 타입 확인 |
| 2026-04-06 | dave_schema.py | RiskComponents 4개 필드 [0,1] 범위 제약 추가 |
