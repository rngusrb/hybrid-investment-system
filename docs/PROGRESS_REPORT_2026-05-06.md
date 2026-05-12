# Hybrid Investment System — 진행 상황 리포트

**작성일**: 2026-05-06
**기준 문서**: TradingAgents (1.pdf), QuantAgents (2.pdf), DESIGN_SPEC_v3.6.md, CLAUDE_CODE_BRIEFING.md

---

## 1. 이 시스템이 뭘 합치려 했나

세 논문/설계 소스의 핵심을 각각 가져왔다.

| 소스 | 가져온 핵심 |
|------|------------|
| **TradingAgents** (1.pdf) | 4 Analysts + Researcher(Bull/Bear) + Trader + Risk Manager 조직형 워크플로우, structured communication protocol |
| **QuantAgents** (2.pdf) | Otto/Bob/Dave/Emily 4 에이전트 + 3 meetings + 3 memory + dual reward policy |
| **Design Spec v3.6** | fine-grained task contract, technical signal priority, agent reliability gating, calibration layer, propagation audit |

**"Hybrid"의 의미**: TradingAgents(개별 종목 분석)를 QuantAgents(포트폴리오 운영 루프) 안으로 끌어들인 것. bc_graph의 `BC_STOCK_ANALYSIS` 노드가 각 ticker에 Pipeline B(TradingAgents 구조)를 실행하고 그 결과를 Emily/Dave/Otto의 포트폴리오 결정에 공급한다. 이 조합은 어느 논문에도 없는 이 시스템만의 설계다.

---

## 2. 설계 스펙 대비 구현 현황

### 2.1 Phase 1 — 코어 (거의 완료)

| 항목 | 상태 | 비고 |
|------|------|------|
| 4 에이전트 (Emily/Bob/Dave/Otto) | ✅ | schemas, prompts, agents/ 전부 구현 |
| 3 meetings (MAM/SDM/RAM) | ✅ | meetings/ + graph/nodes/ 연결됨 |
| Memory 3종 (Market/Reports/Strategy) | ✅ | memory/ 구현, run_memory로 주기 실행 |
| Decision Journal | ✅ | memory/decision_journal.py |
| Shared Ledger | ✅ | ledger/shared_ledger.py |
| Transformation Layer | ✅ | transforms/ 4개 파일 |
| Calibration Layer | ✅ | calibration/ 구현됨 |
| Technical summary packet | ✅ | Emily output에 technical_signal_state 포함 |
| LangGraph state machine | ✅ | bc_graph.py (conditional edges 포함) |
| LLM 이원화 (analyst/decision) | ✅ | llm/factory.py |
| Propagation Audit | ✅ | audit/ 구현됨 |
| Agent Reliability 모듈 | ✅ | reliability/ 구현됨 |
| Dual Reward (w_sim/w_real) | ✅ | adaptive weights 계산 구현됨 |
| Risk-adjusted utility | ✅ | RAM에서 RiskAdjustedUtility 사용 |

### 2.2 Phase 2 — 심화 (부분 완료)

| 항목 | 상태 | 비고 |
|------|------|------|
| Retrieval-grounded prompting | ⚠️ | token overlap 기반 — validity scoring 미적용 |
| Debate sub-step (Bull/Bear) | ✅ | Researcher debate 구현됨 |
| Execution feasibility layer | ⚠️ | transforms/bob_to_execution.py 있으나 bc_graph 흐름에 약하게 연결 |
| Uncertainty propagation rule | ⚠️ | regime_confidence → Bob 연결은 있으나 전체 체인 불완전 |
| Technical priority routing | ⚠️ | signal conflict resolution 구현됨, 실제 routing 영향은 제한적 |
| **Agent reliability → Otto 연결** | ❌ | reliability 모듈 존재하나 Otto 승인 로직에 미연결 |
| **DAILY_AGENT_RELIABILITY_UPDATE** | ❌ | 설계 스펙 Phase 4.1 명시 상태 — graph에 미포함 |

### 2.3 Phase 3 — 평가 (미구현)

