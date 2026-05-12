# 스프린트 아카이브: Retrieval 강화 + 감사 보고서 갱신
**기간**: 2026-04-28
**결과**: 2개 태스크 완료, 884 passed (878 → +6)

---

## 스프린트 목표
memory retrieval validity scoring 실제 적용 / 시스템 감사 보고서 최신화.

---

## 완료 태스크 요약

### B-004: Retrieval validity scoring B/C 연결
- `memory/run_memory.py`: `build_context()`에 `as_of`, `current_regime` 파라미터 추가 (기본값 None, 하위 호환)
- `_result_to_case()` 헬퍼: portfolio result dict → validity_scorer case 형식 변환
- `_apply_validity_filter()` 헬퍼: 후보 2N개 → compute_validity_score() 적용 → threshold=0.3 필터 → score 내림차순 → 상위 N개
- fallback: 전부 미달이면 기존 방식(verified 우선 정렬) 유지
- `tests/unit/test_run_memory.py`: TestBuildContextValidityScoring 6개 테스트 추가
- `memory/_GUIDE.md`: 최근 변경 기록 추가

### B-005: 감사 보고서 갱신
- `docs/SYSTEM_AUDIT_REPORT_v2.md`: 2026-04-17 스냅샷 → 2026-04-28 전면 갱신
- 전체 구현율 42~48% → 62~68% 상향
- 11개 항목 Actual/Notes 전부 업데이트
- Pipeline A+B/C integration, Agent Gating, Dual Reward, MAM → Functional/Completed 처리
- Section 2: 2.6~2.8 신규 추가
- Section 3: Critical Gaps 4개 RESOLVED 표시
- 갱신 이력 섹션 추가

---

## 회고 메모
- BACKLOG가 비었음 — 다음 스프린트는 새 태스크 발굴 필요
- B-004 compute_validity_score 시그니처(5개 인자)가 예상과 달라 어댑터 패턴 필요했음
