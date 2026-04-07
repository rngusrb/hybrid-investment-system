# Walk-Forward 관점 논리 감사 보고서
> 작성: 2026-04-02 | 코드 직접 검증 완료

---

## 심각도 분류

| 심각도 | 의미 |
|--------|------|
| 🔴 Critical | 백테스트 결과 자체가 무효화됨 |
| 🟠 High | 수치가 크게 왜곡됨 |
| 🟡 Medium | 구조적으로 잘못됐지만 결과 왜곡은 제한적 |
| 🟢 Low | 개선 여지 있으나 치명적이지 않음 |

---

## 🔴 Critical 이슈

### 1. 합성 데이터의 순환 논리 (Circular Reasoning)
**파일:** `simulation/synthetic_provider.py` L24-31

```python
quality = (regime_fit + technical_alignment) / 2.0
drift = quality * 0.0008
returns = rng.normal(drift, vol, len(dates))
```

**문제:**
- `regime_fit`, `technical_alignment`는 Bob(LLM)이 생성한 전략 평가 점수
- 그 점수를 입력으로 합성 수익률을 만들고, 그 수익률로 sharpe/sortino를 계산해 Bob의 판단을 "검증"
- **결과:** Bob이 전략을 좋다고 판단하면 → 합성 데이터도 좋게 나옴 → 백테스트도 좋게 나옴 → 검증이 아닌 자기 확인(self-confirmation)
- 독립적 검증이 0%. Polygon API 연결 전까지는 실제로 아무것도 검증하지 않음

**영향:** Bob sim_metrics 수치 전체가 의미 없음 (Polygon 연결 후에만 의미 있음)

---

### 2. Sortino Ratio 공식 오류
**파일:** `evaluation/metrics.py` L40-42

```python
downside = [r for r in excess if r < 0]
downside_std = np.std(downside, ddof=1)  # ← 여기가 틀림
return float(mean_excess / downside_std * np.sqrt(periods_per_year))
```

**올바른 Sortino 공식:**
```
Downside Deviation = sqrt( mean( min(r, 0)^2 ) ) * sqrt(252)
Sortino = (mean_excess * 252) / Downside Deviation
```

**현재 코드의 문제:**
- `std(음수 수익률만)` ≠ `Downside Deviation`
- `std`는 평균을 빼고 분산을 구하지만 (목표수익률이 평균), Downside Deviation은 0을 기준(target=0)으로 제곱합
- 음수 수익률이 많을수록(나쁜 전략) `std(downside)` 분모가 커져서 Sortino가 오히려 낮아지는 역전 현상 발생 가능

**영향:** Sortino 수치가 전략 간 상대 비교에 사용될 수 없음

---

### 3. outcome_alignment 항구적 고정값 (신뢰도 업데이트 불능)
**파일:** `graph/nodes/agent_reliability.py` L62, L70, L78, L87

```python
outcome_alignment=0.5,   # 당일에는 outcome 미확정
```

모든 에이전트(Emily/Bob/Dave/Otto)에서 **매일 0.5로 고정**.

**문제:**
- 신뢰도 5차원 중 outcome_alignment(가중치 20%)가 영원히 0.5
- 즉, "전략이 실제로 수익을 냈는지"가 신뢰도에 전혀 반영되지 않음
- `logging_node.py`에서 전일 결과를 StrategyMemory에 저장하지만, 그 결과를 reliability_update에서 읽어오는 로직이 없음
- 에이전트가 계속 틀린 예측을 해도 신뢰도가 하락하지 않음

**영향:** Agent Reliability Gating 시스템이 실질적으로 작동하지 않음

---

### 4. Adaptive Weights 미연동 (Dual Reward 형식만 존재)
**파일:** `agents/otto.py` L96-112, `transforms/all_to_otto.py`

**문제:**
- `compute_adaptive_weights(reward_history)`가 구현되어 있으나 `reward_history`가 항상 빈 리스트
- `all_to_otto.py`에서 `recent_reward_summary: {}`로 고정 전달
- 결과: `w_sim=0.5, w_real=0.5` 로 항구적 고정
- "시뮬레이션 성과가 좋을수록 w_real 증가" 하는 적응형 가중치가 실제론 작동하지 않음

**영향:** QuantAgents 논문의 핵심인 Dual Reward 적응 메커니즘이 구현은 됐지만 데이터가 흐르지 않아 작동하지 않음