| 항목 | 상태 | 비고 |
|------|------|------|
| 성과 지표 (CR, ARR, SR, MDD, Sortino...) | ❌ | evaluation/metrics.py 미구현 |
| Backtester (point-in-time safe) | ⚠️ | simulation/backtester.py 있으나 전체 평가 파이프라인 없음 |
| Baseline 비교군 | ❌ | evaluation/baselines.py 미구현 |
| Ablation suite | ❌ | evaluation/ablation.py 미구현 |
| Regime robustness evaluation | ❌ | 미구현 |
| Retrieval validity scoring 고도화 | ❌ | RecencyDecay × RegimeMatch × DataQualityScore 미적용 |
| Explainability audit dashboard | ❌ | 미구현 |

### 2.4 TradingAgents 26개 도구 연결

| 항목 | 상태 |
|------|------|
| Technical Indicator Analysis (t1) | ✅ |
| Algorithmic Trading Strategies (t3) | ✅ |
| Economic Indicator Forecasting (t5) | ✅ |
| Corporate Earnings Analysis (t6) | ✅ |
| Risk-Adjusted Return Analysis (t9) | ✅ |
| Portfolio Diversification Tools (t10) | ✅ |
| Portfolio Stress Testing (t17) | ✅ |
| Simulation Optimization Toolkit (t23) | ✅ |
| Strategy Analysis Suite (t24) | ✅ |
| RiskAnalyzer Toolkit (t25) | ✅ |
| Risk Score Assessment Tool (t26) | ✅ |
| FinReport (t20) | ✅ |
| Volatility Assessment Tool (t22) | ✅ |
| Trend Forecasting (t21) | ✅ |
| Fund Performance Evaluation (t19) | ✅ |
| Asset Allocation Optimization (t15) | ✅ |
| Risk Management Frameworks (t16) | ✅ |
| Central Bank Policy Analysis (t11) | ✅ |
| **Sentiment Analysis from Social Media (t2)** | ❌ Reddit/Twitter API 필요 |
| **Regulatory Change Impact Analysis (t4)** | ❌ |
| **NASDAQ-100 Index Component Tracking (t7)** | ❌ |
| **Sector Performance Evaluation (t8)** | ❌ |
| **Global Macroeconomic Trend Analysis (t12)** | ❌ |
| **Currency Pair Correlation Matrix (t13)** | ❌ |
| **Interest Rate Differential Analysis (t14)** | ❌ |
| **Derivatives Strategy Formulation (t18)** | ❌ Options API 필요 |

**연결률**: 18/26 (69%)

---

## 3. 핵심 갭 분석

### 갭 1 — 평가 파이프라인 완전 부재 [Critical]

QuantAgents는 ARR 58.68%, SR 3.11, MDD 16.86%로 모든 베이스라인을 능가했다.
TradingAgents는 CR 26.62%, ARR 30.5%, SR 8.21로 buy-and-hold 대비 +24%였다.

**현재 이 시스템은 자신의 성과를 측정할 방법이 없다.**
bc_graph가 실행되고 결과가 results/에 저장되지만, CR/ARR/SR/MDD로 집계되지 않는다.
베이스라인 비교도 없다. 어블레이션도 없다.
즉, 지금 상태로는 "이 시스템이 더 나은가?"라는 질문에 대답할 수 없다.

### 갭 2 — Daily Cycle 미완성 [High]

DESIGN_SPEC은 다음 일간 흐름을 정의했다:
```
INGEST → UPDATE_MARKET_MEMORY → DAILY_SIGNAL_CALIBRATION
→ DAILY_AGENT_RELIABILITY_UPDATE → DAILY_RISK_CHECK
→ DAILY_POLICY_SELECTION → EXECUTION_FEASIBILITY → ORDER_PLAN → LOGGING
```

현재 bc_graph는 이 일간 사이클 없이 weekly 단위로만 실행된다.
특히 `DAILY_AGENT_RELIABILITY_UPDATE`가 설계 스펙에 명시된 상태임에도 graph에 없다.

### 갭 3 — Agent Reliability가 실제 결정에 미연결 [High]

`reliability/agent_reliability.py`는 구현됐지만 Otto의 승인 로직에 연결되지 않았다.
설계 스펙: "reliability가 floor 이하인 agent는 hard gating 또는 soft downweighting"
현재: Otto는 항상 동일 가중으로 모든 agent 결과를 통합.

### 갭 4 — Retrieval이 논문 스펙보다 단순 [Medium]

