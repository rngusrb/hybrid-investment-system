# Functional Elements — Hybrid Multi-Agent Investment System v3.6
> 작성: 2026-04-02 | 테스트: 421/421 통과

---

## 1. 에이전트 (agents/)

| 에이전트 | 역할 | 핵심 제약 |
|---------|------|----------|
| **Emily** | 시장 분석 → feature space 변환 | technical_signal_state 독립 필드 필수 |
| **Bob** | 전략 후보 생성 + 백테스트 검증 | technical_confidence≥0.6이면 기술적 전략 1개 이상 필수 |
| **Dave** | 리스크 평가 | R_score>0.75이면 Risk Alert 자동 트리거 |
| **Otto** | 최종 정책 선택 | raw 데이터 직접 접근 frozenset으로 하드 차단 |

### BaseAgent 공통 로직
- retry 최대 3회, schema validation 실패 시 자동 재시도
- confidence_floor 미달 시 재시도
- 50KB 응답 사이즈 상한, path traversal 방어

### Bob 특수 로직
- **Bear Critique**: 전략별 failure_conditions ≥1 강제, 모든 candidate regime_fit≥0.85면 재시도
- **Real Sim Enrichment**: LLM 환각 sim_metrics를 실제 백테스트 결과로 교체 (trading_engine 있을 때)

---

## 2. 시뮬레이션 (simulation/)

| 컴포넌트 | 역할 |
|---------|------|
| **SyntheticDataProvider** | API 없을 때 전략 품질 기반 합성 수익률 생성 (seed 재현 가능) |
| **StrategyExecutor** | 6개 전략 타입 → 포지션 시그널 변환 |
| **SimulatedTradingEngine** | 백테스트 오케스트레이터. Polygon 있으면 실제 데이터, 없으면 Synthetic fallback |

### 6개 전략 타입
`momentum` / `mean_reversion` / `directional` / `hedged` / `market_neutral` / `defensive`

### 반환 metrics
`return` / `sharpe` / `sortino` / `mdd` / `turnover` / `hit_rate` (값 범위 clamp 적용)

---

## 3. 도구 (tools/)

| 도구 | 기능 | 외부 API |
|-----|------|---------|
| **TechnicalAnalyzer** | RSI(14), MACD(12/26/9), Bollinger(20,2σ), SMA, momentum signal | 없음 |
| **RiskAnalyzer** | VaR(95%), Portfolio Beta, HHI 섹터 집중도, Stress Test | 없음 |
| **SentimentAnalyzer** | 키워드 기반 감성 [-1,1], 시장 불확실성 [0,1] | 없음 |

---

## 4. 메모리 (memory/)

### 4개 메모리 계층

| 메모리 | 저장 내용 |
|--------|---------|
| **MarketMemory** | 시장 regime, OHLCV, 기술적 지표 |
| **StrategyMemory** | 전략 템플릿, 시뮬레이션 결과, 승인 이력 |
| **ReportsMemory** | 주간 리포트, 토론 결과, 신호 충돌 해소 |
| **DecisionJournal** | 정책 결정, 실제 결과, 오버라이드 이력 |

### Retrieval Validity Score
```
Score = Similarity × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability
```
- RecencyDecay: 90일 반감기 지수 감쇠
- RegimeMatch: 동일=1.0, 유사=0.5~0.7, 다름=0.2
- 10개 유사 regime pair 매핑
- floor(0.3) 미만 자동 폐기, top_k 최대 10

### Registry
- 모든 메모리/리트리버 싱글톤 인스턴스 중앙 관리

---

## 5. 그래프 (graph/)

### 일간 사이클 노드 흐름
```
INGEST → UPDATE_MARKET_MEMORY → SIGNAL_CALIBRATION → AGENT_RELIABILITY
→ RISK_CHECK → POLICY_SELECTION → EXECUTION_FEASIBILITY → ORDER_PLAN → LOGGING
```

### 주간 사이클 노드 흐름
```
MARKET_ANALYSIS_MEETING → STRATEGY_DEVELOPMENT_MEETING
→ PROPAGATION_AUDIT → MEMORY_CONSOLIDATION
```

