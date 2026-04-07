# CLAUDE_CODE_BRIEFING.md
# Hybrid Multi-Agent Investment System v3.6
# Claude Code 핸드오프 문서 — Director + Sub-agent Teams용

---

## 0. 이 문서의 목적과 사용법

이 문서는 Claude Code가 Hybrid Multi-Agent Investment System을 구축할 때 사용하는 핸드오프 문서다.

**Director agent**는 이 문서를 읽고 전체 작업을 조율한다.
**Sub-agent**들은 각자 담당 Phase 섹션과 관련 설계 섹션을 참고한다.
**진행 기록**은 이 문서 하단 `## PROGRESS LOG` 섹션에 계속 append한다. 절대 덮어쓰지 말고 날짜/시간과 함께 기록한다.
**K(사용자)**는 나중에 이 문서를 보고 어떤 결정이 왜 내려졌는지 추적할 수 있어야 한다.

---

## 1. 프로젝트 개요

### 1.1 프로젝트명
**Hybrid Multi-Agent Investment System v3.6**

부제: TradingAgents × QuantAgents × Expert Investment Teams with Temporal Cadence, Dual Reward Policy, Retrieval-Grounded Meetings, Technical Signal Priority, Agent Gating, and Structured Debate-Controlled Execution

### 1.2 위치
```
~/Desktop/hybrid-investment-system/
```

### 1.3 한 줄 정의
TradingAgents의 structured organizational workflow, QuantAgents의 meeting-driven operating loop와 explicit memory modules, Expert Investment Teams의 fine-grained task contracts를 통합하여, 시장 분석 → 전략 시뮬레이션 → 리스크 경보 → 최종 정책 선택 → 실행 계획 확정의 전 과정을 시간축 위의 구조화된 상태 전이와 dual reward learning으로 수행하는 멀티에이전트 투자 의사결정 시스템.

### 1.4 참고 논문/레포
- TradingAgents (arXiv:2412.20138)
- QuantAgents (meeting-driven multi-agent finance)
- Expert Investment Teams (fine-grained task contracts)
- 기존 trading-agents 프로젝트: `~/Desktop/trading-agents/` (참고용, 건드리지 말 것)

### 1.5 핵심 설계 원칙 (절대 타협하지 말 것)
1. **Fine-grained task contract가 시스템 중심축** — agent 수보다 업무 계약이 중요
2. **Technical signal은 우선 신호** — macro/news 요약 안에 묻히면 안 됨
3. **Agent conditional gating** — 모든 agent를 항상 동일 가중으로 신뢰하지 말 것
4. **Propagation audit** — 하위 signal이 실제로 상위 결정에 반영됐는지 추적
5. **Calibration layer** — raw score를 그대로 상위 단계로 누적하지 말 것
6. **LangGraph 유연성** — 정해진 루프를 기계적으로 돌리지 말고 LLM 판단으로 재시도/스킵 가능

---

## 2. Agent Teams 구성

### 2.1 Director (Orchestrator Agent)

**역할**: 전체 작업 조율, 진행 기록, 디버깅, sub-agent 간 충돌 해결

**Director의 책임:**
- 각 Phase 시작 전 계획 수립 및 PROGRESS LOG 기록
- Sub-agent 작업 결과 검토 및 품질 확인
- 테스트 실패 시 원인 분석 및 재시도 지시
- Phase 완료 기준 판단
- 설계 문서(v3.6 기획서)와 구현 내용 간 괴리 발견 시 플래그

**Director가 반드시 기록해야 하는 것:**
- Phase 시작/완료 시각
- 각 sub-agent에게 준 지시 요약
- 발생한 버그와 해결 방법
- 설계 결정 및 그 이유 (왜 그렇게 했는지)
- 다음 Phase에 넘겨야 할 주의사항

### 2.2 Sub-agent 팀 구성

| Sub-agent | 담당 |
|-----------|------|
| **Architect** | 디렉토리 구조 생성, config, schema 작성 |
| **LLM Engineer** | provider 추상화 계층 구현 |
| **Graph Engineer** | LangGraph state/nodes/edges/builder 구현 |
| **Agent Engineer** | Emily/Bob/Dave/Otto agent 구현 |
| **Data Engineer** | Polygon fetcher, data manager 이식 및 개선 |
| **Memory Engineer** | memory 계층, retrieval, ledger 구현 |
| **Transform Engineer** | transformation layer, calibration, audit 구현 |
| **Eval Engineer** | evaluation, metrics, ablation suite 구현 |
| **Test Engineer** | 각 phase 완료 후 통합 테스트 |

Director는 필요에 따라 sub-agent를 병렬 또는 순차 실행한다.

---

## 3. LangGraph 유연성 원칙

이 시스템은 **정해진 루프를 기계적으로 실행하는 게 아니다.**

