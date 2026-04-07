# Live E2E Test Results

**실행일시**: 2026-04-06 22:10:50  
**테스트 기준일**: 2024-01-19  
**LLM**: Anthropic claude-haiku-4-5 (analyst role)  
**데이터**: Polygon SPY  

## 결과 요약

| 체크 항목 | 결과 | 상세 |
|-----------|------|------|
| Polygon client init | ✅ PASS |  |
| OHLCV bars received | ✅ PASS | 139 bars in 0.8s |
| First bar has OHLCV | ✅ PASS | close=443.79 date=2023-07-03 |
| Last bar date ≤ as_of | ✅ PASS | last bar=2024-01-19 |
| run_strategy returns dict | ✅ PASS | {'return': 0.024, 'sharpe': 0.284, 'sortino': 0.4173, 'mdd': 0.0923, 'turnover': |
| data_source = real | ✅ PASS | real |
| sharpe finite | ✅ PASS | sharpe=0.2840 |
| mdd in [0,1] | ✅ PASS | mdd=0.0923 |
| hit_rate in [0,1] | ✅ PASS | hit_rate=0.4731 |
| News endpoint responds | ✅ PASS | 69 articles in 3.3s |
| Article has title | ✅ PASS | S&P 500's Record Highs, Davos AI Debate, Strong Consumer Data And Fed Bets: This |
| Emily LLM call succeeded | ✅ PASS | 4.6s |
| Emily market_regime | ✅ PASS | risk_on |
| Emily regime_confidence | ✅ PASS | 0.78 |
| Emily technical_signal_state present | ✅ PASS |  |
| Emily recommended_market_bias | ✅ PASS | selective_long |
| Emily→Bob packet built | ✅ PASS | regime=risk_on confidence=0.78 |
| Bob LLM call succeeded | ✅ PASS | 9.8s |
| Bob has candidates | ✅ PASS | 3 candidates |
| Bob selected_for_review | ✅ PASS | ['Tech Momentum Long', 'Selective Long Discretionary'] |
| Bob sim_metrics enriched | ✅ PASS |  |
| Bob→Dave packet built | ✅ PASS | strategy=Tech Momentum Long |
| Dave LLM call succeeded | ✅ PASS | 5.6s |
| Dave risk_score in [0,1] | ✅ PASS | 0.582 |
| Dave risk_constraints present | ✅ PASS |  |
| Dave stress_test present | ✅ PASS |  |
| all_to_otto transform | ✅ PASS | keys=['source_agent', 'target_agent', 'date', 'market_regime', 'regime_confidenc |
| Otto LLM call succeeded | ✅ PASS | 5.8s |
| Otto approval_status valid | ✅ PASS | conditional_approval |
| Otto selected_policy present | ✅ PASS | Tech Momentum Long |
| policy_selection runs | ✅ PASS |  |
| utility_score in output | ✅ PASS | utility=0.1438 |
| approval_status set | ✅ PASS | approved |
| logging_node runs | ✅ PASS |  |
| outcome stored in strategy_memory | ✅ PASS |  |
| r_real == r_sim | ✅ PASS | r_sim=0.0610 r_real=0.0610 |

**총 36개 체크 — PASS 36 / FAIL 0**

## 단계별 설명

| 단계 | 내용 |
|------|------|
| STEP 1 | Polygon API — SPY OHLCV 실제 데이터 수신 |
| STEP 2 | SimulatedTradingEngine — 실제 시세로 momentum 백테스트 |
| STEP 3 | Polygon API — SPY 뉴스 수신 |
| STEP 4 | Emily Agent — LLM 시장 분석 (regime, technical signal) |
| STEP 5 | Bob Agent — LLM 전략 선택 + 실제 백테스트 sim_metrics 교체 |
| STEP 6 | Dave Agent — LLM 리스크 평가 |
| STEP 7 | Otto Agent — LLM 최종 정책 결정 |
| STEP 8 | policy_selection 노드 (utility_score) + logging_node (r_real=r_sim) |