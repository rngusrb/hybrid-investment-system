"""WEEKLY_MARKET_ANALYSIS_MEETING node."""
from graph.state import SystemState
from schemas.audit_schema import NodeResult

EMILY_HIGH_CONFIDENCE_THRESHOLD = 0.85  # debate 간소화 기준


def weekly_market_analysis_meeting(state: SystemState) -> SystemState:
    """
    주간 시장 분석 meeting 실행.
    Emily confidence가 매우 높으면 debate 간소화 (skip_log 기록).
    실제 구현에서는 MarketAnalysisMeeting 호출.
    """
    updated = dict(state)

    emily_confidence = state.get("technical_confidence", 0.5)
    current_date = state.get("current_date")

    # Emily confidence 매우 높으면 debate 간소화
    if emily_confidence >= EMILY_HIGH_CONFIDENCE_THRESHOLD:
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "WEEKLY_MARKET_ANALYSIS_MEETING",
            "reason": f"emily technical_confidence={emily_confidence} >= {EMILY_HIGH_CONFIDENCE_THRESHOLD} — debate simplified",
            "date": current_date,
        }]
        debate_resolution = {
            "status": "simplified",
            "reason": "high_confidence_no_debate_needed",
            "emily_confidence": emily_confidence,
        }
    else:
        # 실제는 MarketAnalysisMeeting(state).run() 호출
        debate_resolution = {
            "status": "full_debate",
            "emily_confidence": emily_confidence,
        }

    updated["weekly_market_report"] = {
        "date": current_date,
        "market_regime": (state.get("emily_output") or {}).get("market_regime", "mixed"),
        "debate_resolution": debate_resolution,
    }
    updated["debate_resolution"] = debate_resolution
    updated["next_node"] = "WEEKLY_STRATEGY_DEVELOPMENT_MEETING"
    return updated