### 3.1 LLM 판단 기반 흐름 제어

각 node는 다음을 반환할 수 있다:
```python
class NodeResult(TypedDict):
    next: str                    # 다음 노드 이름
    skip_reason: Optional[str]   # 이 노드를 스킵한 이유
    retry: bool                  # 재시도 요청
    retry_reason: Optional[str]  # 재시도 이유
    confidence: float            # 이 결과에 대한 신뢰도
```

### 3.2 스킵 가능한 케이스 예시
- 데이터 변화가 거의 없을 때 → Weekly Meeting 일부 스킵
- Risk score가 매우 낮고 regime이 stable할 때 → Risk review 경량화
- Emily output confidence가 매우 높을 때 → debate sub-step 간소화
- technical signal과 macro signal이 완전히 일치할 때 → conflict resolution 스킵

### 3.3 재시도 가능한 케이스 예시
- Agent output이 schema validation 실패할 때
- Confidence가 threshold 미달일 때
- 외부 API 호출 실패할 때
- 이전 node 결과와 현재 node 결과가 심각하게 모순될 때

### 3.4 conditional edge 설계 원칙
```
모든 edge는 단순 next_node 반환이 아니라
현재 state를 보고 LLM이 판단한 결과를 반영해야 한다.
```

---

## 4. 전체 디렉토리 구조

```
~/Desktop/hybrid-investment-system/
│
├── CLAUDE_CODE_BRIEFING.md          # 이 문서
├── PROGRESS_LOG.md                  # 진행 기록 전용 (Director가 관리)
├── DESIGN_SPEC_v3.6.md              # v3.6 기획서 전문 (별도 제공)
│
├── config/
│   ├── system_config.yaml           # LLM provider, threshold, cadence
│   ├── agent_config.yaml            # agent별 파라미터, system prompt 경로
│   └── evaluation_config.yaml       # 평가 설정
│
├── llm/
│   ├── __init__.py
│   ├── base.py                      # BaseLLMProvider (ABC)
│   ├── factory.py                   # config 읽고 provider 반환
│   └── providers/
│       ├── __init__.py
│       ├── anthropic_provider.py    # Claude
│       ├── openai_provider.py       # GPT-4o 등
│       └── ollama_provider.py       # 로컬 모델
│
├── schemas/
│   ├── __init__.py
│   ├── base_schema.py               # 공통 Pydantic base
│   ├── emily_schema.py              # EmilyOutput, EmilyToBobPacket
│   ├── bob_schema.py                # BobOutput, BobToDavePacket, BobToExecutionPacket
│   ├── dave_schema.py               # DaveOutput
│   ├── otto_schema.py               # OttoOutput, ExecutionPlan
│   ├── meeting_schema.py            # Meeting input/output schemas
│   └── audit_schema.py             # PropagationAudit, CalibrationLog
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py                # BaseAgent (공통 로직, retry, logging)
│   ├── emily.py                     # Market Analyst
│   ├── bob.py                       # Strategy Analyst
│   ├── dave.py                      # Risk Analyst
│   └── otto.py                      # Fund Manager
│
├── prompts/
│   ├── emily_system.md
│   ├── bob_system.md
│   ├── dave_system.md
│   ├── otto_system.md
│   └── meeting/
│       ├── market_analysis_prompt.md
│       ├── strategy_development_prompt.md
│       └── risk_alert_prompt.md
│
├── meetings/
│   ├── __init__.py
│   ├── base_meeting.py
│   ├── market_analysis.py           # Weekly Meeting 1
│   ├── strategy_development.py      # Weekly Meeting 2
│   └── risk_alert.py                # Event-driven Meeting
│
├── graph/
│   ├── __init__.py
│   ├── state.py                     # SystemState (TypedDict)
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── ingest.py                # INGEST_DAILY_DATA
│   │   ├── memory_update.py         # UPDATE_MARKET_MEMORY
│   │   ├── calibration.py           # DAILY_SIGNAL_CALIBRATION
│   │   ├── risk_check.py            # DAILY_RISK_CHECK
│   │   ├── policy.py                # DAILY_POLICY_SELECTION
│   │   ├── execution.py             # DAILY_EXECUTION_FEASIBILITY_CHECK
│   │   ├── order.py                 # DAILY_ORDER_PLAN_GENERATION
│   │   ├── logging_node.py          # DAILY_POST_EXECUTION_LOGGING
│   │   ├── weekly_market.py         # WEEKLY_MARKET_ANALYSIS_MEETING
│   │   ├── weekly_strategy.py       # WEEKLY_STRATEGY_DEVELOPMENT_MEETING
│   │   ├── propagation_audit.py     # WEEKLY_PROPAGATION_AUDIT
│   │   ├── risk_alert.py            # RISK_ALERT_MEETING
│   │   └── consolidation.py         # MEMORY_CONSOLIDATION
│   ├── edges/
│   │   ├── __init__.py
│   │   ├── daily_edges.py           # 일간 전이 규칙
│   │   ├── weekly_edges.py          # 주간 전이 규칙
│   │   └── event_edges.py           # event-driven 전이 규칙
│   └── builder.py                   # Graph 조립
│
├── memory/
│   ├── __init__.py
│   ├── base_memory.py               # BaseMemory (공통 인터페이스)
│   ├── market_memory.py             # OHLCV, factors, technicals
│   ├── reports_memory.py            # weekly reports, debate resolutions
│   ├── strategy_memory.py           # strategy templates, sim outcomes
│   ├── decision_journal.py          # policy decisions, outcomes
│   └── retrieval/
│       ├── __init__.py
│       ├── retriever.py             # top-k retrieval
│       └── validity_scorer.py       # RetrievalScore 계산
│
├── ledger/
│   ├── __init__.py
│   └── shared_ledger.py             # 공식 output 전용 기록소
│
├── transforms/
│   ├── __init__.py
│   ├── emily_to_bob.py              # Emily full report → Bob feature packet
│   ├── bob_to_dave.py               # Bob strategy → Dave risk packet
│   ├── bob_to_execution.py          # Bob strategy → Execution feasibility packet
│   └── all_to_otto.py               # 3개 packet → Otto policy packet
│
├── calibration/
│   ├── __init__.py
│   └── calibrator.py                # rolling std, normalization, shrinkage, clipping
│
├── audit/
│   ├── __init__.py
│   └── propagation_audit.py         # adopted rate, dropped signal rate, semantic sim
│
├── reliability/
│   ├── __init__.py
│   └── agent_reliability.py         # reliability state, update, conditional gating
│
├── data/
│   ├── __init__.py
│   ├── polygon_fetcher.py           # 기존 코드 이식 + 개선
│   ├── data_manager.py              # 데이터 전처리, missing flag
│   └── missing_protocol.py          # missing-data protocol
│
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py                   # 성과 지표 전체
│   ├── ablation.py                  # ablation suite
│   ├── backtester.py                # point-in-time safe backtester
│   └── baselines.py                 # baseline comparisons
│
├── tests/
│   ├── unit/
│   │   ├── test_schemas.py
│   │   ├── test_llm_providers.py
│   │   ├── test_transforms.py
│   │   ├── test_calibration.py
│   │   └── test_retrieval.py
│   └── integration/
│       ├── test_weekly_cycle.py
│       ├── test_daily_cycle.py
│       └── test_risk_alert.py
│
├── orchestrator.py                  # 메인 진입점
├── requirements.txt
├── .env.example
└── README.md
```

