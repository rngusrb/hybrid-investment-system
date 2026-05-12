# DEV_GUIDE — Hybrid Investment System 코드 작성 참고서

> 이 문서는 코드 작성 전 반드시 읽는 참고서입니다.
> CLAUDE.md(설계 원칙)와 별개로, **실제 코드 수정 시 따르는 프로토콜**을 정의합니다.

---

## ★ 대규칙 — 모든 작업에 반드시 따를 것

```
1. 작업 전  → 해당 폴더 _GUIDE.md 확인
2. 작업 전  → harness 실행으로 현재 상태 파악
              python scripts/harness.py <폴더>/
3. 코드 수정
4. 작업 후  → harness 재실행으로 검증
              python scripts/harness.py <폴더>/
5. 실패 시  → 원인 파악 → 코드 수정 → 4번으로 (max 10회)
6. 통과 시  → _GUIDE.md ## 금지사항에 새 패턴 추가 (사고 이력 포함)
              → 6번 완료 전까지 "완료" 선언 금지
7. GC 체크  → python scripts/harness.py <폴더>/ --gc
```

**루프 기본값: 전부 통과할 때까지 반복. 중간에 묻지 않음.**
**특히 6번 _GUIDE.md 갱신이 핵심 — 같은 실수가 반복되는 유일한 이유는 규칙이 안 쌓였기 때문.**

> ⚠️ **_GUIDE.md / DEV_GUIDE.md 업데이트 원칙**
> - 해당 파일에 **실제 변경사항(버그 수정, 금지 규칙 추가, 새 파일/기능 추가)이 있을 때만** 업데이트.
> - 작업 완료 인사, 점검만 한 경우, 코드 내용 재확인만 한 경우에는 업데이트 금지.
> - 이유: 불필요한 업데이트가 반복되면 "최근 변경" 섹션이 오염되어 실제 변경 추적이 불가능해짐.

---

## 시스템 전체 구조 (2026-05-12 기준)

이 프로젝트는 **3개의 실행 경로**가 공존한다: Pipeline A (SPY 분석), B/C 운영 루프 (bc_graph LangGraph), 그리고 단일 종목 CLI (stock_pipeline).

---

### 파이프라인 A — SPY 포트폴리오 시스템 (LangGraph 기반)

```
[Polygon API]
     │ OHLCV + News (SPY 고정)
     ▼
[ingest node]  ← graph/nodes/ingest.py
     │ raw_market_data (SystemState 경유)
     ▼
[Emily Agent]  ← agents/emily.py, schemas/emily_schema.py
     │ EmilyOutput: market_regime, technical_confidence, reversal_risk
     │ emily_to_bob_packet (transforms/emily_to_bob.py)
     ▼
[Bob Agent]    ← agents/bob.py, schemas/bob_schema.py
     │ BobOutput: candidate_strategies + simulation/
     │ bob_to_dave_packet (transforms/bob_to_dave.py)
     ▼
[Dave Agent]   ← agents/dave.py, schemas/dave_schema.py
     │ DaveOutput: risk_score, risk_components (컴포넌트 가중합으로 강제 덮어씀)
     ▼
[all_to_otto]  ← transforms/all_to_otto.py (raw data 하드 차단)
     ▼
[Otto Agent]   ← agents/otto.py, schemas/otto_schema.py
     │ OttoOutput:
     │   allocation: {equities, hedge, cash}  ← 포트폴리오 비중
     │   execution_plan: {entry_style, rebalance_frequency, stop_loss}
     │   approval_status: approved / rejected / conditional
     ▼
[policy node]  ← graph/nodes/policy.py, utils/utility.py
     │ utility_score, otto_policy_packet
     ▼
[order node]   ← graph/nodes/order.py, execution/position_sizer.py
     │ OrderPlan: shares, stop_loss, slippage
     ▼
[logging node] ← graph/nodes/logging_node.py, utils/forward_return.py
     │ r_sim, r_real → strategy_memory (memory/strategy_memory.py)
     ▼
[memory]       ← memory/ (in-memory, 재시작 시 초기화)
     └─ market_memory, strategy_memory, decision_journal, reports_memory
```

