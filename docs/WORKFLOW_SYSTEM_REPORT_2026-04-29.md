# Workflow System 개편 보고서

**날짜**: 2026-04-29
**대상**: 기술 검토
**범위**: 문서 관리 체계 → 자동화 검증 체계 전환

---

## 1. 문제 정의

### 기존 구조의 근본 약점

이 프로젝트는 `CLAUDE.md`, `WORKFLOW.md`, `TASKS.md`, `_GUIDE.md`(18개) 등 다수의 관리 문서를 운영해왔다. 초기엔 강력한 구조였지만 다음 문제가 반복됐다.

- **수동 갱신 의존**: 스프린트 완료 후 TASKS.md, BACKLOG.md, CLAUDE.md를 사람이 기억해서 순서대로 갱신해야 함
- **컨텍스트 소실**: 세션이 길어지면 이전에 약속한 문서 갱신이 압축 이후 누락됨
- **문서 부채 누적**: `_GUIDE.md` 최근 변경 섹션, 파일 구조 섹션이 항상 낡은 상태로 방치됨
- **규칙 비강제**: "이렇게 해야 한다"는 문서가 있어도 어겨도 아무 일이 안 일어남

핵심 진단: **문서를 더 열심히 쓰면 해결되는 문제가 아니었다.**

---

## 2. 설계 방향

### 원칙

> "사람이 기억해야 유지되는 규칙" → "시스템이 강제하는 규칙"

구체적으로:
- `문서`를 운영 원천으로 두지 않고, `검사 가능한 데이터`를 원천으로
- 사람이 직접 갱신해야 하는 문서는 최소화, 나머지는 자동 검증
- 절차는 Skills가 실행, 규칙은 Harness가 강제

### 구조

```
원칙층   CLAUDE.md (헌법), WORKFLOW.md (운영 레퍼런스)
상태층   TASKS.md (현재판 전용), BACKLOG.md
규칙층   _GUIDE.md × 18 (금지사항 + 패턴만)
실행층   .agent/skills/ (sprint-close, harness-run, task-start)
검증층   scripts/harness.py (pytest + doc lint)
원천층   meta/project_state.yaml
기록층   docs/sprints/
```

검증층과 실행층이 같이 있어야 루프가 닫힌다.
검증(harness)만 있으면 "문제 감지"는 되지만 "자동 처리"가 없다.
Skills가 실행층으로 들어와야 "감지 → 처리 → 재검증" 루프가 완성된다.

---

## 3. 구현 내용

### 3-1. Agent Skills (`.agent/skills/`)

오픈 표준 Agent Skills 포맷 적용. description 기반 자동 트리거.

| 스킬 | 트리거 조건 | 실행 내용 |
|------|-----------|---------|
| `sprint-close` | "스프린트 완료", 전 태스크 completed | docs/sprints 아카이브 → TASKS/BACKLOG/CLAUDE.md 갱신 → harness all |
| `harness-run` | 코드 수정 후, "테스트 돌려" | 폴더 harness → 실패 시 원인 분석 (2회 연속 실패 시 중단) → all |
| `task-start` | "시작할게", 태스크 픽업 | DEV_GUIDE + _GUIDE.md 로드 → baseline harness → 금지사항 보고 |

**정책 명문화 (sprint-close)**:
```
태스크 완료 → TASKS.md completed 표시 (잠깐 허용)
           → sprint-close 실행
           → harness lint: completed 본문 없음 → PASS
```
harness의 "completed 본문 금지"는 sprint-close를 안 돌렸을 때 잡는 안전망이다.

### 3-2. Harness Doc Lint (`scripts/harness.py`)

`python scripts/harness.py all` 실행 시 pytest 전에 자동 실행.

**FAIL 조건** (exit code 1):
```
- TASKS.md에 **상태**: completed 본문 존재
- TASKS.md 활성 태스크 4개 이상
- 시크릿 하드코딩 (sk-, ANTHROPIC_API_KEY=, OPENAI_API_KEY=, polygon_api_key 등)
- meta/project_state.yaml entry_points 파일 미존재
```

**WARN 조건**:
```
- _GUIDE.md에 ## 최근 변경 섹션 존재
- meta folder_guides _GUIDE.md 미존재
```

**탐지 범위**: `.py`, `.yaml`, `.yml`, `.env`, `.env.example`, `.md`

### 3-3. meta/project_state.yaml

harness가 검증할 사실 데이터만. 설명 없음.

```yaml
entry_points:
  bc_pipeline: graph/bc_graph.py   # B/C LangGraph 진입점
  pipeline_a:  graph/builder.py
  run_loop:    scripts/run_loop.py
  portfolio:   scripts/portfolio_pipeline.py
  harness:     scripts/harness.py

sprint_archive_dir: docs/sprints/

folder_guides:                     # 18개 폴더 _GUIDE.md 매핑
  simulation: simulation/_GUIDE.md
  ...
```

파일이 없으면 → harness lint FAIL. yaml이 현실과 맞게 유지 강제됨.

### 3-4. 문서 다이어트

| 대상 | 변경 | 결과 |
|------|------|------|
| `CLAUDE.md` | 완료 이력 상세 제거 | 140줄 → 55줄 |
| `WORKFLOW.md` | 절차 상세 제거, Skills 표 추가 | 210줄 → 60줄 |
| `TASKS.md` | completed 본문 전부 제거 | 현재판 전용 |
| `_GUIDE.md` × 18 | `## 최근 변경` + `## 파일 구조` 제거 | 규칙/금지사항만 |

---

## 4. 검증

```
harness all 결과: 899 passed, doc lint ✅
```

실제 FAIL 감지 테스트:
- TASKS.md에 completed 본문 임시 추가 → `❌ tasks_completed_body` FAIL, exit 1
- meta/project_state.yaml에 존재하지 않는 파일 추가 → `⚠️ missing_entry_point` 감지

---

## 5. 개편 전/후 비교

| 항목 | 개편 전 | 개편 후 |
|------|--------|--------|
| 스프린트 클로즈아웃 | 사람이 기억해서 순서대로 실행 | sprint-close 스킬 자동 트리거 |
| 문서 규칙 강제 | 없음 (어겨도 무방) | harness lint FAIL → 진행 불가 |
| _GUIDE.md 신뢰도 | 낡은 변경 이력/파일 구조 포함 | 금지사항/패턴만, 검증 대상에서 제외 |
| 시크릿 탐지 | 없음 | .py + yaml + env + md 전체 |
| 진입점 파일 관리 | 문서에 설명 | meta yaml + harness 검증 |

---

## 6. 잔존 과제 (BACKLOG)

| 항목 | 설명 | 우선순위 |
|------|------|---------|
| D-001 | bc_graph 통합 테스트 — 노드 단위만 있고 conditional edge 흐름 테스트 없음 | medium |
| D-002 | DEV_GUIDE.md B/C 파이프라인 섹션 — sequential 기준 설명이 LangGraph 전환 미반영 | low |

---

## 7. 현재 상태 평가

| 항목 | 점수 |
|------|------|
| 구조 반영도 | 9/10 |
| 문서 다이어트 완료도 | 9/10 |
| harness 검증 완성도 | 8/10 |
| 스킬-문서 정책 정합성 | 9/10 |
| **전체 운영체계 성숙도** | **9/10** |

남은 1점: bc_graph 통합 테스트, DEV_GUIDE B/C 섹션 갱신.

---

*작성: 2026-04-29*
