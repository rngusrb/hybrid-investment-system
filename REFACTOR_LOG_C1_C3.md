# Refactor Log — C1 (Simulated Trading) + C3 (Tool Use)
> 작업 시작: 2026-04-02
> Director: Claude (검토·디버깅·품질 검증)
> Sub-agents: 항목별 병렬 코딩 에이전트

---

## 범위 재분석 결과

### C1 - Simulated Trading
**기존 판단:** ❌ 불가 (API 필요)
**수정 판단:** ✅ 가능 — 인프라 80% 존재

| 기존 컴포넌트 | 상태 |
|---|---|
| `evaluation/backtester.py` PointInTimeBacktester | ✅ 완성 |
| `data/polygon_fetcher.py` OHLCV fetcher | ✅ 완성 |
| `data/data_manager.py` DataManager | ✅ 완성 |
| `evaluation/metrics.py` compute_all_metrics | ✅ 완성 |

**없는 것:**
- `simulation/strategy_executor.py` — 전략 타입 → 매매 시그널 변환기
- `simulation/trading_engine.py` — 백테스터 오케스트레이터
- `simulation/synthetic_provider.py` — API 없을 때 합성 데이터 생성
- Bob 통합 — `sim_metrics` LLM 환각값 → 실제 백테스트 결과로 교체

### C3 - Tool Use
**기존 판단:** ❌ 불가 (26개 API 필요)
**수정 판단:** ✅ 18/26개 가능 — 기술/리스크/감성 도구는 외부 API 불필요

| 도구 유형 | 필요 라이브러리 | 상태 |
|---|---|---|
| Technical Indicators (RSI/MACD/BB/SMA) | pandas + numpy | 미구현 |
| Volatility Assessment + VaR | scipy + numpy | 미구현 |
| Portfolio Stress Testing | numpy 시나리오 | 미구현 |
| Sentiment Analysis | 키워드 기반 | 미구현 |
| News 데이터 | polygon_fetcher (이미 있음) | 미연결 |
| Vector 검색 | faiss-cpu (requirements에 있음) | 미사용 |
| 소셜미디어 | ❌ 외부 API 필요 | 제외 |
| 재무제표 상세 | ❌ 외부 API 필요 | 제외 |

---

## Round 1 — simulation/ 기반 인프라 (C1 코어)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `simulation/__init__.py` 생성
- `simulation/synthetic_provider.py` — API 없을 때 합성 OHLCV 데이터 생성
  - 전략 regime_fit + technical_alignment 기반 드리프트 계산
  - 재현 가능한 시드 사용
- `simulation/strategy_executor.py` — CandidateStrategy.type → 매매 시그널 변환
  - "momentum": SMA 크로스오버
  - "mean_reversion": RSI 기반
  - "directional": 트렌드 추종
  - "hedged": 롱/쇼트 혼합
  - "market_neutral": 중립
  - "defensive": 현금성 보유
- `simulation/trading_engine.py` — SimulatedTradingEngine
  - PointInTimeBacktester 래핑
  - 실제 metrics(sharpe/mdd/sortino/turnover/hit_rate) 반환
  - fetcher=None이면 SyntheticDataProvider 사용

### 파일
- `simulation/__init__.py` (신규)
- `simulation/synthetic_provider.py` (신규)
- `simulation/strategy_executor.py` (신규)
- `simulation/trading_engine.py` (신규)

---

## Round 2 — tools/ 기반 인프라 (C3 코어)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `tools/__init__.py` 생성
- `tools/technical.py` — 기술적 지표 계산
  - compute_rsi(df, period=14) → float
  - compute_macd(df) → dict(macd, signal, histogram)
  - compute_bollinger_bands(df, window=20) → dict(upper, middle, lower)
  - compute_sma(df, window) → pd.Series
  - compute_momentum_signal(df, window=20) → "buy"/"sell"/"hold"
- `tools/risk.py` — 리스크 도구
  - compute_var(returns, confidence=0.95) → float
  - compute_portfolio_beta(returns, benchmark) → float
  - compute_sector_concentration(holdings) → float
  - run_stress_test(returns, shock_scenarios) → dict(severity, worst_case)
