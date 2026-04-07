# DESIGN_SPEC_v3.6.md
# 코덱스용 최종 통합 설계 명령서 v3.6

**프로젝트명**: Hybrid Multi-Agent Investment System v3.6

**부제**: TradingAgents × QuantAgents × Expert Investment Teams with Temporal Cadence, Dual Reward Policy, Retrieval-Grounded Meetings, Technical Signal Priority, Agent Gating, and Structured Debate-Controlled Execution

---

## 0. 이 버전의 핵심 수정 목표

기존 v3.5의 장점은 유지하되, 아래 5가지를 반드시 강화하라.

- Expert Investment Teams 논문에서 드러난 핵심처럼, **fine-grained task contract 자체를 시스템 중심축**으로 둘 것
- **Technical signal이 단순 feature가 아니라 상위 의사결정에 실제 반영되는 우선 신호**임을 명시할 것
- 모든 specialist agent를 항상 동일하게 신뢰하지 말고, **regime별 conditional gating과 reliability tracking**을 둘 것
- meeting output이 다음 단계 input으로 들어갈 때 transformation interface뿐 아니라 **propagation audit**도 둘 것
- score 기반 의사결정에는 **calibration layer**를 두어 scale drift와 noise amplification을 막을 것

추가로, v3.5에서 부족했던 아래 4가지를 보강한다.

- retrieval은 유지하되, task contract와 transformation보다 앞서는 핵심 엔진처럼 보이지 않게 **우선순위를 재정렬**할 것
- bullish / bearish debate를 단순 찬반 구조가 아니라 **heterogeneous signal conflict resolution**으로 확장할 것
- 각 agent 산출물이 실제로 상위 의사결정에 반영되었는지 **semantic propagation audit**으로 점검할 것
- **empty-case protocol과 missing-data protocol**을 명시하여 재현성과 운영성을 높일 것

이 시스템은 더 이상 "좋은 설계 초안"이 아니라, **재현 가능한 연구형 시스템 설계서**여야 한다.

---

## 1. 최종 시스템 정의

이 시스템은 다음 문장을 만족해야 한다.

> "TradingAgents의 structured organizational workflow와 shared state ledger, QuantAgents의 meeting-driven operating loop와 explicit memory modules, 그리고 Expert Investment Teams의 fine-grained task contracts를 통합하여, 시장 분석 → 전략 시뮬레이션 → 리스크 경보 → 최종 정책 선택 → 실행 계획 확정의 전 과정을 시간축 위의 구조화된 상태 전이와 dual reward learning으로 수행하는 멀티에이전트 투자 의사결정 시스템."

핵심은 다음 네 가지다.

**첫째**, 이 시스템은 단순 agent chat이 아니라 **조직형 workflow**여야 한다.

**둘째**, 이 시스템은 단순 과거 반성형 회고가 아니라 **simulated trading 기반 forward-looking policy evaluation**을 포함해야 한다.

**셋째**, 이 시스템은 raw 대화 기록이 아니라 **official report, risk summary, policy packet, execution plan 중심**으로 상태가 전이되어야 한다. 이는 TradingAgents가 강조한 structured communication protocol과 동일한 문제의식을 따른다.

**넷째**, 이 시스템은 **fine-grained task contract를 명시적으로 가져야 한다.** Expert Investment Teams 논문이 강조한 핵심은 agent 수 자체보다, 실제 투자 실무에 가까운 세분화된 업무 계약이 성능과 해석 가능성을 높인다는 점이다. 따라서 본 시스템에서도 역할명보다 업무 항목, 평가 차원, 전달 포맷, 상위 의사결정 반영 규칙이 더 중요하다.

---

## 2. 이 시스템이 재현하려는 QuantAgents의 본질

이 시스템은 QuantAgents의 외형만 모방하지 말고, 아래 본질을 반드시 유지해야 한다.

**첫째**, 에이전트는 4명이다. Bob, Dave, Emily, Otto를 유지한다. 역할은 simulated trading analyst, risk control analyst, market news analyst, manager에 대응한다.

**둘째**, 회의는 3종이다. Market Analysis Meeting, Strategy Development Meeting, Risk Alert Meeting이다. 이 meeting은 단순 설명 텍스트 생성이 아니라, 실제 조직의 의사결정 프로토콜처럼 입력 → 분석 → 구조화 출력 → 메모리 업데이트 → 다음 단계 전이를 수행해야 한다.

**셋째**, 학습은 사후반성만으로 끝나면 안 된다. simulated trading을 통해 미래 전략의 적합성을 사전 검토하고, 실제 보상과 시뮬레이션 보상을 함께 사용해야 한다. 이것이 QuantAgents가 기존 post-reflection형 금융 에이전트와 다른 핵심이다.

**넷째**, risk는 별도 회의로 다뤄야 한다. QuantAgents는 risk score가 일정 threshold를 넘을 때 Risk Alert Meeting을 호출한다. 따라서 risk는 단순 report field가 아니라 **상태 머신을 바꾸는 이벤트**여야 한다.

**다섯째**, debate는 장식이 아니라 **편향 통제 장치**다. TradingAgents의 researcher debate 구조를 참고하여, market interpretation과 strategy selection 과정에서는 반드시 bull case / bear case 충돌 후 structured resolution이 남아야 한다. 자연어 토론 전문을 다 저장할 필요는 없지만, 논쟁 결과는 official state로 남겨야 한다.