---

## 5. 핵심 설계 명세

### 5.1 SystemState (LangGraph)

```python
# graph/state.py
class SystemState(TypedDict):
    # 시간 컨텍스트
    current_date: str
    cycle_type: Literal["daily", "weekly", "event"]
    is_week_end: bool

    # Raw data
    raw_market_data: Optional[dict]
    raw_news: Optional[list]

    # Agent 공식 outputs
    emily_output: Optional[EmilyOutput]
    bob_output: Optional[BobOutput]
    dave_output: Optional[DaveOutput]
    otto_output: Optional[OttoOutput]

    # Transformation packets
    emily_to_bob_packet: Optional[EmilyToBobPacket]
    bob_to_dave_packet: Optional[BobToDavePacket]
    bob_to_execution_packet: Optional[BobToExecutionPacket]
    otto_policy_packet: Optional[OttoPolicyPacket]

    # 제어 신호
    risk_alert_triggered: bool
    risk_score: float
    uncertainty_level: float
    technical_confidence: float

    # Agent reliability
    agent_reliability: dict  # {"emily": 0.8, "bob": 0.7, ...}

    # 감사 / 캘리브레이션
    propagation_audit_log: list
    calibration_log: list
    skip_log: list           # 스킵된 노드와 이유
    retry_log: list          # 재시도된 노드와 이유

    # 메모리 retrieval 결과
    retrieved_market_cases: Optional[list]
    retrieved_strategy_cases: Optional[list]

    # 실행
    execution_plan: Optional[dict]
    execution_feasibility_score: float

    # 주간 meeting 출력
    weekly_market_report: Optional[dict]
    debate_resolution: Optional[dict]
    signal_conflict_resolution: Optional[dict]
    weekly_strategy_set: Optional[dict]

    # 다음 노드 제어
    next_node: Optional[str]
    flow_decision_reason: Optional[str]
```

### 5.2 LLM Provider 추상화

```python
# llm/base.py
from abc import ABC, abstractmethod
from typing import Optional, List

class BaseLLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        response_format: Optional[dict] = None,  # JSON schema 강제용
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """동기 chat completion. JSON string 반환."""
        ...

    @abstractmethod
    def name(self) -> str:
        """provider 이름 반환"""
        ...
```

