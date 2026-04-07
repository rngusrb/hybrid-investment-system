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
              _GUIDE.md ## 최근변경 섹션 업데이트
              → 6번 완료 전까지 "완료" 선언 금지
7. GC 체크  → python scripts/harness.py <폴더>/ --gc
```

**루프 기본값: 전부 통과할 때까지 반복. 중간에 묻지 않음.**
**특히 6번 _GUIDE.md 갱신이 핵심 — 같은 실수가 반복되는 유일한 이유는 규칙이 안 쌓였기 때문.**

---

## 데이터 흐름 지도

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

## 현재 의도적 미완성 영역 (건드리지 말 것)

| 영역 | 현재 상태 | 이유 |
|------|----------|------|
| `r_real` T+1 업데이트 | Polygon 조회 시도, 미래면 r_sim proxy | 실시간 모드에서 T+1 미확정 |
| Memory 영속성 | in-memory dict | DB 연결 미구현, 재시작 시 초기화됨 |
| FAISS dense retrieval | token overlap 기반 | sentence-transformer 미연결 |
| 브로커 연결 | position_sizer까지만, 실제 주문 미전송 | API 계정 필요 |
| Emily 4분할 | 단일 Emily | 스키마 파괴적 변경 필요 |
| 실제 스케줄러 | is_week_end() 구현됨 | 연결 미완 |
| ticker 동적화 | SPY 고정 | 멀티 ticker 미구현 |

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

*마지막 갱신: 2026-04-07*
