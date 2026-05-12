# SPRINT 2026-05-12 — 평가 파이프라인 (E-005, E-006)

**날짜**: 2026-05-12
**상태**: completed
**테스트**: 1016 passed / 0 failed

---

## E-005: 1순위 구현 흐름 통합 테스트

E-001~E-004 구현 시 동시 완료됨. 별도 구현 불필요.

- `tests/integration/test_reliability_otto.py` (15 tests)
- `tests/integration/test_execution_feasibility.py` (16 tests)
- `tests/integration/test_uncertainty_propagation.py` (24 tests)

---

## E-006: 평가 파이프라인 구축

### 신규 파일
- `scripts/run_eval.py` — 평가 실행기 (CLI + 저장)
- `tests/unit/test_run_eval.py` — 38 tests

### 수정 파일
- `evaluation/baselines.py` — BnH/MACD/SMA 실제 시그널 + 수익률 계산 추가

### 주요 구현 내용

**evaluation/baselines.py** 추가 함수:
- `_ema(data, period)` — EMA 내부 계산
- `compute_macd_signal(bars)` — MACD(12/26/9), 1 or 0
- `compute_sma_signal(bars, period=20)` — SMA 크로스오버, 1 or 0
- `compute_baseline_returns(dates, prices, bars_by_date)` → {buy_and_hold, macd, sma}

**scripts/run_eval.py**:
- `load_portfolio_results(start, end)` — results/ 로드, r_real 없는 날짜 필터
- `extract_aapl_price/bars(data)` — stock_results에서 AAPL 추출
- `compute_metrics_for(returns, label)` — CR/ARR/SR/Sortino/MDD/WinRate
- `run_evaluation(start, end, output)` — 전체 실행 + JSON 저장 + 터미널 출력
- `_print_table(metrics)` — 비교표 출력

### 실행 결과 (AAPL+NVDA 2024-01~03)

```
Strategy            CR      ARR     SR     MDD
-----------------   -----   ------  -----  -----
Hybrid System       15.7%   88.3%   3.11   4.3%
Buy & Hold (AAPL)   -4.9%  -21.2%  -1.17  11.3%
MACD (12/26/9)      -3.0%  -13.3%  -1.85   3.4%
SMA (20)            -3.0%  -13.3%  -1.85   3.4%
```

---

## 완료 기준

- [x] 1016 passed / 0 failed
- [x] `python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31` 출력 확인
- [x] results/eval_2024-03-22.json 생성