**여섯째**, specialist agent는 항상 모두 도움이 되는 존재로 가정하지 말아야 한다. Expert Investment Teams 논문은 일부 agent, 특히 Technical signal이 상위 의사결정 품질 향상에 강하게 기여하는 반면, 다른 일부 agent는 noise나 redundancy를 유발할 가능성도 시사한다. 따라서 본 시스템은 multi-agent diversity를 무조건 선으로 두지 않고, **conditional gating과 reliability tracking**을 포함해야 한다.

---

## 3. 운영 시간축 정의

v3.5의 cadence 구조는 유지하되, 각 cycle이 어떤 종류의 fine-grained task contract를 실행하는지 더 명시적으로 연결한다.

### 3.1 의사결정 시간 단위

#### Daily Cycle
매 거래일마다 수행한다.

목적:
- 현재 포지션 유지 / 미세 조정 / execution 관리 / risk threshold 점검
- 전일 선택된 policy의 실행 가능성 점검
- execution 결과 로그 기록
- specialist signal calibration drift 점검

#### Weekly Cycle
매주 마지막 거래일 이후 수행한다.

목적:
- Weekly Market Analysis Meeting
- Weekly Strategy Development Meeting
- 전략 재평가
- memory consolidation
- agent reliability update
- propagation audit 수행

이 cadence는 QuantAgents 논문에서 market analysis meeting과 strategy development meeting이 weekly로 돌아가는 구조를 반영한다.

#### Event-Driven Cycle
아래 조건에서 즉시 수행한다.

- risk_score > threshold
- volatility shock
- liquidity collapse
- major macro event
- severe sentiment shock
- technical reversal shock
- execution feasibility collapse

목적:
- Risk Alert Meeting
- 강제 de-risking 또는 policy override
- agent gating 재계산

### 3.2 실행 granularity 보강

v3.6에서도 Daily Cycle을 단순 execution 한 줄로 두지 않는다. 실행 단계는 아래처럼 세분화한다.

- pre-execution check
- execution feasibility review
- order/action generation
- post-execution logging
- execution slippage attribution
- next-day calibration update

이렇게 해야 policy와 실제 action 사이의 explainability를 유지할 수 있다.

---

## 4. 상태 머신 재정의

상태 머신은 단순 나열이 아니라 time cadence, reliability control, propagation audit와 연결되어야 한다.

### 4.1 상태 목록

- `INGEST_DAILY_DATA`
- `UPDATE_MARKET_MEMORY`
- `DAILY_SIGNAL_CALIBRATION`
- `DAILY_AGENT_RELIABILITY_UPDATE`
- `DAILY_RISK_CHECK`
- `DAILY_POLICY_SELECTION`
- `DAILY_EXECUTION_FEASIBILITY_CHECK`
- `DAILY_ORDER_PLAN_GENERATION`
- `DAILY_POST_EXECUTION_LOGGING`
- `WEEKLY_MARKET_ANALYSIS_MEETING`
- `WEEKLY_STRATEGY_DEVELOPMENT_MEETING`
- `WEEKLY_PROPAGATION_AUDIT`
- `POLICY_SELECTION`
- `EXECUTION_PLAN_GENERATION`
- `MEMORY_CONSOLIDATION`
- `RISK_ALERT_MEETING`
- `BACKTEST_EVALUATION`
- `WAIT_NEXT_BAR`

### 4.2 일간 전이 규칙

1. 거래일 시작 시 `INGEST_DAILY_DATA`
2. 시장 데이터 / 뉴스 / 포트폴리오 상태 반영 후 `UPDATE_MARKET_MEMORY`
3. 이후 `DAILY_SIGNAL_CALIBRATION` 수행
4. Dave가 `DAILY_RISK_CHECK`
5. risk threshold 미초과면 `DAILY_POLICY_SELECTION`
6. risk threshold 초과면 즉시 `RISK_ALERT_MEETING`
7. 정책 확정 후 `DAILY_EXECUTION_FEASIBILITY_CHECK` 수행
8. 실행 가능한 경우 `DAILY_ORDER_PLAN_GENERATION`
9. 거래 종료 후 `DAILY_POST_EXECUTION_LOGGING`과 memory/ledger 기록
10. 주말 또는 주간 마감 시 `WEEKLY_MARKET_ANALYSIS_MEETING`, `WEEKLY_STRATEGY_DEVELOPMENT_MEETING`, `WEEKLY_PROPAGATION_AUDIT` 수행

### 4.3 주간 전이 규칙

주간 종료 시 반드시 아래 순서로 진행한다.

1. Emily 중심 시장 상태 정리
2. Technical sub-signal summary 생성
3. bull / bear 및 signal conflict resolution sub-step 수행
4. Bob 중심 전략 시뮬레이션
5. Dave 중심 전략 리스크 점검
6. Otto의 정책 선택
7. execution plan generation
8. propagation audit
9. memory consolidation
10. 다음 주 실거래 policy 확정

### 4.4 uncertainty 전이 규칙

각 상태는 단순 결과만 넘기지 말고 confidence / uncertainty control signal도 함께 넘긴다.

- Emily uncertainty↑ → Bob은 candidate strategy diversity↑
- Technical confidence↑ + macro uncertainty↑ → Bob은 selective momentum / hedged trend 계열 우선
- Bob confidence↓ → Dave는 stress severity 가중
- Dave risk_score↑ + Emily uncertainty↑ → Otto는 exposure shrinkage 적용
- agent reliability↓ → 해당 agent output 가중치 축소 또는 conditional skip

