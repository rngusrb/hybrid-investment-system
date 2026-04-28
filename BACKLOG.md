# BACKLOG — 대기 중인 이슈 및 태스크

> **분류 기준**
> - 대기 중인 태스크: 설계 고민 필요한 것, 여러 파일 수정 필요한 것
> - 이슈 테이블: 한 줄 수정급, 단순 개선 (작고 빠른 것)
> - 완료된 항목은 즉시 삭제
>
> 스프린트 시작 시 대기 중인 태스크 상위 3개를 TASKS.md로 올림.

---

## 대기 중인 태스크

### D-001: bc_graph 통합 테스트
**우선순위**: medium
**배경**: C-003에서 노드 단위 테스트만 추가. bc_graph 전체 흐름(conditional edges) 통합 테스트 없음.
**작업**: `tests/integration/test_bc_graph.py` — mock LLM으로 Dave risk>0.7, Otto rejected 분기 검증

### D-002: DEV_GUIDE.md B/C 파이프라인 섹션 갱신
**우선순위**: low
**배경**: DEV_GUIDE.md의 B/C 파이프라인 섹션이 sequential 함수 호출 기준으로 작성됨. C-003 이후 LangGraph 구조로 변경.
**작업**: bc_graph.py 흐름도, 9노드 구조, conditional edges 반영

---

## 이슈 테이블
> 한 줄 수정급 단순 이슈. 작업 중 발견 시 즉시 추가, 완료 시 즉시 삭제.

| 발견일 | 파일 | 내용 | 우선순위 |
|--------|------|------|---------|
| 2026-04-21 | `docs/` | AUDIT_WALKFORWARD.md 참조되지만 파일 없음 | low |

---

*마지막 갱신: 2026-04-28 — D-001, D-002 추가 (C-003 스프린트 후속)*