```yaml
# config/system_config.yaml
llm:
  provider: "anthropic"       # anthropic | openai | ollama
  model: "claude-opus-4-5"    # provider별로 다름
  temperature: 0.2
  max_tokens: 4096

thresholds:
  risk_alert: 0.75
  reliability_floor: 0.35
  calibration_shrinkage: 0.3
  retrieval_floor: 0.4
  execution_feasibility_floor: 0.5
  agent_confidence_floor: 0.45

cadence:
  weekly_cycle_day: "friday"
  daily_start_time: "09:00"
  timezone: "America/New_York"
```

### 5.3 BaseAgent

```python
# agents/base_agent.py
class BaseAgent:
    def __init__(self, llm: BaseLLMProvider, config: dict):
        self.llm = llm
        self.config = config
        self.max_retries = 3

    def run(self, input_packet: dict, state: SystemState) -> dict:
        """
        1. system prompt 로드
        2. retrieval context 붙이기 (있으면)
        3. LLM 호출
        4. schema validation
        5. 실패 시 retry (max_retries까지)
        6. calibration 통과
        7. 결과 반환
        """
        ...

    def _build_prompt(self, input_packet, retrieved_cases) -> List[dict]:
        ...

    def _validate_output(self, raw: str, schema_class) -> dict:
        ...

    def _should_retry(self, output: dict, attempt: int) -> tuple[bool, str]:
        """LLM 판단으로 재시도 여부 결정"""
        ...
```

### 5.4 Risk Score 수식

```
R_score = w1 * beta_norm + w2 * illiquidity_norm + w3 * sector_exposure_norm + w4 * volatility_norm

기본값: w1=0.3, w2=0.25, w3=0.25, w4=0.2
threshold: 0.75 → Risk Alert Meeting 트리거

signal_conflict_risk (보조 지표):
- technical vs macro 방향 불일치 시 상승
- strategy regime mismatch 시 상승
- R_score 대체 아님, escalation 우선순위 보조용
```

### 5.5 Dual Reward 수식

```
CombinedReward_t(μ) = w_sim_t * r_sim_t(μ) + w_real_t * r_real_t(μ)

w_sim_t = sigmoid(sum r_sim_i / sum(r_sim_i + r_real_i + eps))  for i in [t-n, t]
w_real_t = 1 - w_sim_t

Utility_t(μ) = CombinedReward_t(μ)
             - λ1 * RiskScore_t
             - λ2 * ConstraintViolationPenalty_t
             - λ3 * MarketAlignmentPenalty_t
             - λ4 * ExecutionFeasibilityPenalty_t
             - λ5 * AgentReliabilityPenalty_t

기본값: λ1=0.3, λ2=0.2, λ3=0.15, λ4=0.2, λ5=0.15
주의: r_sim과 r_real은 반드시 동일 스케일로 정규화 후 사용할 것
```

### 5.6 Retrieval Validity Score

```
RetrievalScore(case) = Sim(query, case)
                     × RecencyDecay(case_age)
                     × RegimeMatch(current_regime, case_regime)
                     × DataQualityScore(case)
                     × OutcomeReliability(case)

floor 이하 case 폐기
top-k: 5~10
현재 시점 이후 데이터 참조 절대 금지
```

---

## 6. Agent 명세

### 6.1 Emily — Market Analyst

**역할**: 시장 상태를 전략 가능한 feature space로 변환. Technical signal을 공식 출력에 포함.

**입력**: raw market data, news, macro indicators, technical indicators, prior reports

**핵심 출력 (반드시 포함)**:
```json
{
  "agent": "Emily",
  "date": "YYYY-MM-DD",
  "market_regime": "risk_on|risk_off|mixed|fragile_rebound|transition",
  "regime_confidence": 0.0,
  "macro_state": {
    "rates": 0.0, "inflation": 0.0, "growth": 0.0,
    "liquidity": 0.0, "risk_sentiment": 0.0
  },
  "technical_signal_state": {
    "trend_direction": "up|down|mixed",
    "continuation_strength": 0.0,
    "reversal_risk": 0.0,
    "technical_confidence": 0.0
  },
  "sector_preference": [{"sector": "...", "score": 0.0}],
  "bull_catalysts": [],
  "bear_catalysts": [],
  "event_sensitivity_map": [],
  "technical_conflict_flags": [],
  "risk_flags": [],
  "uncertainty_reasons": [],
  "recommended_market_bias": "selective_long|defensive|neutral"
}
```

**Emily → Bob Transformation Packet**:
```json
{
  "regime": "risk_on",
  "regime_confidence": 0.73,
  "preferred_sectors": ["semiconductor"],
  "avoid_sectors": ["utilities"],
  "market_bias": "selective_long",
  "event_risk_level": 0.42,
  "market_uncertainty": 0.38,
  "technical_direction": "up",
  "technical_confidence": 0.77,
  "reversal_risk": 0.21
}
```