---

## 5. 메모리 재정의: 저장소가 아니라 retrieval substrate

v3.5의 retrieval 구조는 유지하되, v3.6에서는 priority order를 명확히 한다.

**의사결정 우선순위:**

1. fine-grained task contract
2. structured transformation interface
3. calibration + propagation audit
4. retrieval-grounded augmentation
5. adaptive reward refinement

즉, retrieval은 핵심 지원 계층이지 task contract를 대체하는 엔진이 아니다.

### 5.1 Memory 계층

#### Market Memory
저장:
- daily OHLCV
- factor snapshots
- technical indicators
- realized volatility
- event windows
- macro snapshots
- sector rotation signatures
- cross-horizon momentum states
- reversal risk markers

#### Reports Memory
저장:
- weekly market reports
- regime summaries
- event interpretations
- sector outlooks
- prior unresolved risks
- debate resolutions
- signal conflict resolutions

#### Strategy Memory
저장:
- strategy templates
- historical simulation outcomes
- strategy-context fit summaries
- failure conditions
- optimization notes
- approval / rejection reasons

#### Decision Journal
저장:
- selected policy
- actual outcome after horizon h
- reward attribution
- ex-post review
- policy drift
- override history
- execution slippage / feasibility notes
- propagation audit summary

### 5.2 Retrieval query 정의

#### Emily retrieval query
입력: macro regime, sector dispersion, major headlines, technical trend state

출력:
- 과거 유사 macro/regime 사례
- 과거 event interpretation report
- 유사 sector rotation pattern
- 유사 technical reversal / continuation case

#### Bob retrieval query
입력: market regime, trend state, volatility state, portfolio posture, technical-confidence

출력:
- 유사 regime에서 성과가 좋았던 전략
- 실패했던 전략과 failure condition
- strategy optimization note
- technical-aligned strategy template

#### Dave retrieval query
입력: portfolio beta, liquidity, concentration, realized vol, current shock state

출력:
- 유사 drawdown episode
- 유사 sector concentration failure case
- 과거 de-risking effectiveness record

#### Otto retrieval query
입력: Emily/Bob/Dave 요약 결과 + recent reward history + agent reliability summary

출력:
- 유사 상황에서 최종 policy와 실제 성과
- policy drift 사례
- simulated vs real reward mismatch 사례
- 특정 agent 과신으로 실패한 사례

### 5.3 Retrieval 규칙

- 각 retrieval은 top-k=5~10으로 제한
- 현재 시점 이후 데이터는 절대 참조 금지
- retrieval 결과는 raw text가 아니라 `retrieved_case_summary`로 재구성해서 agent prompt에 삽입
- retrieval 결과에는 반드시 case date range와 당시 regime tag를 포함
- near-duplicate case는 dedup
- floor 이하 validity case는 폐기

### 5.4 Retrieval validity scoring

단순 top-k 유사도 검색만 사용하지 말고, 각 retrieved case에 대해 validity score를 계산하라.

```
RetrievalScore(case) = Sim(query, case)
                     × RecencyDecay(case_age)
                     × RegimeMatch(current_regime, case_regime)
                     × DataQualityScore(case)
                     × OutcomeReliability(case)
```

세부 규칙:
- `RecencyDecay(case_age)`: 오래된 사례일수록 감쇠
- `RegimeMatch`: 현재 regime와 과거 case regime가 유사할수록 가중
- `DataQualityScore`: case 기록 completeness 반영
- `OutcomeReliability`: 해당 case가 충분한 review horizon 이후 검증된 사례인지 반영

추가 제약:
- RetrievalScore가 floor 이하인 case는 폐기
- `retrieved_case_summary`에는 당시 selected policy, outcome horizon, success/failure rationale을 포함
- retrieval은 cosine similarity 하나로 끝내지 말 것

---

## 6. Shared Ledger와 정보 비대칭 분리

### 6.1 Shared Ledger 목적

TradingAgents식 shared global state는 유지한다. 다만 이것은 "모든 내부 추론을 다 공유하는 공간"이 아니라, **회의 결과와 승인된 구조화 산출물을 남기는 공식 기록부**여야 한다.

### 6.2 Ledger에 저장할 것

- final market report
- technical summary packet
- candidate strategy summary
- risk review summary
- debate resolution
- signal conflict resolution
- final policy decision
- execution plan
- risk override record
- weekly propagation audit summary

### 6.3 Ledger에 저장하지 않을 것

- raw chain-of-thought
- agent 내부 임시 스케치
- 모든 retrieval 결과 전문
- 실험용 중간 가설 전부
- 토론 전체 transcript 전문

### 6.4 접근 규칙

- Emily는 이전 official market report와 current market memory를 볼 수 있다
- Bob은 official market report, technical summary packet, strategy memory를 본다
- Dave는 strategy summary와 risk-related memory를 본다
- Otto는 official outputs만 통합한다

즉, shared ledger는 공식 기록, memory는 agent별 retrieval substrate다. 둘을 섞지 말 것.

---

## 7. 에이전트 정의 v3.6

### 7.1 Emily — Market Analyst

Emily의 역할은 "시장 리포트 작성자"를 넘어서, 시장 상태를 전략 가능한 feature space로 변환하는 agent다.

