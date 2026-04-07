# agents/ — Agent 레이어 가이드

## 역할
LLM을 호출해 구조화된 출력(Pydantic schema)을 생성하는 레이어.
Emily → Bob → Dave → Otto 순서로 시장 분석 → 전략 → 리스크 → 정책을 담당.

---

## 핵심 패턴

### _validate_output() — 모든 agent의 핵심 방어선
LLM이 반환한 raw dict를 Pydantic 검증 전에 자동 교정.
```python
def _validate_output(self, output: dict) -> dict:
    output = dict(output)
    # 1. alias 교정 (LLM이 잘못 쓰는 필드명 → 스키마 표준명)
    # 2. 타입 교정 (string → float, dict → list 등)
    # 3. 범위 교정 (mdd 음수 → abs, 퍼센트 → 소수)
    # 4. 누락 필드 기본값
    validated = XxxOutput(**output)
    return validated.model_dump()
```

### _should_retry() — 자동 교정으로 못 잡는 것만 재시도
ValidationError는 _validate_output()에서 잡고,
_should_retry()는 논리적 문제만 잡음.
```python
# 예) Bob: technical_confidence >= 0.6인데 technical-aligned candidate 없음
# 예) Dave: risk_constraints 자체가 없음
# 예) Otto: approval_status가 valid 값이 아님
```

### Agent별 alias 딕셔너리
LLM이 자주 잘못 반환하는 필드명을 클래스 변수로 관리:
- Bob: `_TYPE_ALIASES`, `_SIM_METRICS_ALIASES`
- Emily: `_TREND_ALIASES`, `_REGIME_ALIASES`, `_BIAS_ALIASES`
- Otto: `_ENTRY_ALIASES`, `_FREQ_ALIASES`

---

## 금지사항

### ❌ _validate_output() 없이 Pydantic 직접 호출
```python
# 금지
validated = BobOutput(**llm_output)
# LLM이 win_rate 반환하면 hit_rate 없다고 ValidationError
```

### ❌ LLM 수치를 검증 없이 신뢰
```python
# 금지 — Dave에서 발생한 실제 사고
risk_score = output["risk_score"]
# LLM이 컴포넌트 합계와 다른 수치 반환 → 파이프라인 전체 오염
# 반드시: risk_score = compute_risk_score(components)
```

### ❌ Otto에 raw data 필드 포함
```python
# 금지
input_packet["raw_market_data"] = ohlcv
otto.run(input_packet, state)
# OttoAgent._block_raw_data_access()가 ValueError 발생시킴
```

### ❌ _should_retry()에 auto-correction으로 해결 가능한 것 넣기
재시도는 API 비용이 발생함. 필드명 오류, 타입 오류, 범위 오류는
_validate_output()에서 교정하고, _should_retry()는 구조적으로
불가능한 케이스(필드 자체 없음, 논리 모순)만 처리.

### ❌ max_retries 초과 시 fallback 값 임의 생성
3회 실패하면 RuntimeError 발생 — 이걸 try/except로 잡아서
임의 값 넣지 말 것. 실패는 실패로 처리해야 파이프라인 오염 방지.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `base_agent.py` | retry 루프, JSON 파싱, 50KB 상한, path traversal 방어 |
| `emily.py` | 시장 분석. event_sensitivity_map dict→list 교정 포함 |
| `bob.py` | 전략 생성. Bear Critique, sim_metrics 실제 백테스트 교체 |
| `dave.py` | 리스크 평가. risk_score를 컴포넌트 가중합으로 강제 덮어씀 |
| `otto.py` | 정책 선택. raw data frozenset 차단. compute_utility()는 utils/utility.py 위임 |

---

## 하네스

```
tests:
  - tests/unit/test_agents.py
  - tests/integration/test_e2e_fixes.py
```

```bash
python scripts/harness.py agents/
python scripts/harness.py agents/bob.py
```

---

## GC 체크 패턴

```
forbidden:
  - pattern: "raw_market_data.*otto|otto.*raw_market_data"
    message: "Otto raw data 접근 차단"
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-07 | emily.py | _validate_output() 추가 — trend_direction alias, event_sensitivity_map dict→list, list 필드 보장 |
| 2026-04-07 | otto.py | _validate_output() 추가 — candidate_policies, adaptive_weights.lookback_steps, allocation 교정 |
| 2026-04-06 | bob.py | _SIM_METRICS_ALIASES 추가 — expected_return→return, win_rate→hit_rate 등 |
| 2026-04-06 | dave.py | _validate_output()에 risk_score 강제 덮어쓰기, risk_level lowercase, stress_test/risk_constraints 교정 |
