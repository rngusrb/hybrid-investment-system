# simulation/ — 시뮬레이션 레이어 가이드

## 역할
Bob이 LLM으로 생성한 sim_metrics를 실제 백테스트로 교체.
Polygon 데이터 있으면 real, 없으면 synthetic fallback.

---

## 핵심 패턴

### data_source 필드 필수
```python
return {
    "return": ..., "sharpe": ...,
    "data_source": "real"   # 또는 "synthetic"
}
# 없으면 Bob이 synthetic 경고 붙일 수 없음
```

### mean-reversion z-score lookahead 방지
```python
# 금지 — 전체 시리즈 기준 z-score (미래 데이터 포함)
z = (price - price.mean()) / price.std()

# 반드시 — 현재까지의 rolling window만
z = (price - price.rolling(window).mean()) / price.rolling(window).std()
```
**사고 이력**: 전체 시리즈 기준 z-score로 lookahead bias 발생.

---

## 금지사항

### ❌ sim_metrics에 data_source 없이 반환
Bob의 _enrich_with_real_sim_metrics()가 synthetic 경고를 붙이려면
data_source 필드가 반드시 있어야 함.

### ❌ 미래 데이터 사용
sim_window.train_end 이후 데이터로 전략 계산 금지.
point-in-time constraint 항상 준수.

### ❌ mdd를 음수로 반환
```python
# 금지
return {"mdd": -0.08}   # 음수 MDD

# 반드시 양수 소수
return {"mdd": 0.08}    # 8% drawdown
```

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `trading_engine.py` | 오케스트레이터. Polygon/Synthetic 선택 |
| `strategy_executor.py` | 6개 전략 타입 → 포지션 시그널 |
| `synthetic_data.py` | API 없을 때 전략 품질 기반 합성 데이터 |

---

## 하네스

```
tests/unit/test_simulation.py
tests/unit/test_backtester.py
```

```bash
python scripts/harness.py simulation/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | trading_engine.py | data_source 필드 추가 |
| 2026-04-06 | strategy_executor.py | mean_reversion z-score rolling window 수정 |
| 2026-04-14 | backtester.py | 신규 (Phase 3 Bob): bars_to_returns / backtest_all / save_sim_result / format_sim_for_prompt. close=0 falsy 버그 수정. 30개 테스트 추가 |