v3.6에서는 Emily 내부에 **Technical signal priority**를 명시적으로 포함한다. Expert Investment Teams 논문에서 fine-grained task가 특히 Technical signal을 상위 의사결정으로 더 잘 전달한 점을 반영해야 한다. 따라서 Emily는 단순 macro/news 요약자가 아니라, market regime를 기술할 때 **technical continuation / reversal context도 공식 출력에 포함**해야 한다.

#### Emily의 핵심 출력

- `market_regime`
- `macro_state_score`
- `sector_preference` vector
- `catalyst_map`
- `uncertainty_score`
- `recommended_market_bias`
- `technical_signal_state`
- `technical_conflict_flags`

추가 필드:
- `regime_confidence`
- `uncertainty_reasons`
- `event_sensitivity_map`
- `technical_confidence`
- `reversal_risk`
- `continuation_strength`

#### Emily output schema

```json
{
  "agent": "Emily",
  "date": "YYYY-MM-DD",
  "market_regime": "risk_on | risk_off | mixed | fragile_rebound | transition",
  "regime_confidence": 0.0,
  "macro_state": {
    "rates": 0.0,
    "inflation": 0.0,
    "growth": 0.0,
    "liquidity": 0.0,
    "risk_sentiment": 0.0
  },
  "technical_signal_state": {
    "trend_direction": "up | down | mixed",
    "continuation_strength": 0.0,
    "reversal_risk": 0.0,
    "technical_confidence": 0.0
  },
  "sector_preference": [
    {"sector": "semiconductor", "score": 0.82},
    {"sector": "utilities", "score": 0.28}
  ],
  "bull_catalysts": [],
  "bear_catalysts": [],
  "event_sensitivity_map": [],
  "technical_conflict_flags": [],
  "risk_flags": [],
  "uncertainty_reasons": [],
  "recommended_market_bias": "selective_long | defensive | neutral"
}
```

#### Emily → Bob 전달용 transformation

```json
{
  "regime": "risk_on",
  "regime_confidence": 0.73,
  "preferred_sectors": ["semiconductor", "software"],
  "avoid_sectors": ["utilities"],
  "market_bias": "selective_long",
  "event_risk_level": 0.42,
  "market_uncertainty": 0.38,
  "technical_direction": "up",
  "technical_confidence": 0.77,
  "reversal_risk": 0.21
}
```

#### Emily uncertainty rule

- `regime_confidence < 0.55` 이면 Bob은 candidate strategy diversity를 늘린다
- `event_risk_level`이 높으면 Dave risk review 시 event shock penalty를 반영한다
- `technical_confidence`가 높으면 Bob은 aligned momentum / trend 전략 가중을 높인다
- `reversal_risk`가 높으면 Otto는 directional exposure 축소를 우선 고려한다

---

### 7.2 Bob — Strategy Analyst

Bob은 "전략을 생각하는 agent"가 아니라, 시장 상태를 전략 후보 집합으로 변환하고 simulated trading으로 검증하는 agent다.

v3.6에서는 Bob이 Emily의 technical packet을 명시적으로 활용해야 한다. 즉, Bob은 macro/news만 보고 전략을 만드는 것이 아니라, **technical continuation / reversal 구조와 regime confidence를 함께 읽어야 한다.**

#### Bob의 강화 포인트

- 전략 후보를 생성할 때 시장 state와 strategy memory retrieval을 함께 반영
- backtest는 반드시 point-in-time 제약 하에서만 수행
- 전략별 failure condition을 반드시 남김
- confidence는 단순 자기신뢰가 아니라 metric + regime fit + technical alignment 기반이어야 함
- `technical_confidence`가 높으면 technical-aligned candidate를 최소 1개 이상 반드시 포함
- contradiction이 큰 경우 conflict-aware hedge candidate를 생성

#### Bob output schema

```json
{
  "agent": "Bob",
  "date": "YYYY-MM-DD",
  "candidate_strategies": [
    {
      "name": "trend_following_long",
      "type": "directional",
      "logic_summary": "follow breakout in strong sectors",
      "regime_fit": 0.0,
      "technical_alignment": 0.0,
      "sim_window": {
        "train_start": "YYYY-MM-DD",
        "train_end": "YYYY-MM-DD"
      },
      "sim_metrics": {
        "return": 0.12,
        "sharpe": 1.42,
        "sortino": 1.88,
        "mdd": 0.07,
        "turnover": 0.31,
        "hit_rate": 0.56
      },
      "failure_conditions": [],
      "optimization_suggestions": [],
      "confidence": 0.73
    }
  ],
  "selected_for_review": []
}
```

#### Bob 핵심 규칙

- 현재 시점 이후 데이터 금지
- simulation period 명시 필수
- `selected_for_review`는 Dave 검토 전 최종 확정 아님
- confidence < threshold면 자동 탈락
- `technical_alignment < floor`이고 `market_uncertainty`가 높으면 full-size directional 전략 금지

#### Bob → Dave 전달용 transformation

```json
{
  "strategy_name": "trend_following_long",
  "expected_turnover": 0.31,
  "sector_bias": ["semiconductor", "software"],
  "expected_vol_profile": 0.58,
  "failure_conditions": ["macro shock", "sector reversal"],
  "strategy_confidence": 0.73,
  "technical_alignment": 0.81
}
```

#### Bob → Execution translation용 transformation

Bob의 strategy report를 실제 집행안과 동일시하지 말 것. Bob의 출력은 "실행 가능한 전략 후보"이지, 곧바로 주문안이 아니다.