### 이벤트 기반
```
RISK_ALERT_MEETING (risk_score > 0.75 시 일간 사이클 중 트리거)
```

### 스킵 가능 조건
- RISK_CHECK: risk < 0.3 + regime stable → 경량화
- 토론 sub-step: Emily confidence ≥ 0.85 → 간소화
- Signal conflict resolution: technical/macro 방향 일치 → 스킵

### SystemState 주요 필드
- 시간: current_date, cycle_type, is_week_end
- 에이전트 출력: emily_output, bob_output, dave_output, otto_output
- 제어: risk_alert_triggered, risk_score, technical_confidence
- 감사: propagation_audit_log, calibration_log, skip_log, retry_log

---

## 6. 미팅 (meetings/)

### Weekly Market Analysis Meeting
1. Bull/Bear 토론 (Emily confidence≥0.85면 간소화)
2. 신호 충돌 감지 (기술적 vs 거시, 방향 vs 편향 등 4종)
3. 기술적 지표 계산 (OHLCV 20봉 이상 있을 때)
4. DebateResolution + SignalConflictResolution → Ledger 기록

### Weekly Strategy Development Meeting
- Bob 후보 전략 검토 + rejection_reasons 생성
- BobToExecutionPacket 생성 (urgency, hedge_preference 계산)
- confidence < 0.45 전략 자동 거부

### Risk Alert Meeting (이벤트 기반)
```
RiskAdjustedUtility = (1-λ)*CombinedReward - λ*RiskReward
RiskReward = -a*risk_score - b*stress_severity + c*sentiment_safety - d*technical_reversal_penalty
```
- 긴급 조치: immediate_de_risk / reduce_exposure / add_hedge / consider_full_exit

---

## 7. 변환 계층 (transforms/)

| 변환 | 핵심 로직 |
|-----|---------|
| **emily_to_bob** | technical_signal_state 보존, event_risk_level 계산 |
| **bob_to_dave** | failure_conditions, technical_alignment 보존 |
| **bob_to_execution** | urgency = 1 - (sharpe*0.1 + regime_fit*0.3), hedge_preference |
| **all_to_otto** | 4개 packet 통합, raw 데이터 필드 주입 차단 |

---

## 8. 캘리브레이션 (calibration/)

4가지 방법 (AgentCalibrator 롤링 히스토리 max 20):
1. **rolling_std**: z-score → sigmoid → [0,1]
2. **shrinkage**: confidence 가중 중립(0.5) 블렌딩
3. **clipping**: [0,1] 하드 클리핑
4. **sector_relative**: 섹터 평균 대비 상대화

적용 대상: Emily(regime_confidence, technical_confidence), Bob(전략별 confidence), Dave(risk_score)

---

## 9. 전파 감사 (audit/)

감사 항목 (emily→bob, bob→dave, all→otto):

| 항목 | 측정 |
|------|-----|
| adopted_keyword_rate | 하위 키워드가 상위에 반영된 비율 |
| dropped_critical_signal_rate | 중요 신호 소실 비율 |
| has_contradiction | 전달 후 모순 발생 여부 |
| semantic_similarity_score | 소스-타겟 의미 유사도 |
| technical_signal_adoption_rate | 기술적 신호 채택률 |

---

## 10. 에이전트 신뢰도 (reliability/)

### ReliabilityState (5차원 EMA, decay=0.9)
| 차원 | 가중치 |
|-----|--------|
| decision_usefulness | 30% |
| contradiction_penalty | 20% |
| propagation_adoption | 20% |
| outcome_alignment | 20% |
| noise_penalty | 10% |

### Gating 결정
- FULL (≥ floor+0.1): 가중치 1.0
- DOWNWEIGHT (floor ~ floor+0.1): 가중치 = score/0.5
- HARD_GATE (< floor=0.35): 가중치 0.0

---

## 11. Shared Ledger (ledger/)

**저장 허용 (10가지)**:
final_market_report / technical_summary_packet / candidate_strategy_summary / risk_review_summary / debate_resolution / signal_conflict_resolution / final_policy_decision / execution_plan / risk_override_record / weekly_propagation_audit_summary

