# dashboard/ — Streamlit 대시보드 가이드

## 역할
파이프라인 A/B/C 실행 결과를 시각화하는 Streamlit 웹 UI.
분석 실행, 뉴스 데이터 확인, 에이전트 보고서 조회, 포트폴리오 결과 시각화를 제공한다.

## 파일 구조

```
dashboard/
  app.py                       ← 메인 페이지 (종목 입력 + 실행)
  pages/
    0_🔄_파이프라인_추적.py      ← 전체 흐름 + 회의록 (Step 0~7 타임라인)
    1_📰_뉴스_데이터.py          ← 뉴스 테이블 + OHLCV 차트
    2_🤖_에이전트_보고서.py       ← 에이전트별 full 출력 + 플로우 다이어그램
    3_📊_포트폴리오_결과.py       ← 파이차트 + 배분표 + 종목 비교
  utils/
    formatters.py               ← 순수 변환 함수 (st.* 없음, 테스트 가능)
  _GUIDE.md                    ← 이 파일
```

## 실행 방법
```bash
streamlit run dashboard/app.py
```

## 상태 공유 (session_state 구조)
모든 페이지가 `st.session_state`를 통해 결과를 공유한다.

```python
st.session_state = {
    "tickers": ["AAPL", "NVDA", "TSLA"],
    "date": "2024-01-15",
    "results": {
        "AAPL": {
            "ticker": "AAPL",
            "current_price": 185.92,
            "bars": [...],        # OHLCV 리스트
            "articles": [...],    # 뉴스 리스트
            "financials": [...],
            "fundamental": {...},
            "sentiment": {...},
            "news": {...},
            "technical": {...},
            "researcher": {...},
            "trader": {...},
            "risk_manager": {...},
        },
        ...
    },
    "portfolio": {
        "allocations": [...],
        "total_equity_pct": 0.33,
        "cash_pct": 0.60,
        ...
    }
}
```

## 금지사항 (사고 이력 포함)

### 1. 페이지에서 직접 LLM/API 호출 금지
```python
# ❌ 금지 — 페이지 전환마다 API 재호출 발생
def page_news():
    data = fetch_data(ticker, date)  # 여기서 호출하면 안 됨

# ✅ session_state에서 읽기만
def page_news():
    result = st.session_state["results"][ticker]
    articles = result["articles"]
```
**이유**: pages는 매번 re-run됨. API 호출은 app.py 실행 시 1회만.

### 2. session_state 미확인 후 페이지 접근 금지
```python
# ❌ 금지 — KeyError 발생
articles = st.session_state["results"]["AAPL"]["articles"]

# ✅ 항상 존재 여부 먼저 확인
if not st.session_state.get("results"):
    st.warning("먼저 메인 페이지에서 분석을 실행하세요.")
    st.stop()
```

### 3. Streamlit 컴포넌트를 pages/ 밖에서 import 금지
```python
# ❌ 금지 — scripts/, schemas/ 등에 st.* 코드 넣지 말 것
# ✅ 모든 st.* 호출은 dashboard/ 내부에서만
```

### 4. f-string 안에 백슬래시 사용 금지 (Python 3.11 미만)
```python
# ❌ 금지 — SyntaxError
f"{'<br>' if changed else ''}"  # 중첩 따옴표+백슬래시 조합

# ✅ 변수로 분리
changed_html = "<br><span>변경됨</span>" if changed else ""
f"{changed_html}"
```
**사고 이력**: 3_포트폴리오_결과.py 188번 줄 SyntaxError — f-string 내부 백슬래시로 전체 페이지 렌더링 실패.

### 5. plotly add_vline에 날짜 문자열 직접 전달 금지
```python
# ❌ 금지 — TypeError: unsupported operand type(s) for +: 'int' and 'str'
fig.add_vline(x="2024-01-15", ...)

# ✅ timestamp()*1000 으로 변환
import pandas as pd
fig.add_vline(x=pd.Timestamp("2024-01-15").timestamp() * 1000, ...)
```
**사고 이력**: plotly add_vline이 내부에서 x값 산술 연산 시도 → 문자열이면 TypeError.

### 6. app.py에서 이미 지운 파일(app.py 이전 버전) 참조 금지
현재 유효한 app.py는 `dashboard/app.py` 하나. 루트에 생성된 임시 app.py가 있으면 삭제.

## 하네스

```
tests:
  - tests/unit/test_dashboard_utils.py
```

```bash
python scripts/harness.py dashboard/
```

## 테스트 전략
Streamlit UI는 직접 단위 테스트가 어려움. 대신:
- **유틸 함수**는 `dashboard/utils/` 분리 후 pytest 테스트
- **session_state 구조**는 `tests/unit/test_dashboard_utils.py`에서 검증
- UI 렌더링 자체는 수동 확인 (streamlit run)


## 최근 변경

| 날짜 | 변경 내용 |
|------|----------|
| 2026-04-07 | dashboard/ 최초 생성, app.py + 3개 pages + utils/formatters.py 구현, 21개 테스트 통과 |
| 2026-04-07 | 0_파이프라인_추적.py 추가 — 8단계 타임라인 + Researcher/RiskManager 회의록 전문 표시. build_pipeline_trace() 구현, 28개 테스트 통과 |