**제어 규칙**:
- regime_confidence < 0.55 → Bob은 candidate diversity 증가
- technical_confidence 높음 → Bob은 technical-aligned strategy 가중
- reversal_risk 높음 → Otto는 directional exposure 축소 우선

### 6.2 Bob — Strategy Analyst

**역할**: Emily packet을 전략 후보 집합으로 변환 + simulated trading 검증

**반드시**: technical_confidence 높으면 technical-aligned candidate 1개 이상 포함

**핵심 출력**:
```json
{
  "agent": "Bob",
  "date": "YYYY-MM-DD",
  "candidate_strategies": [{
    "name": "trend_following_long",
    "type": "directional",
    "logic_summary": "...",
    "regime_fit": 0.0,
    "technical_alignment": 0.0,
    "sim_window": {"train_start": "...", "train_end": "..."},
    "sim_metrics": {
      "return": 0.12, "sharpe": 1.42, "sortino": 1.88,
      "mdd": 0.07, "turnover": 0.31, "hit_rate": 0.56
    },
    "failure_conditions": [],
    "optimization_suggestions": [],
    "confidence": 0.73
  }],
  "selected_for_review": []
}
```

**금지**: 현재 시점 이후 데이터 사용, simulation period 미기재

### 6.3 Dave — Risk Analyst

**역할**: 전략을 제약과 경보가 있는 위험 공간 위에 올리는 agent

**R_score > 0.75 시 즉시 Risk Alert Meeting 트리거**

**핵심 출력**:
```json
{
  "agent": "Dave",
  "date": "YYYY-MM-DD",
  "risk_score": 0.81,
  "risk_components": {
    "beta": 0.22, "illiquidity": 0.15,
    "sector_concentration": 0.17, "volatility": 0.08
  },
  "signal_conflict_risk": 0.0,
  "stress_test": {"severity_score": 0.72, "worst_case_drawdown": 0.13},
  "risk_level": "low|medium|high|critical",
  "recommended_controls": [],
  "risk_constraints": {
    "max_single_sector_weight": 0.25,
    "max_beta": 1.05,
    "max_gross_exposure": 0.80
  },
  "trigger_risk_alert_meeting": true
}
```

### 6.4 Otto — Fund Manager

**역할**: 공식 packet만 통합해서 최종 policy 선택. Raw data 직접 해석 절대 금지.

**입력**: Emily packet, Bob packet, Dave packet, Execution packet, reward history, reliability summary

**Otto 금지 사항** (하드코딩으로 강제):
- raw 뉴스 직접 해석
- raw OHLCV 직접 해석
- strategy 재생성
- risk score 재계산
- raw retrieval text 직접 열람

**핵심 출력**:
```json
{
  "agent": "Otto",
  "date": "YYYY-MM-DD",
  "candidate_policies": [],
  "adaptive_weights": {"w_sim": 0.44, "w_real": 0.56, "lookback_steps": 8},
  "selected_policy": "trend_following_long_plus_hedge",
  "allocation": {"equities": 0.55, "hedge": 0.10, "cash": 0.35},
  "execution_plan": {
    "entry_style": "staggered",
    "rebalance_frequency": "weekly",
    "stop_loss": 0.06
  },
  "policy_reasoning_summary": [],
  "approval_status": "approved|approved_with_modification|conditional_approval|rejected"
}
```

---

## 7. Meeting 프로토콜

### 7.1 Weekly Market Analysis Meeting

**순서**:
1. Emily regime report 생성
2. Technical sub-signal summary 생성
3. Bob quantitative augmentation
4. Dave risk interpretation
5. Bull/Bear debate sub-step
6. Signal conflict resolution sub-step
7. Final market report 확정
8. Reports Memory + Ledger 기록

**Debate sub-step 출력** (반드시 공식 상태로 저장):
```json
{
  "bull_case": {"growth_path": "...", "upside_catalysts": []},
  "bear_case": {"downside_risks": [], "reversal_triggers": []},
  "moderator_summary": "...",
  "unresolved_issues": [],
  "regime_confidence_adjustment": 0.0
}
```

**Signal Conflict Resolution 출력**:
```json
{
  "conflict_matrix": [{
    "signal_a": "technical_momentum_strong",
    "signal_b": "macro_risk_off",
    "conflict_type": "time_horizon_mismatch",
    "resolution": "reduce gross exposure, keep selective long"
  }]
}
```

### 7.2 Weekly Strategy Development Meeting

**순서**: Bob 후보 생성 → Bob sim → Bob failure conditions → Dave risk review → Emily regime fit review → Strategy debate → Selection → Memory + Ledger

**중요**: selected strategy ≠ execution order. Execution feasibility packet 별도 생성 필수.

