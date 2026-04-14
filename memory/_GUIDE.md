# memory/ — 메모리 레이어 가이드

## 역할
에이전트 간 정보 영속성 관리. 4개 메모리 + retriever + ledger로 구성.
현재 in-memory dict 기반 (재시작 시 초기화 — 의도된 미완성).

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

## 파일 구조

| 파일 | 역할 |
|------|------|
| `base_memory.py` | ABC, point-in-time 강제 |
| `strategy_memory.py` | 전략 결과, outcome, r_sim/r_real 저장 |
| `market_memory.py` | regime, OHLCV, 기술적 지표 |
| `reports_memory.py` | 주간 리포트, 토론 결과 |
| `decision_journal.py` | 정책 결정, 실제 결과 |
| `registry.py` | 싱글톤 인스턴스 중앙 관리 |
| `retrieval/validity_scorer.py` | 5개 factor 곱 validity score |
| `retrieval/retriever.py` | top_k 검색, timestamp guard |

---

## 하네스

```
tests/unit/test_retrieval.py
tests/unit/test_run_memory.py
tests/integration/test_e2e_fixes.py
tests/integration/test_multicycle.py
```

```bash
python scripts/harness.py memory/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | strategy_memory.py | _store[key] 날짜 충돌 수정 |
| 2026-04-06 | market_memory.py | 동일 수정 |
| 2026-04-14 | run_memory.py | 신규: results/ 기반 루프 메모리 (Phase 2). find_prev_dates / build_context / format_context_for_prompt / get_context_prompt. 24개 테스트 추가 |
