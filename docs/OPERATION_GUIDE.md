# Hybrid Investment System — 실전 작동 설명서

> 직접 돌려보면서 확인한 내용 기반. 공식 문서보다 실제에 가깝습니다.

---

## 1. 이 시스템이 뭘 하는 건가

한 마디로 요약하면: **"AI 애널리스트 팀이 주식을 매일/매주 분석해서 포트폴리오 배분을 결정하는 시스템"**

```
Polygon API (실제 주가/뉴스/재무제표 데이터)
        ↓
Emily   → 시장 전체 분위기 파악 (risk_on? fragile_rebound?)
        ↓
각 종목 분석 → Fundamental / Sentiment / News / Technical 4개 애널리스트
        ↓
Researcher → Bull vs Bear 토론 → 합의
        ↓
Trader → 초안 매매 결정 (BUY/SELL/HOLD)
        ↓
Risk Manager → 3인 토론 → 포지션 조정
        ↓
Backtester → 6개 전략으로 과거 수익률 시뮬레이션
        ↓
회의 3종 (MAM / SDM / RAM) → 전략 확정
        ↓
Portfolio Manager → 종목 간 비중 배분
        ↓
Dave → 포트폴리오 전체 리스크 점수 계산
        ↓
Otto → 최종 승인 게이트 (approved / conditional / rejected)
        ↓
results/{날짜}/portfolio.json 저장
```

**중요한 특징**: 모든 에이전트가 LLM(claude)을 실제로 호출합니다. 날짜 하나 처리에 약 2~3분 걸리는 이유가 여기 있습니다.

---

## 2. 실행 전 준비

### API 키 설정
`.env` 파일에 두 개만 있으면 됩니다:
```
ANTHROPIC_API_KEY=sk-ant-...
POLYGON_API_KEY=...
```

> OpenAI 키는 필요 없습니다. `config/system_config.yaml`에서 provider가 anthropic으로 설정돼 있습니다.

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 크레딧 확인 (중요!)
직접 돌려본 결과, **하루치(날짜 1개)에 약 $0.5~1 정도** 소모됩니다.
종목 2개 × 1개월(약 23일) = 약 $10~20 예상.
실행 전에 Anthropic Console에서 잔액 확인 필수.

---

## 3. 실행 방법

### 기본 실행
```bash
# 일간 (매 영업일)
python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-01-31 --freq daily

# 주간 (매주 금요일)
python scripts/run_loop.py AAPL NVDA TSLA --start 2024-01-01 --end 2024-03-31
```

### 이어서 실행 (중단됐을 때)
```bash
# --resume: 이미 성공한 날짜 스킵, 나머지만 실행
python scripts/run_loop.py AAPL NVDA --start 2024-01-01 --end 2024-01-31 --freq daily --resume
```

> **주의**: `--resume`은 `results/{날짜}/portfolio.json` 파일이 존재하면 무조건 스킵합니다.
> 크레딧 부족으로 실패했어도 파일이 있으면 스킵합니다.
> 실패한 날짜를 재실행하려면 해당 폴더를 직접 삭제 후 실행해야 합니다.

### 실패 날짜 폴더 정리 후 재실행
```bash
# 실패한 날짜 확인
for dir in results/2024-01-*/; do
  date=$(basename $dir)
  errors=$(python3 -c "import json; d=json.load(open('$dir/portfolio.json')); print(len(d.get('errors',[])))" 2>/dev/null)
  echo "$date: errors=$errors"
done

# 실패 폴더 삭제 후 재실행
rm -rf results/2024-01-04  # 예시
python scripts/run_loop.py AAPL NVDA --start 2024-01-04 --end 2024-01-31 --freq daily
```

---

## 4. 실행 중 터미널에서 보이는 것

```
[1/23] 2024-01-01
  [r_real] 2개 결과 업데이트: ['AAPL', 'NVDA']   ← 이전 결과 r_real 업데이트
  [Memory] 첫 실행                                ← 메모리 컨텍스트
  [Gating] (없으면 표시 안 됨)

  ✅  2024-01-01  [142s]                          ← 성공 + 소요 시간

  NVDA BUY 20%  AAPL SELL 0%  cash=70%            ← 최종 배분 요약
```

날짜 하나당 **2~3분** 소요. 23일이면 약 **50~70분** 예상.

---

## 5. 결과 파일 구조

실행이 끝나면 `results/{날짜}/portfolio.json`에 저장됩니다.

