---
name: harness-run
description: |
  Use this after modifying any code file to verify tests pass before declaring a task done.
  Triggers on: code edit complete, "테스트 돌려", "harness 실행", "검증해봐",
  or before any "완료" declaration.
---

# Harness Run Skill

## Goal
코드 수정 후 테스트를 실행하고 실패 원인을 분석한다.
같은 실패를 반복하지 않도록 중단 기준을 강제한다.

## Instructions

1. **대상 폴더 파악**
   - 수정된 파일의 폴더를 기준으로 대상 결정
   - 예: `simulation/backtester.py` 수정 → `simulation/`

2. **폴더 단위 실행**
   ```
   python scripts/harness.py {folder}/
   ```

3. **실패 시 처리**
   - 실패한 테스트명 + 에러 메시지 출력
   - 원인 파악 후 수정
   - 재실행
   - **같은 실패가 2회 연속이면 즉시 중단** — 설계 재검토 또는 사용자 보고

4. **폴더 통과 후 전체 실행**
   ```
   python scripts/harness.py all
   ```

5. **결과 보고**
   - 통과: `{N} passed` 확인
   - 실패: 실패 테스트 목록 + 원인 요약

## Constraints
- 같은 수정을 10회 이상 반복 금지
- harness 실패 상태에서 "완료" 선언 금지
- `--no-verify` 또는 테스트 스킵 금지