**저장 금지**: raw chain-of-thought, LLM 중간 추론, retrieval 전문, 토론 transcript

---

## 12. 데이터 (data/)

### PolygonFetcher
- point-in-time 강제: as_of 이후 날짜 → FUTURE_DATE_BLOCKED 플래그
- staleness 체크: 최신 바 ≥ 5일 전이면 STALE_DATA
- get_ohlcv() / get_news() — bars list 또는 articles list 반환

### DataManager
- preprocess_ohlcv(): NaN forward-fill, 이상치 탐지
- compute_returns(): return, log_return 컬럼 추가
- compute_realized_vol(): 롤링 std × √252 (연율화)
- get_sector(): GICS 기반 섹터 매핑

### MissingProtocol
6가지 MissingReason → confidence shrinkage 자동 계산:

| 사유 | shrinkage |
|-----|-----------|
| FUTURE_DATE_BLOCKED | 0.50 |
| API_FAILURE | 0.15 |
| INSUFFICIENT_HISTORY | 0.08 |
| STALE_DATA | 0.10 |
| NAN_VALUE | 0.05 |
| NO_NEWS | 0.02 |

---

## 13. 평가 (evaluation/)

### 12개 성과 지표
sharpe / sortino / max_drawdown / calmar / annualized_return / total_return / win_rate / turnover / policy_oscillation / technical_signal_adoption_rate / dropped_critical_signal_rate / semantic_similarity

### PointInTimeBacktester
- leakage 감지: data_date > as_of_date 차단
- BacktestResult: dates, returns, policies, metrics, leakage_violations

### 9개 Baseline 비교군
buy_and_hold / mean_variance / single_agent_llm / no_sim_trading / no_risk_alert / no_memory / no_calibration / no_propagation_audit / full_hybrid_system

### 12개 Ablation 변형
각 핵심 컴포넌트 제거 시 성능 저하 측정용

---

## 14. Dual Reward 수식

```
CombinedReward = w_sim * r_sim + w_real * r_real
w_sim = sigmoid(Σr_sim / Σ(r_sim + r_real + ε))  — 이동 윈도우

Utility = CombinedReward
        - λ1(0.3) * RiskScore
        - λ2(0.2) * ConstraintViolation
        - λ3(0.15) * MarketAlignmentPenalty
        - λ4(0.2) * ExecutionFeasibilityPenalty
        - λ5(0.15) * AgentReliabilityPenalty
```

---

## 15. 설정 (config/)

| 파일 | 주요 내용 |
|-----|---------|
| system_config.yaml | LLM provider/model, model_roles(decision/analyst), thresholds, cadence, Polygon API 키 |
| agent_config.yaml | 에이전트별 system_prompt_path, max_retries, confidence_floor |
| evaluation_config.yaml | baseline/ablation 설정, backtest 파라미터 |

### 주요 임계값 (system_config.yaml)
| 항목 | 값 |
|-----|-----|
| risk_alert | 0.75 |
| reliability_floor | 0.35 |
| calibration_shrinkage | 0.3 |
| retrieval_floor | 0.4 |
| execution_feasibility_floor | 0.5 |
| agent_confidence_floor | 0.45 |

---

## 미구현 / 향후 과제

| ID | 항목 | 비고 |
|----|------|------|
| M1 | Emily 4분할 (4 sub-agents) | 스키마 파괴적 변경 |
| M2 | 3-Trader 토론 | 신규 에이전트 3개 필요 |
| RL | 강화학습 루프 (PPO/SAC) | 프레임워크 전면 교체 |
| - | Memory DB 영속성 | 현재 in-memory, 재시작 시 초기화 |
| - | FAISS dense retrieval | 현재 token overlap 기반 |
| - | 백테스트 ticker 동적화 | 현재 SPY 고정 |
| - | 소셜미디어/옵션/재무제표 도구 | 외부 API 필요 |
| - | 실제 스케줄러 연결 | is_week_end() 구현됨, 연결 미완 |

---

*테스트 현황: 421 passed (unit 388 + integration 33) | 2026-04-02*
