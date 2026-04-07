# utils/ — 공유 유틸리티 가이드

## 역할
여러 레이어에서 공통으로 쓰는 순수 함수 모음.
특정 도메인에 종속되지 않는 것만 여기에 둠.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `utility.py` | Utility 공식 단일 소스. policy.py + otto.py 모두 여기서 가져옴 |
| `forward_return.py` | Polygon T+1 실제 수익률 계산. 실패 시 None 반환 |

---

## 핵심 패턴

### utility.py — 단일 소스 원칙
```python
from utils.utility import compute_utility, compute_utility_from_state

# policy.py에서
utility = compute_utility_from_state(state, approval_status)

# otto.py에서
utility = self.compute_utility(...)   # 내부적으로 compute_utility() 위임
```
두 곳이 동일한 공식 사용 보장.

### forward_return.py — 실패는 None으로
```python
r_real = fetch_forward_return(fetcher, ticker, date)
if r_real is None:
    r_real = r_sim   # fallback
```
API 실패, 미래 날짜, 가격 없음 등 모두 None 반환. 예외 발생 금지.

---

## 금지사항

### ❌ utils/에 도메인 로직 추가
에이전트 판단, 리스크 계산, 전략 선택 같은 도메인 로직은 각 레이어에.
utils는 순수 계산 함수만.

### ❌ utility 공식을 utils 밖에서 재정의
```python
# 금지 — policy.py 안에 직접 구현 (이중화 사고 이력 있음)
utility = 0.5 - 0.3 * risk - 0.2 * uncertainty ...
```

### ❌ fetch_forward_return에서 예외 발생
내부적으로 모든 예외를 catch해서 None 반환. 호출부에서 None 체크로 처리.

---

## 하네스

```
tests:
  - tests/integration/test_e2e_fixes.py
  - tests/integration/test_multicycle.py
```

```bash
python scripts/harness.py utils/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-07 | utility.py | 신규 생성 — policy.py _compute_utility() + otto.py compute_utility() 통합 |
| 2026-04-07 | forward_return.py | 신규 생성 — Polygon T+1 실제 수익률 계산 |