**진입점**: `orchestrator.py`
**LLM 주입**: `use_real_llm=True` 시 `_llm_analyst`, `_llm_decision`, `_polygon_fetcher`를 SystemState에 주입
**테스트 기본값**: `use_real_llm=False` (API 호출 없음)

---

### 파이프라인 B — 개별 종목 TradingAgents 시스템

```
[Polygon API]
     │ OHLCV(180일) + News(30일) + 재무제표(2년) + EPS/PE
     ▼
fetch_data()   ← scripts/stock_pipeline.py
     │ ticker, bars, articles, financials, eps, pe_ratio
     ▼
┌─────────────────────────────────────────────────────────┐
│  4개 Analyst (순차 실행)                                 │
│                                                         │
│  [Fundamental Analyst]  ← prompts/fundamental_system.md │
│       FundamentalAnalystOutput: score, intrinsic_value  │
│                                                         │
│  [Sentiment Analyst]    ← prompts/sentiment_system.md   │
│       SentimentAnalystOutput: score, dominant_emotion   │
│                                                         │
│  [News Analyst]         ← prompts/news_system.md        │
│       NewsAnalystOutput: macro_impact, event_risk       │
│                                                         │
│  [Technical Analyst]    ← prompts/technical_system.md   │
│       TechnicalAnalystOutput: score, RSI, MACD, signal  │
└─────────────────────────────────────────────────────────┘
     ▼
[Researcher]  ← prompts/researcher_system.md
     │ Bull/Bear 토론 → consensus, conviction, risk_reward_ratio
     ▼
[Trader]      ← prompts/trader_system.md
     │ action: BUY/SELL/HOLD (초안)
     │ confidence, position_size_pct, target_price, stop_loss_price
     ▼
[Risk Manager] ← prompts/risk_manager_system.md
     │ 3인 토론 (Aggressive Rick / Conservative Clara / Neutral Nathan)
     │ final_action, final_position_size_pct, cash_reserve_pct
     │ hedge_type, risk_level, risk_flags
     ▼
print_results() (터미널 출력)
```

**진입점**: `scripts/stock_pipeline.py AAPL --date 2024-01-15 --verbose`
**스키마**: `schemas/stock_schemas.py` (7개: Fundamental/Sentiment/News/Technical/Researcher/Trader/RiskManager)
**LLM**: `llm/factory.py create_provider(node_role=...)` (analyst / decision 분리)

---

### 파이프라인 B/C — LangGraph 상태 기계 (2026-04-28 전환)

날짜 범위 반복 실행은 `run_loop.py` → `bc_graph.py` 로 통합됐다.

```
python scripts/run_loop.py AAPL NVDA TSLA --start 2024-01-01 --end 2024-03-31

[bc_graph.py — StateGraph(SystemStateBC)]

  BC_EMILY          ← Emily SPY 레짐 분석 (emily_context 생성)
       ↓
  BC_STOCK_ANALYSIS ← 종목별 파이프라인 B 실행 (gating 적용)
       ↓
  BC_BACKTESTER     ← 6개 전략 Pool 백테스트 (emily_context, risk_mode 지원)
       ↓ [route_after_backtester]
  BC_MEETINGS       ← MAM/SDM/RAM (llm 토론 포함)
       ↓
  BC_CALIBRATION       ← 신뢰도 감사 + gating 갱신 → reliability_summary 추출
       ↓
  BC_RELIABILITY_UPDATE ← reliability_state.json 영속 + state reliability_summary 갱신
       ↓
  BC_PORTFOLIO_MANAGER ← Portfolio Manager (otto_feedback 주입 지원) → execution_feasibility 계산
       ↓
  BC_DAVE              ← 포트폴리오 리스크 평가 (avg_sharpe < 0.5 → stress_multiplier)
       ↓ [route_after_dave]
       ├─ risk_score > 0.7 (첫 1회) → BC_BACKTESTER_DEFENSIVE → BC_PORTFOLIO_MANAGER → BC_DAVE
       └─ else →
  BC_OTTO              ← 최종 승인 게이트
       ↓ [route_after_otto]
       ├─ rejected + retry <= 2 → BC_PORTFOLIO_MANAGER (otto_retry_count++)
       └─ else → END
```

