# Refactor Log — Paper-Driven Improvements
> 두 논문(TradingAgents, QuantAgents) 피드백 반영 수정 작업 로그
> Director: Claude (검토·디버깅·품질 검증)
> Sub-agents: 각 항목별 코딩 에이전트
> 완료일: 2026-04-02

---

## 적용 범위 결정

### ✅ 적용 대상 (상충 없음, 인프라 존재)
| ID | 항목 | 출처 | 난이도 |
|----|------|------|--------|
| C4 | Memory 시스템 그래프 배선 | QuantAgents | 중 |
| M4 | Reflection 피드백 루프 | QuantAgents | 중 |
| m1 | LLM 백본 이원화 (decision vs analyst) | TradingAgents | 하 |
| M3 | Retriever 쿼리 개선 + 체계적 regime 매칭 | QuantAgents | 중 |
| C2p | Bob 적대적(Bear) 검증 — full debate 아닌 critique | TradingAgents | 하 |

### ❌ 적용 제외
| ID | 이유 |
|----|------|
| C1 | 실제 백테스트 엔진 — 가격 데이터 API 필요 |
| C3 | Tool 사용 — 26개 외부 API 연동 필요 |
| M1 | Emily 4분할 — 스키마 파괴적 변경 |
| M2 | 3-Trader 토론 — 신규 에이전트 신설 필요 |
| RL | Gradient ascent loop — 프레임워크 전면 교체 |

---

## Round 1 — Memory Registry + 그래프 배선 (C4)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `memory/registry.py` 생성: 싱글톤 메모리 인스턴스 중앙 관리
- `graph/nodes/memory_update.py`: 빈 리스트 반환 → Retriever 실제 호출
- Emily/Bob output을 Memory에 저장하는 로직 추가

### 파일
- `memory/registry.py` (신규) — MarketMemory, StrategyMemory, ReportsMemory + Retriever 싱글톤
- `graph/nodes/memory_update.py` (수정) — emily_output/bob_output 저장 + regime query 빌드 + retrieve 실행

### 핵심 변경 내용
```
이전: retrieved_market_cases = []  # 항상 빈 리스트
이후:
  - emily_output → market_memory.store()
  - bob_output → strategy_memory.store()
  - market_retriever.retrieve(query, as_of=current_date) 실제 호출
  - retrieved_market_cases = 실제 유사 케이스 리스트
```

### 검증
- retrieved_market_cases가 None이 아닌 list로 반환됨 ✅
- emily_output=None이면 빈 리스트 반환 (기존 동작 유지) ✅
- point-in-time 준수 (as_of=current_date) ✅

---

## Round 2 — Reflection 피드백 루프 (M4)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- `graph/nodes/logging_node.py`: 실행 결과를 StrategyMemory에 outcome으로 저장
- 다음 사이클 retrieve 시 유사 과거 outcome 참조 가능하도록

### 파일
- `graph/nodes/logging_node.py` (수정) — strategy_memory.store() 추가

### 핵심 변경 내용
```python
# 실행 후 outcome을 strategy_memory에 저장
outcome_entry = {
    "approval_status": ..., "selected_policy": ...,
    "risk_score": ..., "horizon_closed": True,
    "rationale": "Policy X executed with risk_score=0.xx"
}
tags = ["outcome", "horizon_closed", approval_status]
strategy_memory.store(key=f"outcome_{date}", value=outcome_entry, date=date, tags=tags)
```

### 검증
- horizon_closed=True로 저장 → OutcomeReliability=1.0 → 다음 retrieve에서 최고 신뢰도 케이스로 활용 ✅
- current_date 빈 문자열이면 저장 skip ✅
- 기존 Ledger 기록 로직 유지 ✅

---

## Round 3 — LLM 백본 이원화 (m1)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- config에 model_roles 추가 (decision: heavy, analyst: light)
- factory.py에 node_role 파라미터 추가
- 하위 호환 유지

### 파일
- `config/system_config.yaml` (수정) — model_roles 블록 추가
- `llm/factory.py` (수정) — node_role 파라미터 추가, model_roles fallback 로직

### 핵심 변경 내용
```yaml
# config/system_config.yaml
llm:
  model: claude-opus-4-5          # 기존 fallback 유지
  model_roles:
    decision: claude-opus-4-5     # 의사결정 노드
    analyst: claude-haiku-4-5-20251001  # 분석/요약 노드
```

```python
# factory.py
def create_provider(config_path=..., node_role="decision") -> BaseLLMProvider:
    # model_roles[node_role] → 없으면 model 필드 fallback
```

### 검증
- 기존 create_provider(config_path) 단일 인자 호출 하위 호환 ✅
- TestLLMFactory 전체 통과 ✅

---

