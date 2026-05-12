"""graph/nodes/bc_reliability_update.py — BC_RELIABILITY_UPDATE 노드.

설계 스펙 Phase 4.1: DAILY_AGENT_RELIABILITY_UPDATE.
BC_CALIBRATION 이후 reliability 상태를 파일에 명시적으로 동기화하고
최신 summary를 state에 기록.
"""
import logging
logger = logging.getLogger(__name__)


def bc_reliability_update_node(state: dict) -> dict:
    """
    Reliability 상태 파일 동기화.
    - calibration에서 업데이트된 reliability_summary를 state에서 확인
    - persist_reliability_state()로 reliability_state.json 갱신 보장
    - 최신 summary를 reliability_summary로 state에 반환
    """
    from calibration.run_calibration import persist_reliability_state

    errors = list(state.get("errors", []))

    try:
        updated_summary = persist_reliability_state()
        below_floor = [a for a, s in updated_summary.items() if s < 0.35]
        logger.info(
            f"[BC_RELIABILITY_UPDATE] reliability_state.json 갱신 완료 "
            f"agents={list(updated_summary.keys())} "
            f"below_floor={below_floor or 'none'}"
        )
        return {
            "reliability_summary": updated_summary,
            "errors": errors,
        }

    except Exception as e:
        logger.warning(f"[BC_RELIABILITY_UPDATE] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_RELIABILITY_UPDATE", "error": str(e)})
        return {"errors": errors}