### 7.3 Risk Alert Meeting

**트리거**: risk_score > 0.75, liquidity shock, drawdown breach, technical reversal shock, high signal_conflict_risk

**수식**:
```
RiskAdjustedUtility_t(μ) = (1-λ) * CombinedReward_t(μ) - λ * RiskReward_t(μ)
RiskReward_t(μ) = -a*R_score - b*StressSeverity + c*SentimentSafety - d*TechnicalReversalPenalty
```

---

## 8. 구현 단계 (Phase 상세)

### Phase 1: 환경 & 뼈대 (Architect)
**목표**: 프로젝트 구조 생성, 의존성 설정, config 작성

작업 목록:
- [ ] `~/Desktop/hybrid-investment-system/` 디렉토리 전체 구조 생성
- [ ] `requirements.txt` 작성 (langgraph, pydantic, anthropic, openai, polygon-api-client, faiss-cpu, numpy, pandas, pytest 등)
- [ ] `.env.example` 작성
- [ ] `config/system_config.yaml` 작성 (위 5.2 명세 기준)
- [ ] `config/agent_config.yaml` 작성
- [ ] `README.md` 초안

완료 기준: `pip install -r requirements.txt` 성공, 디렉토리 구조 일치

---

### Phase 2: Schema 전체 (Architect + Agent Engineer)
**목표**: v3.6 명세 기반 Pydantic schema 전체 작성

작업 목록:
- [ ] `schemas/base_schema.py` — 공통 base, 공통 field
- [ ] `schemas/emily_schema.py` — EmilyOutput, EmilyToBobPacket
- [ ] `schemas/bob_schema.py` — BobOutput, BobToDavePacket, BobToExecutionPacket
- [ ] `schemas/dave_schema.py` — DaveOutput
- [ ] `schemas/otto_schema.py` — OttoOutput, ExecutionPlan
- [ ] `schemas/meeting_schema.py` — DebateResolution, SignalConflictResolution, WeeklyMarketReport, WeeklyStrategySet
- [ ] `schemas/audit_schema.py` — PropagationAuditLog, CalibrationLog, NodeResult
- [ ] `tests/unit/test_schemas.py` — 모든 schema 유효성 테스트

완료 기준: 모든 schema unittest 통과

---

### Phase 3: LLM Provider 추상화 (LLM Engineer)
**목표**: 어떤 provider든 교체 가능한 추상화 계층

작업 목록:
- [ ] `llm/base.py` — BaseLLMProvider ABC
- [ ] `llm/providers/anthropic_provider.py` — claude-opus-4-5 기본
- [ ] `llm/providers/openai_provider.py` — gpt-4o 기본
- [ ] `llm/providers/ollama_provider.py` — local model
- [ ] `llm/factory.py` — config 읽고 provider 인스턴스 반환
- [ ] `tests/unit/test_llm_providers.py` — mock 기반 테스트

완료 기준: config 한 줄만 바꾸면 provider 교체 됨, mock 테스트 통과

---

### Phase 4: Data Layer (Data Engineer)
**목표**: Polygon.io 데이터 연결, missing-data protocol

작업 목록:
- [ ] `data/polygon_fetcher.py` — 기존 trading-agents 코드 이식 + 개선
  - OHLCV, 뉴스, 재무 데이터
  - point-in-time constraint 적용
- [ ] `data/data_manager.py` — 전처리, 정규화, sector mapping
- [ ] `data/missing_protocol.py` — missing flag 생성, confidence shrinkage
  - No news → "No material news" 명시, hallucination 금지
  - NaN → missing flag와 함께 전달
  - stale data → freshness check
- [ ] `tests/unit/test_data.py`

완료 기준: 실제 Polygon API 호출 성공, missing data 처리 확인

---

### Phase 5: Agent 구현 (Agent Engineer)
**목표**: Emily, Bob, Dave, Otto 구현

작업 목록:
- [ ] `agents/base_agent.py` — retry 로직, schema validation, logging
- [ ] `prompts/emily_system.md` — Emily system prompt (v3.6 기준)
- [ ] `prompts/bob_system.md`
- [ ] `prompts/dave_system.md`
- [ ] `prompts/otto_system.md`
- [ ] `agents/emily.py` — Emily 구현
- [ ] `agents/bob.py` — Bob 구현
- [ ] `agents/dave.py` — Dave 구현 (R_score 수식 포함)
- [ ] `agents/otto.py` — Otto 구현 (raw data 접근 차단 포함)
- [ ] `tests/unit/test_agents.py` — mock LLM으로 각 agent 테스트

완료 기준: 각 agent가 mock LLM으로 올바른 schema 출력 확인

---

### Phase 6: Transformation Layer (Transform Engineer)
**목표**: agent 간 정보 변환 계층