---

## 🟠 High 이슈

### 5. horizon_closed 즉시 True 처리
**파일:** `graph/nodes/logging_node.py` L83

```python
"horizon_closed": True,   # 이미 실행된 결과이므로 closed
```

**문제:**
- 당일 실행 직후 바로 horizon_closed=True
- `validity_scorer.py`에서 `horizon_closed=True`이면 OutcomeReliability=1.0 (최고 신뢰도)
- 실제 결과가 확인되지 않은 당일 기록이 즉시 최고 신뢰도 메모리로 저장됨
- 다음날 retrieval 시 이 기록이 높은 점수로 조회됨

**영향:** 검증 안 된 결과가 최고 신뢰도로 과거 케이스에 영향

---

### 6. Annualized Return 공식의 단기 과장 문제
**파일:** `evaluation/metrics.py` L15-21

```python
return float(total ** (periods_per_year / n) - 1)
```

**문제:**
- 30일(n=30) 백테스트: 연율화 지수 = 252/30 = 8.4
- 1% 총수익률 → 연율화 = 1.01^8.4 - 1 ≈ 8.8%
- 전략을 단기 윈도우로 백테스트하면 연율화 수익률이 극단적으로 과장됨
- sim_window가 60~90일짜리 단기면 모든 전략의 연율화 수치가 부풀려짐

**영향:** 단기 sim_window 전략의 연율화 수익률 신뢰 불가

---

## 🟡 Medium 이슈

### 7. Stress Test 결과 매번 동일 (seed=42 고정)
**파일:** `meetings/risk_alert.py` L51-56

```python
proxy_returns = (np.random.default_rng(42).normal(0, max(vol_proxy, 0.005), 30)).tolist()
stress_result = self._risk_analyzer.run_stress_test(proxy_returns)
```

**문제:**
- seed=42 고정 → 30일 proxy_returns 항상 동일한 난수 시퀀스
- 시장 상황이 달라도(고변동성/저변동성) stress severity가 `vol_proxy` 차이로만 달라짐
- Risk Alert Meeting의 주요 판단 근거가 사실상 `vol_proxy` 한 변수에만 의존

---

### 8. Dave Risk Score 검증 허용 오차 과도
**파일:** `agents/dave.py` L70-80

```python
if abs(computed - reported) > 0.25:
    return True, "inconsistent..."
```

**문제:**
- 0.25 허용 = 전체 범위(0~1)의 25%
- computed=0.50 (medium), reported=0.74 (high 임박) → 차이=0.24 → 통과
- 0.75 임계값 근처에서 0.01 차이가 Risk Alert 트리거 여부를 결정하는 시스템에서 ±0.25 허용은 과도

---

### 9. Calibration 신뢰도 파라미터 교차 오염
**파일:** `graph/nodes/calibration.py` L36-94

```python
# Emily technical signal 교정 시 regime_confidence를 confidence로 사용
confidence=float(rc or 0.5)   # rc = regime_confidence

# Dave는 항상 confidence=1.0 (shrinkage 없음)
confidence=1.0
```

**문제:**
- Emily의 reversal_risk, continuation_strength를 교정할 때 자기 confidence가 아닌 regime_confidence 사용
- Dave의 risk_score는 항상 shrinkage=0 → 불확실한 상황에서도 risk_score가 중립(0.5)으로 당겨지지 않음
- 즉, "데이터가 불확실할수록 중립으로" 라는 calibration 원칙이 Dave에서 작동하지 않음

---

### 10. mean_reversion 전략의 자기참조적 z-score
**파일:** `simulation/strategy_executor.py` L84-95

```python
recent = returns[i - lookback:i]
z = (returns[i - 1] - np.mean(recent)) / (np.std(recent) + 1e-8)
```

**문제:**
- `recent`에 `returns[i-1]`이 포함됨
- z-score 계산 시 자기 자신이 포함된 분포 대비 자기 자신을 정규화
- 통계적으로 약한 in-sample bias (look-ahead는 아니나 자기 참조)
- 올바른 방식: `recent = returns[i-lookback:i-1]` (직전 bar 제외)

---

### 11. DataQuality Score 미검증 outcome에 보너스
**파일:** `memory/retrieval/validity_scorer.py` L108-116