논문: `RetrievalScore = Sim × RecencyDecay × RegimeMatch × DataQualityScore × OutcomeReliability`
현재: token overlap 기반 similarity만 사용.
결과: 오래된 케이스나 현재 레짐과 맞지 않는 케이스가 검색될 수 있음.

### 갭 5 — Execution Feasibility Layer 약한 연결 [Medium]

설계 스펙: "selected strategy ≠ execution order"를 명시적으로 분리.
`bob_to_execution.py` transform은 존재하나, bc_graph 흐름에서 이 패킷이 Otto의 최종 승인에 실질적으로 영향을 주지 않는다.

---

## 4. 원래 설계 대비 달성도 요약

```
Phase 1 (Core)          ████████████░  ~90%  ← 거의 완료
Phase 2 (Advanced)      ████████░░░░░  ~55%  ← 부분 완료
Phase 3 (Evaluation)    ██░░░░░░░░░░░  ~10%  ← 거의 미착수
TradingAgents Tools     ██████████░░░  69%   ← 일부 외부 API 의존
```

**전체 달성도**: 설계 스펙의 약 55~60% 구현됨.

---

## 5. 다음 스프린트 후보 태스크

우선순위 기준: 시스템이 "작동하는가"가 아니라 "측정 가능한가" + "설계 의도대로인가"

### E-001: 평가 파이프라인 구축 [우선순위: 최상]
**배경**: 갭 1. 현재 성과 측정 불가.
**작업**:
- `evaluation/metrics.py` — CR, ARR, SR, Sortino, MDD, VoL 계산
- `evaluation/backtester.py` — run_loop 결과를 지표로 집계 (point-in-time safe)
- `evaluation/baselines.py` — Buy-and-hold, MACD, SMA 최소 3개 베이스라인
- 결과를 `results/eval_YYYY-MM-DD.json`으로 저장

**완료 기준**: AAPL 2024-01~03 구간 실행 후 CR/ARR/SR/MDD가 baselines와 함께 출력됨.

---

### E-002: Agent Reliability → Otto 연결 [우선순위: 상]
**배경**: 갭 3. reliability 모듈이 고립되어 있음.
**작업**:
- `graph/nodes/bc_calibration.py`에서 reliability state를 SystemStateBC에 기록
- `graph/nodes/bc_portfolio.py`에서 otto_feedback에 reliability summary 주입
- `graph/nodes/bc_otto.py`에서 낮은 reliability agent 의존도 높은 policy에 conditional_approval 처리

**완료 기준**: reliability floor 이하 agent 의존 시 Otto가 conditional_approval 반환하는 통합 테스트 통과.

---

### E-003: Retrieval Validity Scoring 고도화 [우선순위: 중]
**배경**: 갭 4. 논문 스펙 미달.
**작업**:
- `memory/retrieval/validity_scorer.py`에 RecencyDecay, RegimeMatch, DataQualityScore 구현
- 기존 token overlap → validity-weighted score로 교체
- floor 이하 case 폐기 로직 추가

**완료 기준**: 오래된 케이스(age > 180일)의 retrieval score가 최신 케이스보다 낮게 계산됨.

---

### E-004: DAILY_AGENT_RELIABILITY_UPDATE 노드 연결 [우선순위: 중]
**배경**: 갭 2. 설계 스펙에 명시된 상태가 graph에 없음.
**작업**:
- bc_graph에 `BC_RELIABILITY_UPDATE` 노드 추가 (BC_CALIBRATION 이후)
- 각 날짜 실행 후 reliability state 업데이트

**완료 기준**: harness all 통과 + reliability_state.json이 실행마다 갱신됨.

---

## 6. 결론

이 시스템은 세 논문의 핵심 구조를 실제로 구현했고, 특히 TradingAgents × QuantAgents를 하나의 bc_graph 루프로 통합한 설계는 어느 논문에도 없는 독자적 기여다.

그러나 **지금 상태로 논문과 비교하는 건 불가능하다** — 평가 파이프라인이 없기 때문이다.

다음 단계의 핵심은 E-001이다. 평가가 가능해야 나머지 개선(reliability, retrieval, ablation)의 효과도 측정할 수 있다.

---

*문서 경로: `docs/PROGRESS_REPORT_2026-05-06.md`*