- `tools/sentiment.py` — 감성 분석 (외부 API 없음)
  - compute_sentiment_score(texts) → float(-1~1)
  - compute_market_uncertainty(texts) → float(0~1)

### 파일
- `tools/__init__.py` (신규)
- `tools/technical.py` (신규)
- `tools/risk.py` (신규)
- `tools/sentiment.py` (신규)

---

## Round 3 — Bob에 TradingEngine 통합 (C1 연결)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `agents/bob.py` 수정
  - `__init__`에 `trading_engine` 선택적 파라미터 추가
  - LLM 호출 후 `_enrich_with_real_sim_metrics()` 실행
  - trading_engine=None이면 기존 LLM 값 그대로 사용 (하위 호환)
- `graph/nodes/weekly_strategy.py` 수정
  - BobAgent 생성 시 SimulatedTradingEngine 주입

### 파일
- `agents/bob.py` (수정)
- `graph/nodes/weekly_strategy.py` (수정)

---

## Round 4 — 미팅 노드에 Tools 연결 (C3 연결)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `meetings/risk_alert.py` 수정
  - Dave의 risk score 계산에 `tools/risk.py`의 run_stress_test, compute_var 실제 사용
  - Emily의 sentiment에 `tools/sentiment.py` 실제 사용
- `meetings/market_analysis.py` 수정
  - technical_summary_packet 구성 시 `tools/technical.py` 결과 포함
- `graph/nodes/risk_check.py` 수정
  - 기술적 지표 기반 risk 체크 추가

### 파일
- `meetings/risk_alert.py` (수정)
- `meetings/market_analysis.py` (수정)
- `graph/nodes/risk_check.py` (수정)

---

## Round 5 — 통합 테스트 + 엣지케이스 수정
**Status: ✅ DONE** | 테스트: 421/421 통과 (+98 신규)

### 목표
- 전체 pytest 421개+ 통과 확인 ✅ (323 기존 + 98 신규)
- C1: BobAgent sim_metrics 실제 값 검증 ✅ (sharpe=-0.8070, hit_rate=0.4402 — LLM 환각값 교체됨)
- C3: tools 함수 단위 테스트 추가 ✅ (test_simulation.py 40개, test_tools.py 58개)
- edge case: API 없을 때 SyntheticProvider 정상 동작 확인 ✅
- REFACTOR_LOG 최종 업데이트 ✅

---

## 진행 상황 요약

| Round | 항목 | Status | 테스트 |
|-------|------|--------|--------|
| 1 | simulation/ 인프라 | ✅ DONE | 323/323 |
| 2 | tools/ 인프라 | ✅ DONE | 323/323 |
| 3 | Bob-TradingEngine 통합 | ✅ DONE | 323/323 |
| 4 | 미팅 노드-Tools 연결 | ✅ DONE | 323/323 |
| 5 | 통합 테스트 + 수정 | ✅ **DONE** | **421/421** |
| **통합** | **전체 최종** | ✅ **PASS** | **421/421** |

---

## 변경 파일 목록

| 파일 | 유형 | Round |
|------|------|-------|
| `simulation/__init__.py` | 신규 | 1 |
| `simulation/synthetic_provider.py` | 신규 | 1 |
| `simulation/strategy_executor.py` | 신규 | 1 |
| `simulation/trading_engine.py` | 신규 | 1 |
| `tools/__init__.py` | 신규 | 2 |
| `tools/technical.py` | 신규 | 2 |
| `tools/risk.py` | 신규 | 2 |
| `tools/sentiment.py` | 신규 | 2 |
| `agents/bob.py` | 수정 | 3 |
| `graph/nodes/weekly_strategy.py` | 수정 | 3 |
| `meetings/risk_alert.py` | 수정 | 4 |
| `meetings/market_analysis.py` | 수정 | 4 |
| `graph/nodes/risk_check.py` | 수정 | 4 |
