---
name: task-start
description: |
  Use this when beginning work on a new task from TASKS.md or BACKLOG.md.
  Triggers on: "시작할게", "태스크 시작", "이거 해줘" (with a specific task),
  or picking up a new task after previous one completed.
---

# Task Start Skill

## Goal
태스크 시작 전 필요한 컨텍스트를 로드하고 현재 상태를 파악한다.
"일단 시작하고 나중에 읽기" 패턴을 방지한다.

## Instructions

1. **태스크 확인**
   - TASKS.md에서 해당 태스크의 설계 구상 / 제약사항 읽기
   - 관련 파일 목록 파악

2. **아키텍처 컨텍스트 로드**
   - DEV_GUIDE.md에서 관련 섹션 읽기
   - 수정할 폴더의 `_GUIDE.md` 읽기 (금지사항 필수 확인)

3. **현재 상태 파악**
   ```
   python scripts/harness.py {folder}/
   ```
   - baseline 테스트 수 확인
   - 기존 실패 있으면 먼저 보고

4. **시작 전 체크리스트 보고**
   - 관련 금지사항 요약
   - 수정할 파일 목록
   - baseline 테스트 수

## Constraints
- _GUIDE.md 읽기 전에 코드 수정 시작 금지
- baseline harness 실행 전에 코드 수정 시작 금지