**Conditional edges (핵심)**
- `Dave risk_score > 0.7` → defensive 백테스터 재실행 (momentum -20%, directional -15%)
- `Otto rejected + retry <= 2` → Portfolio Manager 재실행 (rejection reason 주입)

**E-001~E-004 uncertainty/reliability 체인**
- `Emily regime_confidence < 0.55` → `uncertainty_mode=True`, lookback=30, candidate_strategies 포함
- `avg_sharpe < 0.5` → Dave stress_multiplier 적용 (최대 1.15배, risk_score 상향)
- `Dave risk > 0.7 + Emily conf < 0.55` → Otto: total_equity_pct × 0.85 shrinkage
- `reliability[trader|risk_manager|researcher] < 0.35` → Otto: approved → conditional_approval 강제
- `execution_feasibility < 0.4` → Otto: execution_style = staggered 강제

**SystemStateBC 주요 필드** (`graph/bc_state.py`)
- `uncertainty_mode` — Emily confidence < 0.55 시 True
- `reliability_summary` — agent별 EMA 신뢰도 점수 (CALIBRATION/RELIABILITY_UPDATE 갱신)
- `execution_feasibility` — feasibility_score + rebalance_urgency (PORTFOLIO_MANAGER 계산, OTTO 재산출)

**관련 파일**
- `graph/bc_state.py` — SystemStateBC TypedDict + make_initial_bc_state()
- `graph/bc_graph.py` — build_bc_graph() / compile_bc_graph()
- `graph/nodes/bc_*.py` — 10개 노드 (emily/stock/backtester/meetings/calibration/reliability_update/portfolio/dave/otto + defensive)
- `scripts/run_loop.py` — 날짜 범위 루프, bc_graph.invoke() 호출
- `scripts/run_eval.py` — 평가 파이프라인 (CR/ARR/SR/MDD vs baselines)
- `scripts/portfolio_pipeline.py` — 단일 날짜 one-off 실행용 (레거시 호환)

**스키마**: `schemas/portfolio_schemas.py` (StockAllocation, PortfolioManagerOutput)

---

### 세 파이프라인 비교

| 항목 | A (SPY 포트폴리오) | B (개별 종목) | B/C (운영 루프) |
|------|-------------------|---------------|----------------|
| 대상 | SPY 고정 | 임의 single ticker | 임의 N개 ticker × 날짜 범위 |
| 에이전트 | Emily→Bob→Dave→Otto | 4 Analysts→Researcher→Trader→RiskMgr | B × N + Emily/Dave/Otto + PM |
| 출력 | equities/hedge/cash % | BUY/SELL/HOLD + 리스크 조정 | 종목별 배분 + 현금/헤지 % |
| 현금/헤지 | Otto 결정 | RiskManager 권고 (개별) | Portfolio Manager + Otto 승인 |
| 메모리 | strategy_memory 누적 | 없음 (1회성) | run_memory (주기별 컨텍스트) |
| 실행 방식 | LangGraph 상태 그래프 | 함수 순차 호출 (1회성) | LangGraph bc_graph (conditional edges) |
| 진입점 | `orchestrator.py` | `scripts/stock_pipeline.py` | `scripts/run_loop.py` → `graph/bc_graph.py` |

---

### 미구현/의도적 제외 영역

| 영역 | 현재 상태 | 비고 |
|------|----------|------|
| FAISS dense retrieval | token overlap 기반 | 추후 |
| `r_real` T+1 업데이트 | T+7 guard | 실시간 모드 시 T+1 미확정 |
| 브로커 연결 | position_sizer까지만 | API 계정 필요 |
| 종목 간 상관관계 | 미구현 | Portfolio Manager 개선 시 |
| bc_graph 통합 테스트 | graph 전체 흐름 포함 | tests/integration/ (9개 파일) |