```json
{
  "selected_strategy_name": "trend_following_long",
  "target_posture": "pro-risk directional long",
  "rebalance_urgency": 0.52,
  "expected_turnover": 0.31,
  "hedge_preference": "light",
  "execution_constraints_hint": []
}
```

#### Bob uncertainty rule

- strategy confidence가 낮으면 Dave는 stress multiplier를 상향
- `failure_conditions`가 많을수록 Otto는 approval 시 conditional approval 가능성을 높인다
- `technical_alignment`가 낮고 `regime_confidence`도 낮으면 Otto는 execution scale 축소를 우선 고려한다

---

### 7.3 Dave — Risk Control Analyst

Dave는 리포트형 risk 분석가가 아니라, **정책 전이를 유발할 수 있는 제약 생성 agent**다.

QuantAgents는 risk score를 beta, liquidity inverse, sector exposure, volatility의 결합으로 정의하고, threshold 초과 시 회의를 열게 한다. 이 구조를 최대한 유지하라.

#### Risk score 정의

```
R_score = w1 * beta_norm + w2 * illiquidity_norm + w3 * max_sector_exposure_norm + w4 * volatility_norm
```

기본 threshold는 0.75로 시작한다.

#### Dave risk ontology

risk score는 단순 weighted sum이 아니라 아래 세 범주로 해석되어야 한다.

- **Market Risk**: beta, volatility
- **Liquidity Risk**: illiquidity, turnover stress
- **Concentration Risk**: max sector exposure, single-name concentration

v3.6에서는 여기에 `signal_conflict_risk`를 약하게 추가 추적한다. 이는 최종 R_score를 대체하지는 않지만, strategy-macro mismatch, technical-macro mismatch가 큰 경우 escalation 우선순위를 높이는 보조 지표다.

#### Dave output schema

```json
{
  "agent": "Dave",
  "date": "YYYY-MM-DD",
  "risk_score": 0.81,
  "risk_components": {
    "beta": 0.22,
    "illiquidity": 0.15,
    "sector_concentration": 0.17,
    "volatility": 0.08
  },
  "signal_conflict_risk": 0.0,
  "stress_test": {
    "severity_score": 0.72,
    "worst_case_drawdown": 0.13
  },
  "risk_level": "low | medium | high | critical",
  "recommended_controls": [],
  "risk_constraints": {
    "max_single_sector_weight": 0.25,
    "max_beta": 1.05,
    "max_gross_exposure": 0.80
  },
  "trigger_risk_alert_meeting": true
}
```

#### Dave escalation rule

- `risk_score > 0.75` → 즉시 Risk Alert Meeting
- `worst_case_drawdown > cap` → de-risk override proposal
- liquidity shock severe → forced position cap
- `signal_conflict_risk`가 높고 `technical reversal_risk`도 높으면 partial de-risk 우선 검토

#### Dave uncertainty rule

- Emily `market_uncertainty`가 높고 Bob confidence가 낮으면 `severity_score`를 보수적으로 상향
- execution feasibility risk가 높으면 `max_gross_exposure`를 자동 축소
- `technical_alignment`가 낮은 전략은 동일 sim 성과여도 더 높은 risk weight를 부여할 수 있다

---

### 7.4 Otto — Investment Manager

Otto는 단순 aggregator가 아니라, **real reward와 simulated reward를 합쳐 최종 policy를 선택하는 meta-controller**다.

다만 Otto는 super-agent가 되어서는 안 된다. Otto는 raw 뉴스나 raw market data를 직접 해석하지 않고, **공식 packet만 통합**해야 한다.

#### Otto 금지 규칙

Otto는 아래를 직접 수행하지 않는다.

- raw 뉴스 직접 해석 금지
- raw OHLCV 직접 해석 금지
- strategy 재생성 금지
- risk score 재계산 금지
- raw retrieval text 직접 열람 금지

#### Otto 입력

- Market Report Packet
- Strategy Review Packet
- Risk Review Packet
- Execution Feasibility Packet
- recent reward history summary
- prior override journal
- agent reliability summary

#### Dual reward policy score

정책 후보 μ에 대해:

```
CombinedReward_t(μ) = w_sim_t * r_sim_t(μ) + w_real_t * r_real_t(μ)
```

#### Adaptive weighting update

최근 n-step reward history를 사용한다.

```
w_sim_t = sigmoid( sum_{i=t-n}^{t} r_sim_i / sum_{i=t-n}^{t} (r_sim_i + r_real_i + eps) )
w_real_t = 1 - w_sim_t
```

#### Risk-adjusted utility

최종 policy 선택은 단순 CombinedReward 최대화가 아니라 risk penalty를 포함해야 한다.

```
Utility_t(μ) = CombinedReward_t(μ)
             - λ1 * RiskScore_t(μ)
             - λ2 * ConstraintViolationPenalty_t(μ)
             - λ3 * MarketAlignmentPenalty_t(μ)
             - λ4 * ExecutionFeasibilityPenalty_t(μ)
             - λ5 * AgentReliabilityPenalty_t(μ)
```

여기서 `MarketAlignmentPenalty`는 Emily의 시장 상태 및 technical direction과 전략이 얼마나 어긋나는지를 반영한다. `AgentReliabilityPenalty`는 최근 horizon에서 noise가 높았던 signal source에 과도하게 의존한 경우 부과한다.

#### Otto output schema