작업 목록:
- [ ] `transforms/emily_to_bob.py` — Emily full output → Bob feature packet
- [ ] `transforms/bob_to_dave.py` — Bob strategy → Dave risk packet
- [ ] `transforms/bob_to_execution.py` — Bob → Execution feasibility packet
- [ ] `transforms/all_to_otto.py` — 3 packets → Otto policy packet
- [ ] `tests/unit/test_transforms.py` — 각 transformation 입출력 테스트

완료 기준: 각 transform이 올바른 packet 생성, downstream agent가 바로 사용 가능

---

### Phase 7: Calibration & Audit (Transform Engineer)
**목표**: score drift 방지, signal propagation 추적

작업 목록:
- [ ] `calibration/calibrator.py`
  - rolling standardization (agent별)
  - sector-relative normalization
  - confidence-based shrinkage toward neutral
  - outlier clipping
  - missing-value safe fallback
- [ ] `audit/propagation_audit.py`
  - adopted keyword rate
  - dropped critical signal rate
  - contradiction after transformation
  - semantic similarity (source packet vs target summary)
  - technical signal adoption rate
- [ ] `tests/unit/test_calibration.py`

완료 기준: calibration이 실제 score에 반영됨, audit log가 state에 기록됨

---

### Phase 8: Agent Reliability & Gating (Reliability Engineer)
**목표**: agent별 신뢰도 추적, conditional gating

작업 목록:
- [ ] `reliability/agent_reliability.py`
  - reliability state 초기화 (cold start: 0.5 neutral)
  - update 로직 (decision usefulness, contradiction freq, propagation adoption, outcome alignment)
  - conditional gating 규칙
  - floor 이하 agent → hard gating or downweighting
- [ ] Otto가 reliability summary를 policy selection에 반영하는 로직 연결

완료 기준: reliability가 실제로 Otto의 approval 결정에 영향을 줌

---

### Phase 9: Memory Layer (Memory Engineer)
**목표**: 4개 memory 계층, retrieval, validity scoring

작업 목록:
- [ ] `memory/base_memory.py` — 공통 인터페이스
- [ ] `memory/market_memory.py` — OHLCV, factors, technicals 저장/조회
- [ ] `memory/reports_memory.py` — weekly reports, debate resolutions
- [ ] `memory/strategy_memory.py` — strategy templates, sim outcomes
- [ ] `memory/decision_journal.py` — policy decisions, outcomes, overrides
- [ ] `memory/retrieval/retriever.py` — top-k retrieval, timestamp guard
- [ ] `memory/retrieval/validity_scorer.py` — RetrievalScore 수식 구현
- [ ] `ledger/shared_ledger.py` — 공식 output만 저장, raw chain-of-thought 금지
- [ ] `tests/unit/test_retrieval.py`

완료 기준: retrieval이 future data 참조 없이 작동, validity score가 계산됨

---

### Phase 10: LangGraph 구성 (Graph Engineer)
**목표**: 전체 state machine을 LangGraph로 구현 (유연한 흐름 포함)

작업 목록:
- [ ] `graph/state.py` — SystemState TypedDict 전체
- [ ] `graph/nodes/` — 각 node 구현
  - 각 node는 NodeResult 반환 (next, skip_reason, retry, confidence)
  - LLM 판단으로 스킵/재시도 가능
- [ ] `graph/edges/daily_edges.py` — 일간 conditional edges
- [ ] `graph/edges/weekly_edges.py` — 주간 conditional edges
- [ ] `graph/edges/event_edges.py` — event-driven edges
- [ ] `graph/builder.py` — 전체 graph 조립
- [ ] 스킵 가능한 노드 명시:
  - DAILY_RISK_CHECK: risk_score 매우 낮고 regime stable → 경량화
  - WEEKLY market analysis debate: Emily confidence 매우 높음 → 간소화
  - Signal conflict resolution: technical/macro 방향 일치 → 스킵 가능
- [ ] 재시도 가능한 노드 명시:
  - Schema validation 실패 시 자동 재시도 (max 3회)
  - Confidence threshold 미달 시 재시도

완료 기준: graph가 실제로 실행되고 state가 올바르게 전이됨

---

### Phase 11: Meeting 구현 (Agent Engineer + Graph Engineer)
**목표**: 3개 meeting 프로토콜 구현

작업 목록:
- [ ] `meetings/base_meeting.py`
- [ ] `meetings/market_analysis.py` — debate sub-step, signal conflict resolution 포함
- [ ] `meetings/strategy_development.py` — execution feasibility packet 별도 생성
- [ ] `meetings/risk_alert.py` — RiskAdjustedUtility 수식 구현
- [ ] `tests/integration/test_weekly_cycle.py`

완료 기준: weekly meeting 1회 end-to-end 실행, ledger에 결과 기록

---

