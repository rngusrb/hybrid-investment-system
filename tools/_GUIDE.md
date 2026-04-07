# tools/ — 분석 도구 레이어 가이드

## 역할
외부 API 없이 순수 계산으로 기술적/리스크/감성 지표 산출.
Emily가 시장 분석 시 사용. 모두 무상태(stateless) 순수 함수.

---

## 3개 도구

### TechnicalAnalyzer
```python
RSI(14), MACD(12/26/9), Bollinger(20, 2σ), SMA, momentum_signal
```

### RiskAnalyzer
```python
VaR(95%), Portfolio Beta, HHI 섹터 집중도, Stress Test
```

### SentimentAnalyzer
```python
keyword 기반 감성 [-1, 1], 시장 불확실성 [0, 1]
```

---

## 핵심 패턴

### 최소 데이터 요구량 체크
```python
# OHLCV 20봉 미만이면 기술적 지표 계산 불가
if len(ohlcv) < 20:
    return {"error": "insufficient_data"}
```

### 반환값은 항상 float [범위 명시]
```python
rsi: float [0, 100]
sentiment: float [-1, 1]
uncertainty: float [0, 1]
var_95: float [0, 1]  # 양수 손실률
```

---

## 금지사항

### ❌ 외부 API 호출
tools/는 순수 계산만. 데이터는 호출부에서 주입.

### ❌ 상태 저장
도구 인스턴스가 내부 상태를 가지면 안 됨. 같은 입력 → 같은 출력 보장.

### ❌ NaN 반환
계산 불가 시 None 또는 {"error": "..."} 반환. NaN이 하위로 흐르면 스키마 검증 실패.

### ❌ OHLCV 데이터 직접 수정
입력 데이터는 read-only. copy 후 처리.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `technical_analyzer.py` | RSI, MACD, Bollinger, momentum |
| `risk_analyzer.py` | VaR, Beta, HHI, Stress |
| `sentiment_analyzer.py` | 키워드 감성, 불확실성 |
| `tool_registry.py` | 도구 등록 및 접근 |

---

## 하네스

```
tests:
  - tests/unit/test_tools.py
```

```bash
python scripts/harness.py tools/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-02 | tools/ | 초기 구현 완료 — 58개 테스트 통과 |
