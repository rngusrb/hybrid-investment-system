# Sprint 2026-05-12 — Dashboard Pipeline B/C 반영 (G-001)

## 목표
run_loop.py 실행 결과(results/*.json)를 Streamlit 대시보드에서 조회할 수 있도록
B/C 파이프라인 전용 페이지 2개 신설.

## 완료 항목

### G-001-A: formatters.py B/C 로더 함수 추가
- `_RESULTS_DIR` 모듈 상수 (monkeypatch 가능)
- `list_bc_dates()` — results/ 에서 portfolio.json 있는 날짜 목록
- `load_bc_result(run_date)` — results/{date}/portfolio.json 로드
- `load_eval_results()` — results/eval_*.json 전부 로드
- `format_approval_badge(status)` — approved/rejected/conditional → 이모지 배지
- `format_reliability_rows(reliability_summary)` — 신뢰도 테이블 rows

### G-001-B: 페이지 4 — B/C 파이프라인 결과
`dashboard/pages/4_🔄_BC결과.py`
- Emily: market_regime, regime_confidence, technical_confidence, uncertainty_mode
- Dave: risk_score (🔴/🟡/🟢), stress_multiplier, risk_components 테이블, defensive 트리거
- Otto: approval_status 배지, retry 횟수, execution_feasibility 점수, 조건부 제어
- Reliability: 에이전트별 바 차트 (floor=0.35 기준선 포함)
- Execution Feasibility: 5개 구성요소 메트릭 카드
- Meetings: expander로 MAM/SDM/RAM 내용 표시
- 에러: errors 목록 상단 표시

### G-001-C: 페이지 5 — 평가 결과
`dashboard/pages/5_📈_평가결과.py`
- Hybrid System KPI 4종 (CR/SR/MDD/WinRate)
- 전략별 지표 비교표 (System vs BnH vs MACD vs SMA)
- 누적 수익률 시계열 라인 차트 (Plotly)
- 복수 eval 파일 선택 지원

### G-001-D: 테스트 추가 (+17개)
`tests/unit/test_dashboard_utils.py`
- TestListBcDates (3), TestLoadBcResult (3), TestLoadEvalResults (3)
- TestFormatApprovalBadge (4), TestFormatReliabilityRows (4)

### G-001-E: 문서 갱신
- `dashboard/_GUIDE.md`: 데이터 소스 구분 섹션 + 페이지 목록 테이블 추가

## 결과
- 테스트: 1033 passed (기존 1016 → +17)
- Doc Lint: 통과
