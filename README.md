# Hybrid Multi-Agent Investment System v3.6

TradingAgents × QuantAgents × Expert Investment Teams
with Temporal Cadence, Dual Reward Policy, Retrieval-Grounded Meetings,
Technical Signal Priority, Agent Reliability Gating, Uncertainty Propagation, and Structured Debate-Controlled Execution.

---

## Architecture

### 두 파이프라인이 공존

| 파이프라인 | 진입점 | 역할 |
|-----------|--------|------|
| **Pipeline A** (SPY) | `python orchestrator.py` | Emily→Bob→Dave→Otto LangGraph, 단일 SPY 포트폴리오 |
| **Pipeline B/C** (운영 루프) | `python scripts/run_loop.py` | 개별 종목 × 날짜 범위, LangGraph 상태 기계 |

---

### Pipeline B/C — 핵심 노드 흐름

```
BC_EMILY → BC_STOCK_ANALYSIS → BC_BACKTESTER → BC_MEETINGS → BC_CALIBRATION
→ BC_RELIABILITY_UPDATE → BC_PORTFOLIO_MANAGER → BC_DAVE
→ [Dave risk > 0.7] → BC_BACKTESTER_DEFENSIVE → BC_PORTFOLIO_MANAGER → BC_DAVE
→ BC_OTTO
→ [Otto rejected, retry ≤ 2] → BC_PORTFOLIO_MANAGER
→ END
```

### 4 Agents

| Agent | Role | Key Constraint |
|-------|------|----------------|
| **Emily** | Market regime 분석 | `regime_confidence < 0.55` → uncertainty_mode 전파 |
| **Dave** | 포트폴리오 리스크 평가 | `risk_score > 0.7` → defensive 재실행 트리거 |
| **Otto** | 최종 승인 게이트 | reliability floor < 0.35 → conditional_approval 강제 |
| **Portfolio Manager** | 배분 결정 | execution_feasibility < 0.4 → staggered 강제 |

### 3 Meeting Types

| Meeting | Cadence | Key Output |
|---------|---------|------------|
| **Market Analysis** | 매주 금요일 | WeeklyMarketReport + DebateResolution |
| **Strategy Development** | Market Analysis 이후 | WeeklyStrategySet + ExecutionFeasibilityPacket |
| **Risk Alert** | 이벤트 기반 (risk_score > 0.75) | RiskAdjustedUtility + emergency controls |

---

## Setup

```bash
# 1. API keys
cp .env.example .env
# ANTHROPIC_API_KEY, OPENAI_API_KEY, POLYGON_API_KEY 입력

# 2. 의존성 설치
pip install -r requirements.txt

# 3. git hook 설치 (커밋 시 harness all 자동 강제)
sh scripts/install_git_hooks.sh
```

---

## Usage

### Pipeline B/C — 날짜 범위 운영 루프 (주력)

```bash
# 주간 실행 (매주 금요일)
python scripts/run_loop.py AAPL NVDA TSLA --start 2024-01-01 --end 2024-03-31

# 일간 실행
python scripts/run_loop.py AAPL --start 2024-01-01 --end 2024-03-31 --freq daily

# 이어서 실행 (이미 저장된 날짜 스킵)
python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-03-31 --resume
```

### Pipeline A — SPY 포트폴리오 (레거시 호환)

```bash
python orchestrator.py
```

### 평가

```bash
# 시스템 vs 베이스라인 (CR / ARR / SR / MDD)
python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31
# → results/eval_YYYY-MM-DD.json 저장
```

---

## Testing & Verification

```bash
# 전체 검증 (pytest + Doc Lint) — 완료 기준
sh scripts/verify.sh

# 또는
python scripts/harness.py all

# 특정 폴더만
python scripts/harness.py graph/
python scripts/harness.py evaluation/
```

현재 테스트: **1016 passed**

---

## Key Design Decisions

- **Uncertainty Propagation**: Emily confidence → lookback 확장 → Dave stress multiplier → Otto equity shrinkage
- **Agent Reliability Gating**: EMA 기반 신뢰도, floor 0.35 이하 → Otto conditional_approval 강제
- **Execution Feasibility**: Sharpe/Cash/Risk 복합 점수, < 0.4 → staggered execution 강제
- **Retrieval Validity**: Sim × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability (5-factor)
- **Otto raw data 차단**: `_FORBIDDEN_RAW_FIELDS` frozenset, run() 진입 시 즉시 차단
- **Point-in-time safe**: 백테스터/평가 모두 as_of 이후 데이터 접근 차단

---

## Project Structure

```
graph/          — LangGraph 상태 기계 (bc_graph.py, bc_state.py, nodes/)
agents/         — Emily, Bob, Dave, Otto (Pipeline A)
memory/         — 메모리 레이어 (registry, retrieval, run_memory, outcome_filler)
simulation/     — 전략 백테스터 (6개 전략 pool)
calibration/    — 신뢰도 감사 + AgentReliabilityManager
evaluation/     — 성과 지표, PointInTimeBacktester, baselines
scripts/        — run_loop.py, run_eval.py, harness.py, verify.sh
results/        — 주기별 portfolio.json, reliability_state.json
docs/sprints/   — 완료 스프린트 아카이브
```

### 문서 계층

| 파일 | 역할 |
|------|------|
| `CLAUDE.md` | 핵심 원칙 + 완료 스프린트 목록 |
| `DEV_GUIDE.md` | 전체 아키텍처, 데이터 흐름, 금지사항 색인 |
| `WORKFLOW.md` | 태스크 lifecycle, 이슈 심각도 기준 |
| `TASKS.md` | 현재 스프린트 태스크 (최대 3개) |
| `BACKLOG.md` | 대기 태스크 + 이슈 테이블 |
| `DESIGN_SPEC_v3.6.md` | 시스템 설계 원본 (논문급 스펙) |
