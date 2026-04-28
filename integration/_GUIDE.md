# integration/ — Pipeline A ↔ Pipeline B/C 연결 어댑터

## 역할

Pipeline A 에이전트(Emily/Dave/Otto)를 Pipeline B/C run_loop에서 직접 호출하기 위한 어댑터 모듈.
orchestrator.py의 LangGraph 노드를 건드리지 않고 B/C 컨텍스트용 입출력 변환만 담당.

---

## 핵심 패턴

### Emily — SPY 레짐 컨텍스트
```python
from integration.emily_context import run_emily_for_context, format_emily_for_prompt

emily_output, emily_context = run_emily_for_context(llm, spy_data, date)
# emily_context → run_portfolio_manager(..., emily_context=emily_context)
```

### Dave — 포트폴리오 레벨 리스크
```python
from integration.dave_context import run_dave_for_portfolio

dave_output, _ = run_dave_for_portfolio(llm_decision, portfolio, stock_results, date)
# Portfolio Manager 완료 후에만 호출 (입력이 portfolio 출력을 필요로 함)
```

### Otto — 최종 승인 게이트
```python
from integration.otto_gate import run_otto_approval, apply_otto_decision

otto_output = run_otto_approval(llm_decision, date, emily_output, sim_results, dave_output, portfolio)
portfolio = apply_otto_decision(otto_output, portfolio)
```

---

## 금지사항

### ❌ Emily에 개별 종목 bars 넘기지 말 것
Emily는 SPY만 분석. 종목별 bars는 Pipeline B 4 Analyst가 담당.

### ❌ Otto에 raw data 포함 금지 (전역 금지사항 1번)
build_otto_input()이 raw field를 포함하면 OttoAgent._block_raw_data_access()에서 즉시 차단.
금지 필드: bars, articles, raw_market_data, ohlcv, news_articles, raw_news

### ❌ Dave 실행을 Portfolio Manager 이전에 하지 말 것
Dave 입력은 portfolio.allocations를 필요로 함. Portfolio Manager 완료 전에 호출하면 빈 dict 반환.

### ❌ graceful skip 제거 금지
emily_output={}, portfolio={} 등 빈 입력 시 ({}, "") 반환. 호출자가 try/except로 감싸도 되지만
이 모듈 자체는 예외 대신 빈 결과를 반환해야 run_loop의 graceful degradation이 유지됨.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `emily_context.py` | EmilyAgent 실행 + format_emily_for_prompt() |
| `dave_context.py` | build_dave_input() + DaveAgent 실행 + format_dave_for_prompt() |
| `otto_gate.py` | build_otto_input() + OttoAgent 실행 + apply_otto_decision() |

---

## 하네스

```
tests/unit/test_integration_emily.py
tests/unit/test_integration_dave.py
tests/unit/test_integration_otto.py
```

```bash
python scripts/harness.py integration/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-17 | emily_context.py | 신규: EmilyAgent B/C 어댑터 (TASK-001) |
| 2026-04-17 | dave_context.py | 신규: DaveAgent 포트폴리오 리스크 어댑터 (TASK-002) |
| 2026-04-17 | otto_gate.py | 신규: OttoAgent 승인 게이트 + compute_adaptive_weights 연결 (TASK-003) |
