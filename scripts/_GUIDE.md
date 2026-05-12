# scripts/ — 파이프라인 실행 스크립트 가이드

## 역할
- `stock_pipeline.py`: 단일 종목 TradingAgents 파이프라인 (CLI)
- `portfolio_pipeline.py`: 멀티 종목 → Portfolio Manager 파이프라인 (CLI)
- `run_loop.py`: 날짜 범위 반복 실행 루프 — bc_graph.compile() → invoke() 경로 (B/C 파이프라인)
- `harness.py`: 폴더별 테스트/GC 실행 도구

## 파일별 책임

| 파일 | 책임 |
|------|------|
| `stock_pipeline.py` | fetch_data + 6 agents 순차 호출 + 출력 |
| `portfolio_pipeline.py` | 여러 ticker에 stock_pipeline 적용 후 Portfolio Manager 호출 |
| `run_loop.py` | 날짜 범위 생성 → 각 날짜에 compile_bc_graph() → bc.invoke() 실행 → results/ 저장 |
| `harness.py` | pytest 래퍼 + GC + staleness check |

## 금지사항

### 0. 재무제표 fetch — 이중 필터 필수 (API + Python)

```python
# ❌ 금지 — filing_date_lte 단독 사용
# 이유: Polygon 분기 데이터 일부가 filing_date=None → API 필터 우회, 2025년 데이터까지 반환됨

# ✅ 올바른 패턴 — 이중 필터
def _financials_available(item, cutoff: str) -> bool:
    filing = str(getattr(item, "filing_date", None) or "")
    end    = str(getattr(item, "end_date",    None) or "")
    if filing and filing > cutoff: return False  # 공시일이 기준일 이후
    if end    and end    > cutoff: return False  # 분기말이 기준일 이후
    return True

raw = list(client.vx.list_stock_financials(
    ticker=ticker, timeframe="quarterly",
    period_of_report_date_lte=date,   # 1차: API 레벨 컷
))
items = [i for i in raw if _financials_available(i, date)]  # 2차: Python 레벨 컷
```

**사고 이력**:
- `filing_date_lte=date`만 사용 시 `filing_date=None`인 분기 항목이 필터 우회 → 2025년 미래 데이터 반환
- `period_of_report_date_lte`만 사용 시 filing_date가 기준일 이후인 항목(공시 전 데이터) 포함
- 이중 필터로 두 케이스 모두 차단. 분기말 기준과 실제 공시일 기준을 동시 적용.

### 1. stock_pipeline에서 포트폴리오 전체 배분 결정 금지
```python
# ❌ 금지 — 개별 종목이 cash_pct 결정하면 종목 합산 시 100% 초과
trader_output["cash_pct"] = 0.3  # 종목마다 따로 잡으면 안 됨

# ✅ 포트폴리오 배분은 portfolio_pipeline.py의 PortfolioManager만
```
**이유**: 개별 종목은 signal만 생성. 현금/헤지 배분은 포트폴리오 레벨에서 한번만 결정.

### 2. call_llm() 재시도 3회 초과 금지
```python
# ❌ 금지 — LLM 무한 루프
for attempt in range(100): ...

# ❌ 금지 — 로그 없이 조용히 빈 dict 반환 (Silent Failure)
except Exception:
    continue
return {}

# ✅ max 3회, 각 실패 로깅 후 빈 dict 반환
except Exception as e:
    logger.warning(f"[call_llm] attempt={attempt+1} 실패: {e}")
    continue
logger.warning("[call_llm] 3회 모두 실패 — 빈 dict 반환")
return {}
```
**사고 이력**: CLAUDE.md Silent Failure 금지 원칙과 충돌 — except Exception: pass 패턴은 반드시 로깅 필수.

### 3. stock_pipeline 함수를 portfolio_pipeline에서 import해서 재사용할 것
```python
# ❌ 금지 — 코드 복붙
def portfolio_fetch_data(): ...  # stock_pipeline.fetch_data 복붙

# ✅ import해서 재사용
from scripts.stock_pipeline import fetch_data, run_fundamental, ...
```

## 하네스

```
tests/unit/test_stock_pipeline.py
tests/unit/test_run_loop.py
tests/unit/test_portfolio_pipeline.py
```

```bash
# 단위 테스트 (스키마 검증, API 호출 없음)
python scripts/harness.py scripts/

# 실제 실행 검증 (LLM + Polygon API 실제 호출)
python scripts/live_e2e_bc_test.py
python scripts/live_e2e_bc_test.py --tickers AAPL NVDA TSLA --date 2024-01-15

# 루프 dry-run (날짜 목록 확인, API 호출 없음)
python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-03-31 --dry-run

# 루프 실제 실행
python scripts/run_loop.py AAPL NVDA TSLA --start 2024-01-01 --end 2024-03-31
python scripts/run_loop.py AAPL --start 2024-01-01 --end 2024-06-30 --freq daily --resume
```