---

## 데이터 흐름 지도 (파이프라인 A 상세)

```
[Polygon API]
     │ OHLCV + News
     ▼
[ingest node] ──────────────────────────────────────┐
     │ raw_market_data                               │
     ▼                                               │
[Emily Agent]  ← schemas/emily_schema.py             │
     │ EmilyOutput                                   │
     │ emily_to_bob_packet (transforms/)             │
     ▼                                               │
[Bob Agent]    ← schemas/bob_schema.py               │
     │ BobOutput (candidate_strategies)              │
     │ + real backtest (simulation/)                 │
     │ bob_to_dave_packet (transforms/)              │
     ▼                                               │
[Dave Agent]   ← schemas/dave_schema.py              │
     │ DaveOutput (risk_score, risk_components)      │
     ▼                                               │
[all_to_otto]  ← transforms/all_to_otto.py           │
     │ 공식 패킷만 (raw data 차단)                    │
     ▼                                               │
[Otto Agent]   ← schemas/otto_schema.py              │
     │ OttoOutput (approval_status, allocation)      │
     ▼                                               │
[policy node]  ← utils/utility.py                    │
     │ utility_score, approval_status                │
     ▼                                               │
[order node]   ← execution/position_sizer.py         │
     │ OrderPlan (shares, stop_loss, slippage)       │
     ▼                                               │
[logging node] ← utils/forward_return.py             │
     │ r_sim, r_real → strategy_memory              ◄┘
     ▼
[strategy_memory] ← memory/strategy_memory.py
```

---

## "X를 바꾸려면 어디 봐라" 색인

| 바꾸려는 것 | 봐야 할 파일 |
|------------|------------|
| LLM 출력 자동 교정 | `agents/{agent}.py` → `_validate_output()` |
| LLM이 잘못 쓰는 필드명 추가 | `agents/bob.py` → `_TYPE_ALIASES`, `_SIM_METRICS_ALIASES` |
| 스키마 필드 추가/변경 | `schemas/{agent}_schema.py` + `prompts/{agent}_system.md` 동시 수정 |
| 재시도 조건 변경 | `agents/{agent}.py` → `_should_retry()` |
| 노드 실행 순서 | `graph/edges/daily_edges.py` + `graph/builder.py` |
| Risk score 계산식 | `agents/dave.py` → `compute_risk_score()` |
| Utility 계산식 | `utils/utility.py` → `compute_utility()` (여기만 수정, policy.py/otto.py는 자동 반영) |
| 포지션 사이징 | `execution/position_sizer.py` |
| r_real 계산 | `utils/forward_return.py` |
| 멀티사이클 상태 초기화 | `graph/state.py` → `reset_for_next_cycle()` |
| agent 간 packet 변환 | `transforms/{source}_to_{target}.py` |
| 메모리 저장/조회 | `memory/{type}_memory.py` |
| 신뢰도 gating | `reliability/agent_reliability.py` |
| 프롬프트 수정 | `prompts/{agent}_system.md` (스키마 변경 시 반드시 함께) |

---

## Dual Reward 수식 (참조)

```
CombinedReward = w_sim * r_sim + w_real * r_real
w_sim = sigmoid( Σr_sim / Σ(r_sim + r_real + ε) )  — 이동 윈도우

Utility = CombinedReward
        - λ1(0.3) * RiskScore
        - λ2(0.2) * ConstraintViolation
        - λ3(0.15) * MarketAlignmentPenalty
        - λ4(0.2) * ExecutionFeasibilityPenalty
        - λ5(0.15) * AgentReliabilityPenalty
```

구현 위치: `agents/otto.py::compute_adaptive_weights()`, `utils/utility.py::compute_utility()`
현재 상태: 수식은 구현됨, `compute_adaptive_weights()`가 실제 reward_history로 호출되지 않음 (TASKS.md TASK-003 참조)

