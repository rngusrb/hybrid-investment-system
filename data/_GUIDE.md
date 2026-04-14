# data/ — 데이터 레이어 가이드

## 역할
외부 데이터 수집 + 전처리. Point-in-time constraint 강제.
Polygon.io REST API 기반. API 없으면 빈 데이터 + 품질 플래그 반환.

---

## 핵심 패턴

### as_of 파라미터 — 항상 필수
```python
fetcher.get_ohlcv(
    ticker="SPY",
    from_date="2023-01-01",
    to_date="2024-01-20",
    as_of="2024-01-20",   # ← 이 날짜 이후 데이터 자동 차단
)
```
as_of 없이 호출하면 미래 데이터 lookahead 발생.

### 실패는 빈 데이터 + 품질 플래그로 처리
```python
# API 실패해도 예외 발생 안 함
result = fetcher.get_ohlcv(...)
# result = {"data": [], "quality": DataQualityReport(...)}
# quality.missing_flags에 API_FAILURE 기록됨
```

### MissingReason별 confidence shrinkage
| 사유 | shrinkage |
|------|-----------|
| FUTURE_DATE_BLOCKED | 0.50 |
| API_FAILURE | 0.15 |
| STALE_DATA | 0.10 |
| INSUFFICIENT_HISTORY | 0.08 |
| NAN_VALUE | 0.05 |
| NO_NEWS | 0.02 |

---

## 금지사항

### ❌ as_of 없이 get_ohlcv() 호출
미래 데이터가 포함되면 backtesting lookahead bias 발생.
**사고 이력**: as_of 없이 호출 시 미래 close 가격이 전략 계산에 포함됨.

### ❌ 뉴스 article dict에서 publisher 필드 누락
```python
# ❌ 금지 — 출처가 항상 빈 문자열로 표시됨
{"title": ..., "article_url": ...}  # publisher 없음

# ✅ publisher 포함 필수
{"title": ..., "article_url": ...,
 "publisher": {"name": getattr(getattr(item, "publisher", None), "name", "")}}
```
**사고 이력**: polygon_fetcher.py가 publisher 필드 누락 → 대시보드 뉴스 출처 항상 공백.

### ❌ API 실패 시 예외 발생
빈 데이터 + 품질 플래그 반환이 원칙. 상위 레이어가 품질 보고 판단하게.

### ❌ NaN 값 그대로 하위 레이어 전달
DataManager.preprocess_ohlcv()에서 forward-fill + 이상치 탐지 후 전달.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `polygon_fetcher.py` | OHLCV + News. point-in-time 강제, staleness 체크 |
| `data_manager.py` | preprocess, compute_returns, compute_realized_vol, get_sector |
| `missing_protocol.py` | MissingReason(6종), MissingFlag, DataQualityReport |

---

## 하네스

```
tests:
  - tests/unit/test_data.py
```

```bash
python scripts/harness.py data/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | polygon_fetcher.py | Polygon API key 연결, 실제 데이터 검증 완료 |
| 2026-04-07 | polygon_fetcher.py | 뉴스 article dict에 publisher 필드 추가 (대시보드 출처 표시 버그 수정) |
