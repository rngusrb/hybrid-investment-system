# evaluation/ — 평가 레이어 가이드

## 역할
전략 성과 측정, 백테스트, ablation 비교.
Point-in-time safe 백테스터 + 12개 성과 지표 + 9개 baseline 비교군.

---

## 핵심 패턴

### 12개 성과 지표
```python
sharpe / sortino / max_drawdown / calmar / annualized_return /
total_return / win_rate / turnover / policy_oscillation /
technical_signal_adoption_rate / dropped_critical_signal_rate / semantic_similarity
```

### Calmar: MDD=0 처리
```python
# MDD=0이면 0.0 반환 (분모 0 방지)
if mdd == 0:
    return 0.0
return annualized_return / mdd
```
**사고 이력**: MDD=0일 때 ZeroDivisionError 발생했던 버그 수정됨.

### Sortino: downside std만 사용
```python
# 음수 수익률만으로 std 계산
downside = returns[returns < 0]
downside_std = downside.std()
```
**사고 이력**: 전체 returns std 쓰다가 Sortino 공식 오류 수정됨.

### PointInTimeBacktester leakage 차단
```python
if data_date > as_of_date:
    leakage_violations.append(...)  # 자동 차단
```

---

## 금지사항

### ❌ Calmar에서 MDD=0일 때 division 시도
반드시 0 체크 후 0.0 반환.

### ❌ Sortino에서 전체 returns std 사용
downside(음수) returns만으로 계산해야 함.

### ❌ 백테스터에서 as_of_date 이후 데이터 사용
leakage_violations에 기록하고 해당 데이터 제외.

---

## 하네스

```
tests:
  - tests/unit/test_calibration.py
  - tests/unit/test_simulation.py
  - tests/unit/test_run_eval.py   ← E-006 평가 파이프라인 (baselines + run_eval)
```

**평가 실행 스크립트**
```bash
python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31
# → results/eval_YYYY-MM-DD.json 저장 + CR/ARR/SR/MDD 비교표 출력
```

```bash
python scripts/harness.py evaluation/
```

---