---

## 전역 금지사항

### 1. Otto에 raw data 넘기지 말 것
```python
# ❌ 절대 금지
state["raw_market_data"] = ohlcv_data
otto.run(state)  # Otto가 raw_market_data 받음

# ✅ all_to_otto transform을 통해서만
packet = transform_all_to_otto(emily_out, bob_out, dave_out)
otto.run(packet, state)
```
**사고 이력**: Otto가 raw data를 직접 해석하면 summary 에이전트 역할이 무너짐. frozenset으로 하드 차단 중.

### 2. LLM 수치를 검증 없이 신뢰하지 말 것
```python
# ❌ 절대 금지
risk_score = llm_output["risk_score"]  # LLM이 컴포넌트 합과 다른 값 반환 가능

# ✅ 컴포넌트 가중합으로 덮어씀
risk_score = dave.compute_risk_score(components)
```
**사고 이력**: LLM이 risk_components와 불일치한 risk_score를 반환해 파이프라인 전체가 잘못된 기준으로 실행.

### 3. `_validate_output()` 없이 Pydantic 직접 호출 금지
```python
# ❌ 금지 — auto-correction 없이 ValidationError 발생
validated = BobOutput(**raw_llm_output)

# ✅ 반드시 _validate_output() 통해서
validated = bob._validate_output(raw_llm_output)
```

### 4. 스키마 변경 시 프롬프트 동시 수정 필수
스키마만 바꾸고 프롬프트 안 바꾸면 LLM이 여전히 옛날 필드명 반환 → auto-correction에 alias 추가해야 하는 악순환.

### 5. Utility 계산은 `utils/utility.py` 단일 소스에서
`policy.py`나 `otto.py`에 직접 계산식 넣지 말 것. 두 곳이 달라지면 어느 게 공식인지 모호해짐.

### 6. 테스트 없이 `_GUIDE.md` 금지사항 추가하지 말 것
규칙을 추가하면 반드시 그 규칙을 검증하는 테스트나 GC 패턴도 함께 추가.

---

## 폴더별 _GUIDE.md 위치

| 폴더 | 가이드 |
|------|--------|
| `agents/` | `agents/_GUIDE.md` |
| `schemas/` | `schemas/_GUIDE.md` |
| `graph/nodes/` | `graph/nodes/_GUIDE.md` |
| `transforms/` | `transforms/_GUIDE.md` |
| `memory/` | `memory/_GUIDE.md` |
| `simulation/` | `simulation/_GUIDE.md` |
| `execution/` | `execution/_GUIDE.md` |
| `utils/` | `utils/_GUIDE.md` |
| `llm/` | `llm/_GUIDE.md` |
| `data/` | `data/_GUIDE.md` |
| `evaluation/` | `evaluation/_GUIDE.md` |
| `scripts/` | `scripts/_GUIDE.md` |
| `dashboard/` | `dashboard/_GUIDE.md` |

---

## 새 클론 온보딩

```bash
# 1. git hook 설치 (커밋 시 harness all 자동 강제)
sh scripts/install_git_hooks.sh

# 2. 완료 검증 단일 명령
sh scripts/verify.sh
```

---

## harness 사용법

```bash
# 특정 폴더 테스트
python scripts/harness.py agents/
python scripts/harness.py schemas/
python scripts/harness.py agents/bob.py   # 파일 단위도 가능

# 테스트 + GC (drift/dead code/금지패턴 체크)
python scripts/harness.py agents/ --gc

# 이전 실행과 비교 (새로 실패한 것만 표시)
python scripts/harness.py agents/ --diff

# 전체 실행
python scripts/harness.py all
```

---

*마지막 갱신: 2026-05-12 — RELIABILITY_UPDATE 노드 추가, E-001~E-004 체인 설명, SystemStateBC 신규 필드, 온보딩 섹션, retry 조건 정정, bc_graph 통합 테스트 반영.*
