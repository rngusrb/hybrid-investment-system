# transforms/ — 변환 레이어 가이드

## 역할
Agent 출력을 다음 Agent가 받을 수 있는 패킷으로 변환.
정보 손실 없이 전달하되, 불필요한 raw 데이터는 필터링.

---

## 핵심 패턴

### 변환은 단방향, 순수 함수
```python
def transform_emily_to_bob(emily_output: dict, date: str) -> dict:
    # state 변경 없음, 부작용 없음
    # 입력 → 출력만
    return EmilyToBobPacket(...).model_dump()
```

### technical_signal_state 보존 필수
emily → bob 변환 시 technical_signal_state가 손실되면
Bob이 technical-aligned candidate를 판단할 수 없음.
```python
# emily_to_bob.py에서
technical_direction = ts.get("trend_direction", "mixed")
technical_confidence = ts.get("technical_confidence", 0.5)
```

### all_to_otto raw 데이터 차단
```python
# all_to_otto.py — 4개 packet 통합 시 raw 필드 주입 차단
_FORBIDDEN_FIELDS = {"raw_news", "raw_ohlcv", "raw_market_data", ...}
```

---

## 금지사항

### ❌ 변환 함수 안에서 LLM 호출
transforms는 순수 변환만. LLM 판단이 필요하면 agents/로.

### ❌ all_to_otto에서 raw market data 포함
```python
# 금지
otto_packet["ohlcv"] = raw_bars
otto_packet["news_articles"] = articles
# Otto는 공식 패킷 요약만 받아야 함
```

### ❌ technical_signal_state를 macro_state 안에 병합
Emily의 설계 원칙: technical signal은 macro와 독립적인 최상위 필드.
변환 시 중첩시키거나 합치면 Bob이 독립적으로 참조 불가.

### ❌ failure_conditions 드롭
bob → dave 변환 시 failure_conditions 필수 보존.
Dave가 리스크 평가에 사용.

---

## 파일 구조

| 파일 | 변환 내용 |
|------|----------|
| `emily_to_bob.py` | EmilyOutput → EmilyToBobPacket. technical_signal 보존 |
| `bob_to_dave.py` | BobOutput → BobToDavePacket. failure_conditions, technical_alignment 보존 |
| `bob_to_execution.py` | urgency = 1-(sharpe×0.1+regime_fit×0.3), hedge_preference 계산 |
| `all_to_otto.py` | 4개 packet → OttoInput. raw data 차단, reward_history 조회 |

---

## 하네스

```
tests:
  - tests/unit/test_transforms.py
```

```bash
python scripts/harness.py transforms/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | all_to_otto.py | reward_history strategy_memory 자동 조회 추가 |
