---
name: sprint-close
description: |
  Use this when all tasks in the current sprint are completed and need to be archived.
  Triggers on: "스프린트 완료", "다 끝났어", "클로즈아웃", all TASKS.md tasks showing completed status,
  or after harness all passes with no remaining in_progress tasks.
---

# Sprint Close Skill

## Goal
스프린트 완료 시 문서를 자동으로 정리하고 아카이브를 생성한다.
사람이 기억할 필요 없이 일관된 클로즈아웃을 보장한다.

## 완료 상태 정책

작업 흐름:
```
태스크 완료 → TASKS.md에 상태: completed 표시 (잠깐 허용)
           → sprint-close 스킬 실행 (감지 + 아카이브 + 제거)
           → harness lint: completed 본문 없음 → PASS
```
harness lint의 "completed 본문 금지"는 sprint-close를 안 돌렸을 때 잡는 안전망이다.
sprint-close 실행 직전까지는 completed 상태가 TASKS.md에 잠깐 존재해도 된다.

## Instructions

1. **TASKS.md 확인**
   - 현재 스프린트 태스크가 전부 completed 상태인지 확인
   - in_progress / pending 태스크가 남아있으면 중단하고 보고
   - "현재 스프린트: 없음"이면 정리할 것이 없으므로 종료

2. **docs/sprints/ 아카이브 생성**
   - 파일명: `docs/sprints/SPRINT_{YYYY-MM-DD}_{slug}.md`
   - 포함 내용: 스프린트 목표, 태스크별 완료 기준 달성 여부, harness 결과, 미완성 항목
   - 기존 `docs/SPRINT_*.md` 파일이 있으면 `docs/sprints/`로 이동 처리

3. **TASKS.md 정리**
   - completed 태스크 본문 전부 제거
   - 완료된 스프린트 테이블에 1줄 추가 (날짜, 스프린트명, 아카이브 링크)
   - "현재 스프린트: 없음" 상태로 초기화

4. **BACKLOG.md 갱신**
   - 스프린트 중 발견된 후속 이슈 추가
   - 완료된 항목 삭제

5. **CLAUDE.md 갱신**
   - "완료된 스프린트" 테이블에 1줄 추가 (날짜 + 스프린트명만)

6. **harness 실행**
   - `python scripts/harness.py all`
   - 결과 보고

## Constraints
- _GUIDE.md 내용 재작성 금지
- DEV_GUIDE.md 수정 금지
- docs/sprints/ 기존 파일 삭제 금지
- CLAUDE.md에 상세 완료 이력 bullet 추가 금지 — 1줄 테이블 행만
- harness 실패 시 클로즈아웃 완료 선언 금지