### Phase 12: Orchestrator & 통합 (Graph Engineer + Test Engineer)
**목표**: 전체 시스템 통합, 메인 진입점

작업 목록:
- [ ] `orchestrator.py` — graph 실행, cycle 관리, 로깅
- [ ] daily cycle end-to-end 테스트
- [ ] weekly cycle end-to-end 테스트
- [ ] event-driven cycle 테스트
- [ ] `PROGRESS_LOG.md` 업데이트

완료 기준: 실제 데이터로 1주치 시뮬레이션 완료

---

### Phase 13: Evaluation Suite (Eval Engineer)
**목표**: 성과 측정, ablation, baseline 비교

작업 목록:
- [ ] `evaluation/metrics.py` — 전체 지표 (섹션 12 기준)
- [ ] `evaluation/backtester.py` — point-in-time safe, look-ahead bias 방지
- [ ] `evaluation/baselines.py` — 8개 baseline
- [ ] `evaluation/ablation.py` — 12개 ablation
- [ ] propagation / signal 평가 지표 추가:
  - technical signal adoption rate
  - source-to-manager semantic similarity
  - dropped critical signal rate
  - agent-specific marginal utility

완료 기준: ablation 결과가 시스템 개선 근거를 설명함

---

### Phase 14: 최종 검증 & 문서화 (Director)
**목표**: 전체 시스템 검증, 문서 완성

작업 목록:
- [ ] 전체 테스트 스위트 통과
- [ ] leakage-safe evaluation 확인
- [ ] PROGRESS_LOG.md 최종 정리
- [ ] README.md 완성
- [ ] DESIGN_SPEC_v3.6.md 와 구현 간 괴리 목록 작성

---

## 9. 구현 금지 사항 (반드시 지킬 것)

이하 사항을 위반하는 구현은 Director가 즉시 롤백 지시한다.

- simulated trading을 단순 backtest utility로만 만들지 말 것
- shared ledger를 전체 내부 추론 dump로 쓰지 말 것
- Emily/Bob/Dave/Otto가 동일 raw input을 전부 같이 보게 하지 말 것
- Otto가 raw 뉴스/OHLCV를 직접 해석하게 하지 말 것
- risk alert를 단순 warning log로 끝내지 말 것
- adaptive weighting을 placeholder 변수로만 두지 말 것
- debate를 장식용 찬반 문장으로만 두지 말 것
- selected strategy를 곧바로 execution order로 취급하지 말 것
- confidence/uncertainty를 출력만 하고 제어 로직에 안 쓰지 말 것
- retrieval에서 cosine similarity만 보고 오래된 case 그대로 쓰지 말 것
- technical signal을 macro/news 요약 안에 묻히게 하지 말 것
- calibration 없이 raw score를 상위 단계로 누적하지 말 것
- propagation audit 없이 "전달됐다고 가정"하지 말 것
- LangGraph를 단순 순차 파이프라인으로만 쓰지 말 것 (LLM 판단 기반 흐름 제어 필수)

---

## 10. Empty-case / Missing-data Protocol

- **News 없음**: "No material news" 명시, hallucinated catalyst 절대 금지
- **Financial data 누락**: NaN → missing flag와 함께 전달, confidence shrinkage
- **Technical signal 충돌**: conflict flag 생성, directional conviction 자동 하향
- **Execution feasibility 불충분**: phased execution 또는 hold 검토
- **Stale retrieval**: freshness 부족 case 제거, 사용 시 weight 감쇠

---

## 11. Shared Ledger 규칙

**저장할 것 (공식 output만)**:
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

**저장하지 않을 것**:
- raw chain-of-thought
- agent 내부 임시 스케치
- 모든 retrieval 결과 전문
- 토론 전체 transcript
- LLM 중간 추론 과정

---

## 12. 기존 프로젝트 참고 가이드

`~/Desktop/trading-agents/` 에서 참고 가능한 것:
- `polygon_fetcher.py` 또는 유사 파일 → `data/polygon_fetcher.py` 이식
- 기존 analyst agent system prompt 구조 → 참고용 (그대로 쓰지 말 것)
- 기존 LangGraph graph 구조 → 참고용

**절대 건드리지 말 것**: `~/Desktop/trading-agents/` 원본, `~/Desktop/news-pipeline/`

---

## PROGRESS LOG

> 이 섹션은 Director가 관리한다. 절대 덮어쓰지 말고 아래에 계속 append한다.

```
[시작]
날짜: TBD
상태: 브리핑 문서 작성 완료, Claude Code 작업 대기 중
다음 단계: Phase 1 (Architect sub-agent) 시작
```

---

*이 문서는 K와 Claude가 함께 설계한 Hybrid Multi-Agent Investment System v3.6의 공식 구현 핸드오프 문서다. 설계 기반: TradingAgents, QuantAgents, Expert Investment Teams 논문 및 v3.6 기획서.*