## Round 4 — Retriever 쿼리 개선 (M3)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- validity_scorer의 regime 매핑 확장 (3개 pair → 10개 pair)
- compute_sim을 regime/bias 가중치 기반으로 개선

### 파일
- `memory/retrieval/validity_scorer.py` (수정) — similar_pairs 확장, compute_sim 가중치 로직

### 핵심 변경 내용
```python
# regime 유사도 매핑 확장
similar_pairs = {
    frozenset(["risk_on", "fragile_rebound"]): 0.6,
    frozenset(["risk_on", "mixed"]): 0.5,
    frozenset(["risk_off", "transition"]): 0.6,
    frozenset(["risk_off", "mixed"]): 0.5,
    frozenset(["mixed", "transition"]): 0.7,
    frozenset(["mixed", "fragile_rebound"]): 0.55,
    frozenset(["transition", "fragile_rebound"]): 0.65,
    frozenset(["selective_long", "risk_on"]): 0.7,
    frozenset(["selective_long", "mixed"]): 0.6,
}

# compute_sim: regime 정확 매치 +0.3, bias 정확 매치 +0.2, token overlap * 0.5
score = min(overlap * 0.5 + regime_bonus + bias_bonus, 1.0)
```

### 검증
- 동일 regime 케이스가 더 높은 점수로 상위 retrieve ✅
- floor=0.3 이하 케이스 자동 폐기 ✅

---

## Round 5 — Bob Bear Critique (C2 partial)
**Status: ✅ DONE** | 테스트: 323/323 통과

### 목표
- BobAgent._should_retry()에 Bear Critique 검증 2개 추가
- 단방향 낙관론 방지 (TradingAgents Bull/Bear 토론의 경량 대안)

### 파일
- `agents/bob.py` (수정) — _should_retry() Bear Critique 추가

### 핵심 변경 내용
```python
# Bear Critique 1: failure_conditions 부족 → 낙관론 감지
total_failure_conditions = sum(len(c.get("failure_conditions", [])) for c in candidates)
if total_failure_conditions < len(candidates):
    return True, "Bear critique: each strategy must have >= 1 failure_condition"

# Bear Critique 2: 모든 candidate regime_fit >= 0.85 → 과도한 낙관 감지
if len(candidates) >= 2:
    if all(c.get("regime_fit", 0.0) >= 0.85 for c in candidates):
        return True, "Bear critique: all candidates regime_fit >= 0.85, need conservative posture"
```

### 검증
- 기존 bob 테스트 8개 전부 통과 (VALID_BOB_OUTPUT failure_conditions 2개 보유) ✅
- candidate 1개일 때 Critique 2 적용 안 됨 (조건: >= 2) ✅

---

## 최종 진행 상황 요약

| Round | 항목 | Status | 테스트 | 담당 에이전트 |
|-------|------|--------|--------|--------------|
| 1 | C4 Memory 배선 | ✅ DONE | 323/323 | Sub-agent #1 |
| 2 | M4 Reflection 루프 | ✅ DONE | 323/323 | Sub-agent #2 |
| 3 | m1 LLM 이원화 | ✅ DONE | 323/323 | Sub-agent #3 |
| 4 | M3 Retriever 쿼리 | ✅ DONE | 323/323 | Sub-agent #4 |
| 5 | C2p Bear Critique | ✅ DONE | 323/323 | Sub-agent #5 |
| **통합** | **전체 최종** | ✅ **PASS** | **323/323** | **Director** |

---

## 최종 변경 파일 목록

| 파일 | 변경 유형 | Round | 논문 근거 |
|------|----------|-------|----------|
| `memory/registry.py` | 신규 | 1 | QuantAgents 3-type Memory |
| `graph/nodes/memory_update.py` | 수정 | 1 | QuantAgents Memory retrieval |
| `graph/nodes/logging_node.py` | 수정 | 2 | QuantAgents Reflection update |
| `llm/factory.py` | 수정 | 3 | TradingAgents LLM 이원화 |
| `config/system_config.yaml` | 수정 | 3 | TradingAgents LLM 이원화 |
| `memory/retrieval/validity_scorer.py` | 수정 | 4 | QuantAgents Memory retrieval 품질 |
| `agents/bob.py` | 수정 | 5 | TradingAgents Bear perspective |

---

## 미적용 항목 (향후 과제)

| ID | 항목 | 필요 작업 |
|----|------|----------|
| C1 | 실제 Simulated Trading | 백테스트 엔진(backtrader/zipline) + 가격 데이터 API |
| C3 | Tool 사용 (26개) | LangChain tools / 외부 API 연동 레이어 |
| M1 | Emily 4분할 | 스키마 분리 + 4개 에이전트 신설 |
| M2 | 3-Trader 토론 | RiskyTrader/NeutralTrader/SafeTrader 에이전트 신설 |
| RL | 학습 루프 | PPO/SAC 기반 policy 업데이트 |
