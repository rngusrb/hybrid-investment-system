# Hybrid Investment System — Claude 작업 지침

## 문서 계층 구조

| 파일 | 역할 |
|------|------|
| **CLAUDE.md** (이 파일) | 핵심 원칙 + 완료 스프린트 목록 |
| **DEV_GUIDE.md** | 전체 아키텍처 지도, 데이터 흐름, 금지사항 색인 |
| **WORKFLOW.md** | 태스크 lifecycle, 역할, 이슈 심각도 기준 |
| **TASKS.md** | 현재 스프린트 태스크 (최대 3개, 현재판 전용) |
| **BACKLOG.md** | 발견된 이슈 + 다음 스프린트 대기 태스크 |
| **각폴더/_GUIDE.md** | 폴더별 금지사항 + 핵심 패턴 (설명서 아님) |
| **docs/sprints/** | 완료된 스프린트 아카이브 |

**작업 시작 전 반드시**: DEV_GUIDE.md → TASKS.md → 해당 폴더/_GUIDE.md

---

## 핵심 원칙

- **Silent Failure 금지**: `except Exception: pass`, 빈 dict 반환, 로그 없는 fallback — 반드시 로깅
- **"완료" 기준**: `python scripts/harness.py all` 통과 + _GUIDE.md 금지사항 위반 없음
  - `python -m pytest` 단독 실행은 완료 검증으로 인정하지 않음 (Doc Lint 누락)
  - 단축 명령: `sh scripts/verify.sh`
- **테스트 루프**: 실패 시 원인 파악 → 수정 → 재실행 (max 10회, 초과 시 보고)
- **문서 갱신 범위**: 단순 버그픽스 → _GUIDE.md만. 파이프라인 변경 → DEV_GUIDE.md도.

---

## 두 가지 작업 프로토콜

**단순 작업** (버그픽스, 단일 파일):
```
_GUIDE.md 확인 → harness <폴더>/ → 수정 → harness 재실행 → 통과
```

**복잡한 작업** (신규 모듈, 파이프라인 변경):
```
WORKFLOW.md 멀티에이전트 프로토콜 사용
```

---

## 완료된 스프린트

| 날짜 | 스프린트 |
|------|---------|
| 2026-04-21 | Pipeline A+B/C 통합 + 기술 부채 픽스 |
| 2026-04-28 | 학습 루프 완성 + 품질 강화 (B-001~003) |
| 2026-04-28 | Retrieval 강화 + 감사 보고서 갱신 (B-004~005) |
| 2026-04-28 | LangGraph B/C 전환 + 에이전트 피드백 루프 (C-001~003) |
| 2026-05-05 | bc_graph 통합 테스트 + 문서 정합성 픽스 (D-001) |
| 2026-05-06 | Agent Reliability → Otto 연결 + BC_RELIABILITY_UPDATE 노드 (E-001, E-002) |
| 2026-05-06 | Execution Feasibility Layer 완성 (E-003) |
| 2026-05-06 | Uncertainty Propagation 체인 완성 (E-004) |
| 2026-05-12 | 시스템 안정성 픽스 4종 (F-001~F-004) |
| 2026-05-12 | 평가 파이프라인 구축 (E-005, E-006) |
| 2026-05-12 | Dashboard Pipeline B/C 반영 (G-001) |

상세 내용 → `docs/sprints/*.md` 참조

---

## CLAUDE.md 업데이트 원칙

| 섹션 | 업데이트 시점 |
|------|-------------|
| 핵심 원칙 | 워크플로우 자체가 바뀔 때만 |
| 완료된 스프린트 | 스프린트 완료 시 1줄 추가 |
