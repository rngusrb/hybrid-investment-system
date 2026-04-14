# meetings/ — 미팅 레이어 가이드

## 역할
주간/이벤트 기반 협의 프로토콜. 3개 미팅으로 구성.
SharedLedger에 공식 결과만 기록. 토론 transcript는 저장 금지.

---

## 3개 미팅

### Weekly Market Analysis Meeting
1. Bull/Bear 토론 (Emily confidence ≥ 0.85면 간소화)
2. 신호 충돌 감지 (기술적 vs 거시 등 4종)
3. DebateResolution + SignalConflictResolution → Ledger 기록

### Weekly Strategy Development Meeting
- Bob 후보 전략 검토, rejection_reasons 생성
- BobToExecutionPacket 생성 (urgency, hedge_preference)
- confidence < 0.45 전략 자동 거부

### Risk Alert Meeting (이벤트 기반, risk_score > 0.75)
```
RiskAdjustedUtility = (1-λ)*CombinedReward - λ*RiskReward
```
- 긴급 조치: immediate_de_risk / reduce_exposure / add_hedge / consider_full_exit

---

## 핵심 패턴

### Ledger 기록은 공식 결과만
```python
ledger.record("debate_resolution", resolution, date, agent)
# ❌ 금지: ledger.record("debate_transcript", raw_text, ...)
```

### 스킵 조건 명시
```python
# Emily confidence ≥ 0.85면 토론 간소화
# 기술적/거시 방향 일치 시 signal conflict resolution 스킵
```

---

## 금지사항

### ❌ Ledger에 raw 토론 내용 저장
SharedLedger FORBIDDEN frozenset에서 ValueError 발생.
DebateResolution 구조체로만 저장.

### ❌ Risk Alert Meeting을 주기적으로 실행
이벤트 기반(risk_score > 0.75)으로만 트리거.
매일 실행하면 설계 원칙 위반.

### ❌ rejection_reasons 없이 전략 거부
전략 거부 시 이유 명시 필수. Otto가 판단 근거로 사용.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `base_meeting.py` | SharedLedger 연결, _record_to_ledger, _log_skip |
| `market_analysis.py` | Pipeline A — Bull/Bear 토론, 신호 충돌 감지 |
| `strategy_development.py` | Pipeline A — 전략 검토, BobToExecutionPacket 생성 |
| `risk_alert.py` | Pipeline A — RiskAdjustedUtility, 긴급 조치 |
| `run_meetings.py` | Pipeline B/C 어댑터 — MAM/SDM/RAM 실행 + 프롬프트 포맷 |

---

## 핵심 패턴 (run_meetings.py)

### RAM은 이벤트 기반 트리거
```python
# max_risk_score > RISK_ALERT_THRESHOLD(0.75) 일 때만 triggered=True
# 매 주기 실행되지만 triggered=False면 emergency_controls=[]
```

### 시그널 충돌 감지 기준
- `action_changed=True` → risk_manager override conflict
- `tech_score ≥ 7 and fund_score ≤ 3` → tech_strong vs fund_weak
- `tech_score ≤ 3 and fund_score ≥ 7` → tech_weak vs fund_strong

---

## 하네스

```
tests/unit/test_run_meetings.py
tests/integration/test_weekly_cycle.py
tests/integration/test_risk_alert.py
```

```bash
python scripts/harness.py meetings/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-06 | risk_alert.py | stress test seed 날짜 기반 변경 |
| 2026-04-14 | run_meetings.py | 신규 (Phase 4): Pipeline B/C용 MAM/SDM/RAM 어댑터. 40개 테스트 |