```json
{
  "date": "2024-01-04",
  "tickers": ["AAPL", "NVDA"],

  "emily": {
    "market_regime": "fragile_rebound",   ← 시장 레짐
    "regime_confidence": 0.62,            ← 신뢰도 (0.55 이하면 불확실성 모드)
    "technical_confidence": 0.58
  },

  "dave": {
    "risk_score": 0.42,                   ← 0.7 초과면 defensive 재실행
    "risk_level": "medium",
    "risk_components": { "beta": 0.3, "volatility": 0.4, ... }
  },

  "otto": {
    "approval_status": "conditional_approval",  ← approved / conditional / rejected
    "conditional_controls": [...]
  },

  "execution_feasibility": {
    "feasibility_score": 0.606,           ← 0.4 미만이면 staggered 강제
    "avg_sharpe": 1.2,
    "cash_pct": 0.75,
    "dave_risk_score": 0.42
  },

  "portfolio": {
    "allocations": [
      { "ticker": "NVDA", "weight": 0.20, "action": "BUY" },
      { "ticker": "AAPL", "weight": 0.00, "action": "SELL" }
    ],
    "cash_pct": 0.75,
    "hedge_pct": 0.05
  },

  "meetings": {
    "mam": { "market_regime": "fragile_rebound", "debate_skipped": false, ... },
    "sdm": { "strategy_recommendations": { "NVDA": { "sharpe": 4.3, ... } }, ... },
    "ram": { "triggered": false, "avg_risk_score": 0.42, ... }
  },

  "reliability_summary": {
    "fundamental": 0.631,
    "sentiment": 0.631,
    ...
  },

  "errors": []   ← 정상이면 빈 배열
}
```

---

## 6. 결과 해석 방법

### Emily — 시장 레짐

| regime | 의미 | 시스템 반응 |
|--------|------|------------|
| `risk_on` | 강세장, 매수 적합 | 정상 실행 |
| `fragile_rebound` | 반등 중이나 불안정 | uncertainty_mode 가능성 |
| `risk_off` | 약세장 | 방어적 포지션 |
| `sideways` | 횡보 | 보수적 배분 |

`regime_confidence < 0.55` → `uncertainty_mode = True` → Dave 스트레스 배수 증가, Otto 주식 비중 축소

### Dave — 리스크 점수

| risk_score | 의미 |
|-----------|------|
| < 0.5 | 낮음 (정상 실행) |
| 0.5 ~ 0.7 | 보통 |
| > 0.7 | **높음 → Backtester defensive 재실행** |

### Otto — 승인 상태

| approval_status | 의미 |
|----------------|------|
| `approved` | 그대로 실행 |
| `approved_with_modification` | 포지션 소폭 조정 후 승인 |
| `conditional_approval` | 조건부 (변동성 모니터링 등) |
| `rejected` | 거부 → Portfolio Manager 재실행 (최대 2회) |

### Execution Feasibility

| feasibility_score | 의미 |
|-------------------|------|
| ≥ 0.4 | 정상 실행 |
| < 0.4 | **staggered execution 강제** (한 번에 전량 매매 금지) |

---

## 7. 대시보드 사용법

```bash
streamlit run dashboard/app.py
```

브라우저에서 `http://localhost:8501` 열면 됩니다.

### 페이지 구성

| 페이지 | 데이터 소스 | 주요 내용 |
|--------|------------|----------|
| **app (메인)** | 실시간 실행 | 종목 입력 → Pipeline A 즉시 실행 |
| **0. 파이프라인 추적** | session_state | 에이전트별 회의 내용 단계별 보기 |
| **1. 뉴스 데이터** | session_state | 원문 뉴스 기사 테이블 |
| **2. 에이전트 보고서** | session_state | 각 에이전트 분석 보고서 |
| **3. 포트폴리오 결과** | session_state | 파이차트 + 레이더 차트 |
| **4. B/C 결과** | results/{날짜}/ | Emily/Dave/Otto 결과 + 신뢰도 바 차트 |
| **5. 평가 결과** | results/eval_*.json | System vs 베이스라인 수익률 비교 |

> **4번, 5번 페이지**는 메인 페이지에서 실행 안 해도 됩니다. `run_loop.py`로 저장된 파일에서 직접 읽어옵니다.

### 4번 페이지 (B/C 결과) 상세

