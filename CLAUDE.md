# Hybrid Investment System — Claude 작업 지침

## 필독
작업 시작 전 반드시 읽을 것:
- **DEV_GUIDE.md** — 코드 작성 프로토콜, 데이터 흐름 지도, 전역 금지사항
- **해당 폴더/_GUIDE.md** — 폴더별 패턴, 금지사항, 하네스

## 작업 기본값
- 테스트 수반 작업: **전부 통과할 때까지 루프 반복** (max 10회)
- 중간 확인 요청 금지 — 막히면 `_GUIDE.md` 규칙 갱신 후 재시도
- 10회 초과 시에만 현황 보고 후 대기

## 작업 프로토콜 (매 작업마다)
```
1. DEV_GUIDE.md 확인
2. 해당 폴더 _GUIDE.md 확인
3. python scripts/harness.py <폴더>/ 실행 (현재 상태 파악)
4. 코드 수정
5. python scripts/harness.py <폴더>/ 재실행 (검증)
6. 실패 시 → 원인 파악 → 코드 수정 → _GUIDE.md 금지사항 갱신 → 5번으로
7. 통과 시 → _GUIDE.md 최근변경 업데이트 → 완료
```

> 6번에서 _GUIDE.md 갱신 없이 "완료" 선언 금지.
