"""graph/nodes/bc_meetings.py — BC_MEETINGS 노드: MAM/SDM/RAM 실행.

llm을 run_all_meetings에 전달 → debate_skipped=False 시 LLM 토론 실행.
"""
import logging
logger = logging.getLogger(__name__)


def bc_meetings_node(state: dict) -> dict:
    """MAM/SDM/RAM 실행. MAM은 consensus < 0.80 시 LLM 토론 수행."""
    from meetings.run_meetings import run_all_meetings, format_meetings_for_prompt

    stock_results = state.get("stock_results", [])
    sim_results   = state.get("sim_results", {})
    date          = state["current_date"]
    prev_r_real   = state.get("prev_r_real")
    llm           = state.get("_llm_analyst")
    errors        = list(state.get("errors", []))

    try:
        meetings = run_all_meetings(
            stock_results, sim_results, date,
            r_real=prev_r_real,
            llm=llm,
        )
        meetings_context = format_meetings_for_prompt(meetings)

        ram = meetings.get("ram", {})
        mam = meetings.get("mam", {})
        logger.info(
            f"[BC_MEETINGS] regime={mam.get('market_regime','?')}  "
            f"llm_debate={mam.get('llm_debate_used',False)}  "
            f"RAM triggered={meetings.get('ram_triggered',False)}"
        )
        return {"meetings": meetings, "meetings_context": meetings_context, "errors": errors}

    except Exception as e:
        logger.warning(f"[BC_MEETINGS] 실패: {e}", exc_info=True)
        errors.append({"node": "BC_MEETINGS", "error": str(e)})
        return {"meetings": {}, "meetings_context": "", "errors": errors}