```json
{
  "agent": "Otto",
  "date": "YYYY-MM-DD",
  "candidate_policies": [],
  "adaptive_weights": {
    "w_sim": 0.44,
    "w_real": 0.56,
    "lookback_steps": 8
  },
  "selected_policy": "trend_following_long_plus_hedge",
  "allocation": {
    "equities": 0.55,
    "hedge": 0.10,
    "cash": 0.35
  },
  "execution_plan": {
    "entry_style": "staggered",
    "rebalance_frequency": "weekly",
    "stop_loss": 0.06
  },
  "policy_reasoning_summary": [],
  "approval_status": "approved | approved_with_modification | conditional_approval | rejected"
}
```

#### Otto approval rule

- `risk_score` 높고 uncertainty 높으면 `approved_with_modification` 또는 `conditional_approval` 우선
- execution feasibility가 낮으면 phased/staggered execution만 허용 가능
- Bob strategy confidence 낮고 Dave severity 높으면 full-size directional allocation 금지
- `technical_confidence` 높지만 macro uncertainty도 높으면 selective rather than broad allocation 우선
- agent reliability가 낮은 specialist에 과도하게 의존한 정책은 승인을 보수적으로 처리

#### Otto의 본질

Otto는 **policy arbitration manager**다. Otto는 판단을 종합하고 승인/수정/거절을 내리지만, market understanding의 1차 생산자는 아니다.

---

## 8. Meeting 프로토콜 v3.6

### 8.1 Weekly Market Analysis Meeting

**목적**: 시장 상태를 전략 가능한 report로 변환한다.

**cadence**: 매주 마지막 거래일 종료 후 1회

**참여**: Emily, Bob, Dave

**입력**:
- 이번 주 market memory snapshot
- macro summary
- news/event summary
- technical summary
- prior weekly reports

**순서**:
1. Emily가 regime report 생성
2. Technical sub-signal summary 생성
3. Bob이 quantitative augmentation 수행
4. Dave가 risk interpretation 추가
5. bull / bear debate sub-step 실행
6. signal conflict resolution sub-step 실행
7. final market report 확정
8. Reports Memory 저장
9. Shared Ledger 기록

#### debate sub-step

독립 bull/bear full agent를 추가로 두지 않되, 최소한 아래 구조는 유지한다.

```json
{
  "bull_case": {
    "growth_path": "...",
    "upside_catalysts": [],
    "sustainability": "..."
  },
  "bear_case": {
    "downside_risks": [],
    "fragility": "...",
    "reversal_triggers": []
  },
  "moderator_summary": "...",
  "unresolved_issues": [],
  "regime_confidence_adjustment": 0.0
}
```

#### signal conflict resolution sub-step

debate를 단순 찬반 구조로 끝내지 말고, 서로 다른 signal source 간 충돌을 공식 상태로 남겨야 한다.

- Technical vs Macro conflict
- Technical vs News conflict
- Strategy tendency vs current risk regime conflict
- Sector preference vs concentration risk conflict

```json
{
  "conflict_matrix": [
    {
      "signal_a": "technical_momentum_strong",
      "signal_b": "macro_risk_off",
      "conflict_type": "time_horizon_mismatch",
      "resolution": "reduce gross exposure, keep selective long"
    }
  ]
}
```

**최종 출력**:
- official weekly market report
- regime confidence
- preferred sectors / avoid sectors
- unresolved risks
- debate_resolution
- signal_conflict_resolution
- technical summary packet

---

### 8.2 Weekly Strategy Development Meeting

**목적**: 새 전략 후보를 생성하고 simulated trading으로 검증한다.

**cadence**: 매주 마지막 거래일 종료 후 1회, market analysis meeting 직후

**참여**: Bob, Dave, Emily

**입력**:
- official weekly market report
- technical summary packet
- strategy memory retrieval
- historical data up to t only
- portfolio state

**순서**:
1. Bob 전략 후보 생성
2. Bob simulated trading 수행
3. Bob failure condition 정리
4. Dave risk review
5. Emily market fit review
6. strategy debate
7. selected strategy set 확정
8. Strategy Memory 업데이트
9. Shared Ledger 기록

**중요한 규칙**:
- simulation은 반드시 current time 이전 데이터까지만
- selection은 Dave의 제약을 만족해야 함
- selection은 Emily의 regime fit penalty를 반영해야 함
- selection은 technical alignment를 반드시 반영해야 함
- selected strategy는 실제 실행안과 동일하지 않음
- execution feasibility packet을 별도로 생성해야 함

**출력**:
- candidate strategy set
- selected strategy set
- rejection reasons
- optimization notes
- execution feasibility hints
- technical alignment summary

---

### 8.3 Risk Alert Meeting

**목적**: 리스크 임계치 초과 시 policy를 수정한다.

**cadence**: event-driven only

**참여**: Dave, Bob, Emily, Otto

**트리거**:
- `risk_score > 0.75`
- severe liquidity shock
- drawdown breach
- extreme event shock
- technical reversal shock with high leverage
- high signal_conflict_risk

**입력**:
- current portfolio
- Dave risk score
- Bob stress severity
- Emily sentiment/event shock
- Emily technical reversal risk
- current selected policy

**핵심 수식**:

```
RiskAdjustedUtility_t(μ) = (1 - λ) * CombinedReward_t(μ) - λ * RiskReward_t(μ)

RiskReward_t(μ) = -a * R_score - b * StressSeverity + c * SentimentSafety - d * TechnicalReversalPenalty
```

