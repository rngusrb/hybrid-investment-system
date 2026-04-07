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

## 파일 구조

| 파일 | 역할 |
|------|------|
| `metrics.py` | 12개 지표 계산 함수 |
| `backtester.py` | PointInTimeBacktester, BacktestResult |
| `baselines.py` | 9개 baseline 전략 정의 |
| `ablation.py` | 12개 ablation 변형, run_ablation_suite() |

---

## 하네스

```
tests:
  - tests/unit/test_calibration.py
  - tests/unit/test_simulation.py
```

```bash
python scripts/harness.py evaluation/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | metrics.py | Sortino 공식 수정 (downside std), Calmar MDD=0 처리 |