```python
present_optional = sum(1 for f in optional_fields if f in case)
return base + bonus  # 0.5 ~ 1.0
```

**문제:**
- optional_fields 중 "outcome" 필드가 있으면 quality 점수 상승
- 하지만 issue #5에서 outcome은 검증 없이 즉시 저장됨
- 검증 안 된 outcome이 있는 케이스가 없는 케이스보다 더 높은 quality score를 받는 역전 현상

---

## 🟢 Low 이슈

### 12. Sharpe의 무위험 수익률 처리 (사소하나 명시 필요)
**파일:** `evaluation/metrics.py` L28

```python
excess = [r - risk_free / periods_per_year for r in returns]
```

- `risk_free=0.0` 기본값이라 실질적 문제 없음
- 하지만 실제 사용 시 연간 무위험 수익률을 일별로 나눠야 함 → 현재 코드는 이미 그렇게 처리됨 ✅
- 단, risk_free 입력이 일별인지 연간인지 주석으로 명시 필요

### 13. 포지션 타이밍 오프셋 의존성
**파일:** `simulation/strategy_executor.py` L65-67

```python
pos = positions[i - 1]          # t-1 포지션
strat_returns.append(pos * raw_returns[i])  # t 수익률에 적용
```

- 현재 코드는 t-1 포지션을 t 수익률에 올바르게 적용 ✅
- 단, 외부에서 `positions[i] * returns[i]`로 잘못 사용하면 즉시 look-ahead bias 발생
- 취약한 인터페이스 설계 (사용자가 offset을 알아야 함)

---

## 요약 테이블

| # | 파일 | 심각도 | 카테고리 | 핵심 문제 |
|---|------|--------|---------|----------|
| 1 | synthetic_provider.py | 🔴 | 순환 논리 | LLM 평가값으로 검증용 데이터 생성 = 자기 확인 |
| 2 | metrics.py L40 | 🔴 | 수식 오류 | Sortino 분모가 downside deviation이 아닌 std |
| 3 | agent_reliability.py | 🔴 | 미연동 | outcome_alignment 항상 0.5, 실제 결과 미반영 |
| 4 | otto.py + all_to_otto.py | 🔴 | 미연동 | reward_history 비어있어 adaptive weights 항상 0.5/0.5 |
| 5 | logging_node.py L83 | 🟠 | 조기 확정 | 당일 결과 즉시 horizon_closed=True |
| 6 | metrics.py L15 | 🟠 | 수식 왜곡 | 단기 백테스트 연율화 극단적 과장 |
| 7 | risk_alert.py L51 | 🟡 | 고정값 | stress test seed=42 고정, 항상 동일 결과 |
| 8 | dave.py L70 | 🟡 | 검증 과소 | risk_score 허용 오차 ±0.25 과도 |
| 9 | calibration.py | 🟡 | 교차 오염 | Dave confidence=1.0 고정, shrinkage 무력화 |
| 10 | strategy_executor.py L89 | 🟡 | 자기참조 | mean_reversion z-score에 자기 자신 포함 |
| 11 | validity_scorer.py L108 | 🟡 | 역전 | 미검증 outcome 케이스가 더 높은 quality score |
| 12 | metrics.py L28 | 🟢 | 명세 부재 | risk_free 단위 주석 미기재 |
| 13 | strategy_executor.py L65 | 🟢 | 인터페이스 | offset 의존 취약 설계 |

---

## 수정 우선순위

**즉시 수정 (결과 무효화 수준):**
1. **Sortino 공식** (#2) — 수식 하나 교체
2. **Adaptive Weights 데이터 흐름** (#4) — reward_history 연동 또는 기능 비활성화 명시

**Walk-Forward 테스트 전 수정 필수:**
3. **Synthetic data 순환 논리** (#1) — Polygon API 없을 때는 백테스트 결과를 신뢰할 수 없음을 명시하거나 독립적 생성 방식 교체
4. **outcome_alignment 연동** (#3) — logging_node → reliability_update 데이터 흐름 연결

**성능 개선:**
5. **horizon_closed 즉시 확정** (#5) — 최소 1 사이클 후 closed 처리
6. **Dave shrinkage** (#9) — confidence=1.0 → 실제 uncertainty 반영

---

*이 보고서는 코드를 직접 읽고 검증한 결과임. 테스트 통과 여부와 무관하게 로직 레벨의 문제를 다룸.*