**순서**:
1. Dave risk reassessment
2. Bob stress scenario severity 산출
3. Emily sentiment/event shock 점수 산출
4. Emily technical reversal risk 점수 산출
5. Otto가 RiskAdjustedUtility 기준으로 policy 재선택
6. 필요시 de-risk 강제 적용
7. Decision Journal 및 Ledger 업데이트

**출력**:
- updated policy
- emergency controls
- hedge decision
- rollback 여부

---

## 9. Meeting 간 인터페이스 정의

v3.5의 transformation layer는 유지한다. v3.6에서는 여기에 calibration과 propagation audit을 추가한다.

### 9.1 Market Report → Strategy Packet

Emily의 full report를 Bob이 그대로 받지 말고, 전략 생성용 feature packet으로 요약한다.

### 9.2 Strategy Review → Risk Packet

Bob의 strategy report를 Dave가 그대로 받지 말고, risk exposure estimation에 필요한 핵심 요약만 추출한다.

### 9.3 Strategy Review → Execution Feasibility Packet

Bob의 selected strategy set은 곧바로 order plan이 아니다. 실행 단계에서 아래 항목으로 재요약한다.

- target posture
- expected turnover
- urgency
- hedge preference
- position transition cost hint

### 9.4 Risk Review + Strategy Review + Market Report + Execution Feasibility → Policy Packet

Otto는 raw input을 직접 분석하지 않고, 세 agent의 official packet과 execution feasibility packet만 통합한다.

### 9.5 uncertainty propagation interface

모든 packet은 가능하면 confidence/uncertainty field를 포함해야 한다.

- `market_uncertainty`
- `technical_confidence`
- `strategy_confidence`
- `execution_feasibility_score`
- `risk_severity_score`

### 9.6 calibration layer

모든 score 기반 specialist output은 상위 단계 전달 전 Calibration Layer를 반드시 통과해야 한다.

**Calibration Layer 규칙**:
- rolling standardization within agent
- sector-relative normalization
- confidence-based shrinkage toward neutral
- outlier clipping
- missing-value safe fallback

### 9.7 propagation audit

각 transformation 이후, 하위 agent signal이 상위 단계에서 실제로 반영되었는지 점검하라.

최소 아래 항목을 기록할 것:
- adopted keyword rate
- dropped critical signal rate
- contradiction after transformation
- semantic similarity between source packet and target summary
- technical signal adoption rate

---

## 10. Agent reliability와 conditional gating

v3.6에서 새로 명시하는 핵심 규칙이다.

모든 specialist agent를 항상 동일 가중으로 신뢰하지 말 것.

### 10.1 reliability state

```json
{
  "agent_reliability_state": {
    "technical": 0.82,
    "quantitative": 0.54,
    "qualitative": 0.48,
    "news": 0.61,
    "macro": 0.44
  }
}
```

### 10.2 reliability update 기준

- recent decision usefulness
- contradiction frequency
- propagation adoption rate
- post-horizon outcome alignment
- empty / stale / noisy output 비율

### 10.3 conditional gating

```json
{
  "conditional_gating": {
    "risk_off_macro_shock": ["macro", "news", "technical"],
    "stable_trend_market": ["technical", "sector_rotation"],
    "earnings_season": ["quantitative", "news", "qualitative"]
  }
}
```

**규칙**:
- reliability가 floor 이하인 agent는 hard gating 또는 soft downweighting
- 동일 정보가 중복 공급되는 경우 redundancy penalty 적용
- technical signal은 기본적으로 우선 신호이나, reversal risk가 높으면 aggressive usage 금지

### 10.4 Otto 적용 규칙

Otto는 policy selection 시 agent reliability summary를 반드시 본다. 같은 전략 성과여도 신뢰도 낮은 source 조합에 의존한 정책은 보수적으로 승인한다.

---

## 11. Empty-case / missing-data protocol

재현 가능한 시스템을 위해 empty-case protocol을 명시한다.

### 11.1 News 없음
- no news인 경우 임의 해석 금지
- "No material news" 상태를 명시적으로 기록
- neutral 또는 slight-uncertainty 처리
- hallucinated catalyst 생성 금지

### 11.2 Financial data 일부 누락
- NaN은 조용히 버리지 말고 missing flag와 함께 전달
- confidence shrinkage 적용
- 상위 agent는 missing-data aware aggregation 수행

### 11.3 Technical signal 충돌
- momentum strong이지만 reversal risk도 높으면 conflict flag 생성
- 상위 단계에서 directional conviction 자동 하향 가능

### 11.4 Execution feasibility 불충분
- execution feasibility score가 floor 이하이면 즉시 phased execution 또는 hold decision 고려
- Bob 전략안과 order plan 동일시 금지

### 11.5 stale retrieval
- freshness 부족 case는 retrieval 후보에서 제거
- stale case를 쓴 경우 로그에 표시하고 weight 감쇠

---

## 12. 평가 설계 v3.6

### 12.1 기본 성과 지표

- total return
- annualized return
- sharpe ratio
- sortino ratio
- calmar ratio
- max drawdown
- turnover
- win rate
- policy stability

### 12.2 안정성 / 구조 평가

- regime robustness
- risk alert precision
- false positive risk alert rate
- strategy replacement frequency
- policy oscillation index

### 12.3 메모리 / 시스템 평가

- retrieval usefulness score
- decision reproducibility
- memory contamination check
- state ledger consistency
- latency per cycle

### 12.4 explainability 평가

