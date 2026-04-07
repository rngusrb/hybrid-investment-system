# execution/ — 주문 실행 레이어 가이드

## 역할
Otto allocation(equities/hedge/cash %)을 실제 주문 수량으로 변환.
현재 position_sizer까지만 구현 — 실제 브로커 전송 미구현(의도된 미완성).

---

## 핵심 패턴

### PositionSizer 사용
```python
sizer = PositionSizer(
    portfolio_value=1_000_000,
    current_prices={"SPY": 500.0, "SH": 41.0},
)
plan = sizer.compute(
    allocation={"equities": 0.6, "hedge": 0.1, "cash": 0.3},
    execution_plan={"entry_style": "staggered", "stop_loss": 0.05},
    ...
)
```

### state에서 읽는 필드
```python
_portfolio_value    # float, 기본 1,000,000
_current_prices     # {"SPY": 500.0, ...}
_equity_ticker      # 기본 "SPY"
_hedge_ticker       # 기본 "SH"
```

### shares는 항상 정수 (소수 주식 미지원)
```python
shares = math.floor(notional / price)  # 내림
```

---

## 금지사항

### ❌ 실제 브로커 API 호출 추가
현재 설계는 OrderPlan 생성까지만. 브로커 연결은 외부 API 계정 필요.
브로커 호출 코드 추가 시 반드시 사전 논의.

### ❌ portfolio_value <= 0 허용
PositionSizer 생성자에서 ValueError 발생. 0이나 음수 입력 금지.

### ❌ allocation 합계 > 1.0 무시
합계가 1.05 초과 시 정규화 + 경고 추가. 조용히 무시하면 안 됨.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `position_sizer.py` | PositionSizer, OrderPlan, OrderLine |

---

## 하네스

```
tests:
  - tests/unit/test_position_sizer.py
```

```bash
python scripts/harness.py execution/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-07 | position_sizer.py | 신규 생성 — allocation → shares/stop_loss/slippage |
