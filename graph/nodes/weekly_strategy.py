"""WEEKLY_STRATEGY_DEVELOPMENT_MEETING node."""
import yaml
from graph.state import SystemState
from schemas.audit_schema import NodeResult
from simulation.trading_engine import SimulatedTradingEngine


def _make_trading_engine() -> SimulatedTradingEngine:
    """config의 polygon_api_key로 PolygonFetcher 주입. 키 없으면 synthetic fallback."""
    try:
        with open("config/system_config.yaml") as f:
            cfg = yaml.safe_load(f)
        api_key = cfg.get("data", {}).get("polygon_api_key")
        if api_key:
            from data.polygon_fetcher import PolygonFetcher
            return SimulatedTradingEngine(fetcher=PolygonFetcher(api_key=api_key))
    except Exception:
        pass
    return SimulatedTradingEngine()


# module-level 인스턴스
_trading_engine = _make_trading_engine()


def _enrich_bob_output_with_sim_metrics(bob_output: dict) -> dict:
    """bob_output의 sim_metrics를 실제 백테스트 결과로 교체."""
    if not bob_output:
        return bob_output
    candidates = bob_output.get("candidate_strategies", [])
    enriched = []
    for c in candidates:
        try:
            real_metrics = _trading_engine.run_strategy(
                strategy_type=c.get("type", "momentum"),
                sim_window=c.get("sim_window", {}),
                regime_fit=float(c.get("regime_fit", 0.5)),
                technical_alignment=float(c.get("technical_alignment", 0.5)),
            )
            if real_metrics is not None:
                c = dict(c)
                c["sim_metrics"] = real_metrics
        except Exception:
            pass
        enriched.append(c)
    result = dict(bob_output)
    result["candidate_strategies"] = enriched
    return result


def weekly_strategy_development_meeting(state: SystemState) -> SystemState:
    """
    주간 전략 개발 meeting 실행.
    signal_conflict_resolution: technical/macro 방향 일치 시 스킵 가능.
    실제 구현에서는 StrategyDevelopmentMeeting 호출.
    """
    updated = dict(state)

    emily_output = state.get("emily_output") or {}
    bob_output = state.get("bob_output") or {}
    current_date = state.get("current_date")

    if bob_output:
        bob_output = _enrich_bob_output_with_sim_metrics(bob_output)
        updated["bob_output"] = bob_output

    # technical/macro 방향 일치 여부 확인 → 일치하면 signal_conflict_resolution 스킵
    emily_direction = emily_output.get("direction", "neutral")
    bob_direction = bob_output.get("macro_direction", "neutral")
    directions_aligned = (emily_direction == bob_direction) and emily_direction != "neutral"

    if directions_aligned:
        signal_conflict_resolution = {
            "status": "skipped",
            "reason": f"technical={emily_direction} and macro={bob_direction} aligned — no conflict resolution needed",
        }
        updated["skip_log"] = list(state.get("skip_log", [])) + [{
            "node": "WEEKLY_STRATEGY_DEVELOPMENT_MEETING",
            "reason": f"signal directions aligned ({emily_direction}) — conflict resolution skipped",
            "date": current_date,
        }]
    else:
        # 실제는 StrategyDevelopmentMeeting(state).run() 호출
        signal_conflict_resolution = {
            "status": "resolved",
            "technical_direction": emily_direction,
            "macro_direction": bob_direction,
        }

    updated["signal_conflict_resolution"] = signal_conflict_resolution
    updated["weekly_strategy_set"] = {
        "date": current_date,
        "signal_conflict_resolution": signal_conflict_resolution,
        "strategy_action": bob_output.get("recommended_action", "hold"),
    }
    updated["next_node"] = "WEEKLY_PROPAGATION_AUDIT"
    return updated