날짜를 선택하면:
- **Emily 섹션**: 레짐 + 신뢰도. 불확실성 모드 ON/OFF 표시
- **Dave 섹션**: 리스크 점수 (🔴>0.7 / 🟡>0.5 / 🟢 이하)
- **Otto 섹션**: 승인 상태 배지 + Feasibility 점수
- **신뢰도 바 차트**: 에이전트별 신뢰도. 빨간선(0.35) 이하면 GATED
- **회의 요약**: MAM/SDM/RAM expander로 펼쳐보기

> 신뢰도가 처음에 전부 똑같이 나오는 건 정상입니다. r_real 데이터가 쌓여야 차이가 생깁니다.

---

## 8. 자주 만나는 에러와 대처법

### ❌ `credit balance is too low`
```
anthropic.BadRequestError: Error code: 400 - credit balance is too low
```
**원인**: Anthropic API 크레딧 소진
**해결**: console.anthropic.com에서 크레딧 충전 후, 실패 폴더 삭제 후 재실행

```bash
# 실패 폴더 찾아서 삭제
for dir in results/2024-01-*/; do
  errors=$(python3 -c "import json; d=json.load(open('${dir}portfolio.json')); print(len(d.get('errors',[])))" 2>/dev/null)
  [ "$errors" != "0" ] && echo "삭제: $dir" && rm -rf "$dir"
done
```

---

### ❌ `could not convert string to float: 'monitor'`
```
ValueError: could not convert string to float: 'this_week'
```
**원인**: Portfolio Manager LLM이 `rebalance_urgency`를 문자열로 반환
**해결**: 이미 수정됨 (`_urgency_to_float()` 헬퍼). 재현 시 `integration/_GUIDE.md` 참조

---

### ❌ BC_EMILY, BC_STOCK 실패 + Portfolio 빈 배분
```
[BC_PORTFOLIO] stock_results 없음 — 스킵
[BC_DAVE] portfolio 없음 — 스킵
[BC_OTTO] emily_output 또는 portfolio 없음 — 스킵
```
**원인**: 앞 단계 실패(보통 API 크레딧)로 연쇄 스킵
**해결**: 앞 단계 에러 원인 해결 후 해당 날짜 폴더 삭제 + 재실행

---

### ❌ Emily/Dave/Otto가 N/A로 표시 (대시보드)
**원인 A**: 크레딧 부족으로 실패한 날짜
**원인 B**: 구 버전 run_loop.py로 저장된 파일 (해당 필드가 없음)
**해결**: 해당 날짜 재실행

---

## 9. 신뢰도 시스템 이해

에이전트 신뢰도는 EMA(지수이동평균) 기반으로 자동 업데이트됩니다.

```
r_real: 실제 수익률 (T+7일 후 자동 채워짐)
r_sim: 백테스터 시뮬레이션 수익률

신뢰도 업데이트:
- 예측이 실제와 일치 → 신뢰도 ↑
- 예측과 실제가 다름 → 신뢰도 ↓
- floor = 0.35 이하 → GATED (해당 에이전트 신호 무시)
```

초기에 전부 같은 값(0.54~0.63)이 나오는 건 정상입니다. 3개월치 데이터가 쌓이면 에이전트마다 다른 신뢰도가 나타납니다.

신뢰도 현황은 `results/reliability_state.json`에서 확인합니다.

---

## 10. 평가 파이프라인

run_loop.py 실행 후 성과를 측정합니다:

```bash
python scripts/run_eval.py --start 2024-01-01 --end 2024-03-31
# → results/eval_2024-03-31.json 저장
```

결과 예시 (2024 Q1):
```
Hybrid System   CR +15.7%  SR 3.11  MDD 4.4%  승률 83%
Buy & Hold AAPL CR  -4.9%  SR -1.17 MDD 11.3% 승률 55%
MACD (12/26/9)  CR  -3.0%  SR -1.85 MDD 3.4%  승률 9%
```

대시보드 5번 페이지에서 시각화로 확인 가능합니다.

---

## 11. 전체 흐름 요약 (한눈에)

```
1. run_loop.py 실행
        ↓
2. 날짜별 반복
   Emily (레짐) → Stock Analysis (4 애널리스트) → Backtester
   → Meetings (MAM/SDM/RAM) → Calibration → Reliability Update
   → Portfolio Manager → Dave (리스크) → [0.7 초과면 defensive 재실행]
   → Otto (승인) → [rejected면 PM 재실행 최대 2회]
   → results/{날짜}/portfolio.json 저장
        ↓
3. 대시보드에서 결과 조회 (streamlit run dashboard/app.py)
        ↓
4. 평가 (run_eval.py) → System vs Baseline 비교
```

---

*작성일: 2026-05-12 | 직접 실행 경험 기반*
