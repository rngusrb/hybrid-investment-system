# Hybrid Multi-Agent Investment System v3.6

TradingAgents × QuantAgents × Expert Investment Teams
with Temporal Cadence, Dual Reward Policy, Retrieval-Grounded Meetings,
Technical Signal Priority, Agent Gating, and Structured Debate-Controlled Execution.

---

## Architecture

### 4 Agents

| Agent | Role | Input | Key Constraint |
|-------|------|-------|----------------|
| **Emily** | Market Analyst | Raw market data, news, macro | Technical signal as independent top-level field |
| **Bob** | Strategy Analyst | Emily packet | sim_window required; technical_confidence ≥ 0.6 → must include technical-aligned candidate |
| **Dave** | Risk Analyst | Bob packet | R_score > 0.75 → trigger_risk_alert_meeting = True (hard) |
| **Otto** | Fund Manager | Official packets only | Raw data access blocked (frozenset hard-coded) |

### 3 Meeting Types

| Meeting | Cadence | Key Output |
|---------|---------|------------|
| **Weekly Market Analysis** | Every Friday | WeeklyMarketReport + DebateResolution + SignalConflictResolution |
| **Weekly Strategy Development** | After market analysis | WeeklyStrategySet + ExecutionFeasibilityPacket (separate from strategy) |
| **Risk Alert** | Event-driven (R_score > 0.75) | RiskAdjustedUtility calculation + emergency controls + risk_override_record |

---

## Design Principles (Non-Negotiable)

1. **Fine-grained task contract** —업무 계약이 agent 수보다 중요
2. **Technical signal priority** — `technical_signal_state`는 EmilyOutput의 독립 최상위 필드
3. **Agent conditional gating** — cold start 0.5, floor 0.35 이하 → hard gating
4. **Propagation audit** — signal 손실/모순을 실제 비교 로직으로 감지
5. **Calibration layer** — raw score 상위 전달 전 rolling_std/shrinkage/clipping 통과
6. **LangGraph flexibility** — state 기반 conditional edge, skip/retry 실제 작동

---

## Key Implementation Decisions

- **Otto raw data 차단**: `_FORBIDDEN_RAW_FIELDS` frozenset으로 run() 진입 시 즉시 차단
- **Selected strategy ≠ execution order**: `BobToExecutionPacket` 별도 생성 강제
- **Debate는 구조체로 저장**: `DebateResolution` Pydantic 모델, 장식용 텍스트 금지
- **Propagation audit**: token overlap + contradiction detection + semantic similarity
- **Retrieval validity**: Sim × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability (5개 factor 곱)
- **SharedLedger**: ALLOWED/FORBIDDEN type frozenset, raw chain-of-thought 저장 불가

---

## Setup

```bash
# 1. API keys 설정
cp .env.example .env
# ANTHROPIC_API_KEY, OPENAI_API_KEY, POLYGON_API_KEY 입력

# 2. 의존성 설치
pip install -r requirements.txt

# 3. (선택) provider 변경
# config/system_config.yaml의 llm.provider: "anthropic" | "openai" | "ollama"

# 4. 실행
python orchestrator.py
```

---

## Usage

```python
from orchestrator import Orchestrator

orch = Orchestrator()

# Daily cycle
result = orch.run_daily_cycle("2024-01-15")

# Weekly cycle (Friday)
result = orch.run_weekly_cycle("2024-01-19")

# Risk alert (event-driven)
result = orch.run_risk_alert_cycle("2024-01-15", trigger_reason="risk_score=0.82")

# Ledger 확인
print(orch.get_ledger_summary())
```

---

## Testing

```bash
# 전체 테스트 (323개)
pytest tests/ -v

# 단위 테스트만
pytest tests/unit/ -v

# 통합 테스트만
pytest tests/integration/ -v
```

---

## Evaluation

```python
from evaluation.metrics import compute_all_metrics
from evaluation.backtester import PointInTimeBacktester
from evaluation.baselines import list_baselines      # 9개
from evaluation.ablation import list_ablations, run_ablation_suite  # 12개

# Ablation suite
results = run_ablation_suite()  # 12개 변형 config 반환
```

---

## Project Structure

See `CLAUDE_CODE_BRIEFING.md` for full directory layout.
See `DESIGN_SPEC_v3.6.md` for complete system design specification.
See `PROGRESS_LOG.md` for implementation history and design decisions.
