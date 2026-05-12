# WORKFLOW — 작업 프로토콜

## 태스크 관리 규칙

- TASKS.md에는 **현재 태스크 최대 3개**만 (completed 본문 금지 — harness lint 실패)
- 완료 → `docs/sprints/` 아카이브 → BACKLOG.md에서 다음 올림

### 태스크 연장 vs 백로그

| 기준 | 처리 |
|------|------|
| 현재 테스트 통과에 직접 영향, 2~3줄 이내 | 현재 태스크 연장 |
| 별도 파일/모듈 영향, 설계 고민 필요 | BACKLOG.md |

---

## 멀티에이전트 구성

복잡한 작업 (신규 모듈, 파이프라인 변경):

```
팀 리드  →  TASKS.md 설계 구상 작성 + 팀 구성
구현 팀원 × N  →  태스크별 병렬 구현 + harness 자기 폴더
테스트 팀원  →  harness all + TASKS.md 피드백
최종 확인 팀원  →  체크리스트 + sprint-close 스킬 실행
```

단순 작업 (버그픽스, 단일 파일) → CLAUDE.md 프로토콜.

### 태스크 스키마

```markdown
## X-NNN: 태스크 이름
**상태**: pending | in_progress | completed
**우선순위**: high | medium | low
**관련 파일**: ...

> ⚠️ completed 상태는 sprint-close 직전 전이 상태 전용.
> TASKS.md에 completed 본문을 남기면 harness Doc Lint FAIL.
> sprint-close 후 본문 삭제 → 완료 스프린트 테이블 링크만 유지.

### 설계 구상
### 구현 세부사항
### 완료 기준
### 제약사항
### 테스트 피드백
### 최종 확인
- [ ] harness all 통과
- [ ] _GUIDE.md 금지사항 위반 없음
- [ ] sprint-close 스킬 실행
```

---

## 이슈 심각도

| 심각도 | 의미 |
|--------|------|
| 🔴 Critical | 결과 무효화 (lookahead bias, 순환 논리) |
| 🟠 High | 수치 크게 왜곡 (수식 오류, 잘못된 proxy) |
| 🟡 Medium | 구조적 문제, 결과 왜곡 제한적 |
| 🟢 Low | 개선 여지, 치명적이지 않음 |

🔴 Critical → `blocked` 상태로 전환, 즉시 보고.
동일 에러 2회 연속 → 설계 재검토.

---

## Silent Failure 체크

```
□ except Exception: pass/continue 패턴
□ 빈 dict {} 반환 시 호출자가 알아채는가
□ 기본값 fallback 시 로그 있는가
```

---

## Skills

| 스킬 | 트리거 | 위치 |
|------|--------|------|
| `sprint-close` | 스프린트 완료 시 | `.agent/skills/sprint-close/` |
| `harness-run` | 코드 수정 후 검증 | `.agent/skills/harness-run/` |
| `task-start` | 새 태스크 시작 | `.agent/skills/task-start/` |
