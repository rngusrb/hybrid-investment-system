# memory/ — 메모리 레이어 가이드

## 역할
에이전트 간 정보 영속성 관리.

### Pipeline A 전용 (in-memory, 재시작 시 초기화)
```
memory/registry.py → market_memory, strategy_memory, reports_memory (싱글톤)
memory/decision_journal.py → DecisionJournal (registry에 미등록, 직접 인스턴스)
memory/retrieval/ → Retriever + validity_scorer (5차원 scoring)
```
재시작 시 초기화됨 — 의도된 설계 (Pipeline A는 주간 단위 실행).

### Pipeline B/C 전용 (파일 영속, 재시작 후에도 유지)
```
memory/run_memory.py      → results/ 아래 이전 사이클 결과 로드 → memory_context 생성
memory/outcome_filler.py  → T+7 후 Polygon 데이터로 r_real 채우기
results/strategy_memory.json   → ticker별 전략 + Sharpe + r_real
results/reliability_state.json → 7개 agent의 EMA reliability score
results/YYYY-MM-DD/portfolio.json → 당일 배분 결정 (r_real 나중에 채워짐)
```

---

## 핵심 패턴

### 날짜 기반 key 충돌 방지
```python
# 같은 날 다른 타입 저장 시 key 구분 필수
strategy_memory.store(key=f"outcome_{date}", ...)
market_memory.store(key=f"regime_{date}", ...)
# key 안에 타입 prefix 포함 — 같은 날짜여도 충돌 없음
```
**사고 이력**: `{date}` 만으로 key 쓰다가 같은 날 다른 데이터가 덮어쓰기됨.

### registry를 통한 싱글톤 접근
```python
from memory.registry import strategy_memory, market_memory
# 직접 인스턴스 생성 금지 — registry에서 가져올 것
```

### Retrieval validity score
```
Score = Similarity × RecencyDecay × RegimeMatch × DataQuality × OutcomeReliability
```
- floor 0.3 미만 자동 폐기
- top_k 최대 10

---

## 금지사항

### ❌ 메모리 직접 인스턴스 생성
```python
# 금지
mem = StrategyMemory()   # 별도 인스턴스 → registry와 분리됨

# 반드시
from memory.registry import strategy_memory
```

### ❌ SharedLedger에 raw chain-of-thought 저장
```python
# 금지
ledger.record("llm_reasoning", {"chain_of_thought": "..."}, ...)
# FORBIDDEN frozenset에서 ValueError 발생
```

### ❌ get_by_date() 반환값 가정 변경
`get_by_date()`는 단일 dict 반환. list 아님.
```python
result = memory.get_by_date("2024-01-15")
# result = {"key": ..., "value": ..., "date": ..., "tags": [...]}
```

---

## 하네스

```
tests/unit/test_retrieval.py
tests/unit/test_run_memory.py
tests/unit/test_outcome_filler.py
tests/integration/test_e2e_fixes.py
tests/integration/test_multicycle.py
```

```bash
python scripts/harness.py memory/
```

---