- decision trace completeness
- evidence-to-action consistency
- risk rationale consistency
- contradiction rate across meetings
- packet transformation fidelity
- override justification completeness

### 12.5 propagation / signal 평가

반드시 아래 지표를 추가한다.

- technical signal adoption rate
- source-to-manager semantic similarity
- dropped critical signal rate
- conflict resolution quality
- agent-specific marginal utility
- reliability-weighted contribution score

### 12.6 baseline 묶음

최소 다음 비교군을 둬라.

- Buy-and-hold index
- Mean-Variance allocator
- Single-agent LLM trader
- Multi-agent without simulated trading
- Multi-agent without risk alert meeting
- Multi-agent without memory retrieval
- Multi-agent without calibration layer
- Multi-agent without propagation audit
- Full hybrid system

### 12.7 ablation

반드시 아래 ablation을 돌려라.

- remove simulated reward
- remove strategy memory
- remove market analysis meeting
- remove risk alert meeting
- remove adaptive weighting
- remove debate protocol
- remove execution feasibility layer
- remove retrieval validity scoring
- remove technical priority routing
- remove calibration layer
- remove propagation audit
- remove agent reliability gating

### 12.8 leakage-safe evaluation

- point-in-time split 필수
- 미래 뉴스 접근 금지
- future regime tag 접근 금지
- strategy memory에 future result 저장 금지
- retrieval timestamp guard 필수
- review horizon이 닫히기 전 outcome reliability 확정 금지

### 12.9 fine vs coarse task evaluation

Expert Investment Teams 논문 문제의식을 직접 재현하기 위해, 반드시 같은 구조에서 task granularity만 바꾼 비교군을 둬라.

- Same architecture + fine-grained task packets
- Same architecture + coarse-grained raw inputs
- Same architecture + no transformation layer
- Same architecture + no technical priority routing

---

## 13. 구현 금지 사항 v3.6

기존 금지 사항에 더해 아래를 금지한다.

- simulated trading을 단순 backtest utility로만 만들지 말 것
- shared ledger를 전체 내부 추론 dump 저장소로 쓰지 말 것
- Emily/Bob/Dave/Otto가 동일 raw input을 전부 같이 보게 하지 말 것
- Otto가 raw 뉴스나 raw market data를 직접 해석하게 하지 말 것
- risk alert를 단순 warning log로 끝내지 말 것
- adaptive weighting을 placeholder 변수로만 두지 말 것
- evaluation에서 ablation 없이 full system만 자랑하지 말 것
- debate를 장식용 찬반 문장으로만 두지 말 것
- selected strategy를 곧바로 execution order로 취급하지 말 것
- confidence/uncertainty를 출력만 하고 제어 로직에 쓰지 말 것
- retrieval에서 similarity만 보고 오래된 case를 그대로 쓰지 말 것
- technical signal을 macro/news 요약 안에 묻어버리지 말 것
- 모든 specialist agent를 항상 동일 가중으로 통합하지 말 것
- calibration 없이 raw score를 상위 단계로 누적하지 말 것
- propagation audit 없이 "전달되었다고 가정"하지 말 것

---

## 14. 코덱스 구현 우선순위 v3.6

### Phase 1
- 4개 에이전트
- 3개 meeting
- Market/Reports/Strategy memory
- shared official ledger
- transformation layer
- weekly + daily cadence
- deterministic backtest mode
- technical summary packet
- calibration layer

### Phase 2
- dual reward update
- risk-adjusted utility
- retrieval-grounded prompting
- debate sub-step
- decision journal
- execution feasibility layer
- uncertainty propagation rule
- propagation audit
- technical priority routing

### Phase 3
- full ablation suite
- regime robustness evaluation
- live replay mode
- multi-asset extension
- portfolio optimizer refinement
- retrieval validity scoring refinement
- explainability audit dashboard
- agent reliability gating refinement

---

## 15. 최종 설계 요약

**Emily**는 시장을 읽어 전략 가능한 시장 상태로 바꾸고, 동시에 technical continuation / reversal 구조를 공식 시장 상태의 일부로 정리한다.

**Bob**은 그 상태를 시뮬레이션 가능한 전략 후보 집합으로 바꾸며, 특히 technical alignment와 regime fit을 함께 고려해 전략을 생성하고 검증한다.

**Dave**는 그 전략을 제약과 경보가 있는 위험 공간 위에 올리고, risk score와 signal conflict risk를 바탕으로 정책 전이를 유발할 수 있는 제약을 만든다.

**Otto**는 실거래 보상과 시뮬레이션 보상을 함께 고려해 최종 정책을 선택하되, agent reliability와 execution feasibility를 함께 반영하여 승인 / 수정 / 조건부 승인 / 거절을 결정한다.

그리고 이 모든 과정은

- 주간 meeting
- 일간 risk check
- event-driven alert
- retrieval-driven memory
- shared official ledger
- structured debate resolution
- signal conflict resolution
- execution feasibility check
- calibration layer
- propagation audit

위에서 반복된다.

즉 이 시스템은 단순한 agent 대화체가 아니라, **시간축 위에서 굴러가는 조직형 금융 의사결정 엔진**이어야 한다.

QuantAgents가 지향한 simulated trading 기반 forward-looking multi-agent finance의 핵심, TradingAgents가 강조한 역할 분화, structured communication, debate, risk gating의 핵심, 그리고 Expert Investment Teams가 보여준 fine-grained task contract와 signal propagation의 핵심은 바로 여기에 있다.
