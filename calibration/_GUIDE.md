# calibration/ — Calibration 레이어 가이드

## 역할
Agent score의 rolling 정규화 (drift 방지).
Pipeline B/C 전용 어댑터(run_calibration.py)가 Propagation Audit + Reliability까지 통합 실행.

---

## 핵심 패턴

### AgentCalibrator — 4가지 방법
```python
cal.calibrate(field, raw, date, method="rolling_std")
# rolling_std: history ≥ 3이면 z-score → sigmoid
# shrinkage:  confidence 낮으면 neutral(0.5) 방향으로 수축
# clipping:   [clip_min, clip_max]로 clamp
# sector_relative: sector 평균 대비 상대값
```

### run_calibration.py — B/C 어댑터 3단계
```python
run_calibration_audit(stock_results, sim_results, run_date)
  → calibrate_stock_scores()   # 0~10 점수 → rolling std 정규화
  → audit_bc_propagation()     # tech/consensus 신호 채택률 추적
  → update_bc_reliability()    # agent EMA 신뢰도 업데이트
```

### Propagation Audit 판단 기준
```python
# tech 채택: score >= 7 → BUY, score <= 3 → SELL (중립 구간은 모두 허용)
# consensus 채택: bullish↔BUY, bearish↔SELL, neutral↔HOLD
```
**사고 이력**: 중립 구간(3<score<7) 미처리 시 false-negative 발생.

---

## 금지사항

### ❌ floor 값 코드에 하드코딩
```python
# 금지
if score < 0.35: ...
# 반드시 config 또는 ReliabilityState.floor 사용
```

### ❌ cold start reliability 0 초기화
cold start = 0.5. 0이면 첫 cycle에서 즉시 HARD_GATE됨.

### ❌ calibrate 없이 raw score 직접 Portfolio Manager 전달
항상 calibrate_stock_scores() 거친 후 주입.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `calibrator.py` | AgentCalibrator — rolling std / shrinkage / clipping / sector_relative |
| `run_calibration.py` | Pipeline B/C 어댑터 — Calibration + Audit + Reliability 통합 |

---

## 하네스

```
tests/unit/test_calibration.py
tests/unit/test_run_calibration.py
```

```bash
python scripts/harness.py calibration/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | calibrator.py | rolling_std 4가지 method 구현 |
| 2026-04-14 | run_calibration.py | 신규 (Phase 5): B/C용 Calibration+Audit+Reliability 통합. 36개 테스트 |
