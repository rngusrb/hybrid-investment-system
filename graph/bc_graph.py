"""
graph/bc_graph.py — B/C 파이프라인 LangGraph 상태 기계.

기존 Pipeline A 그래프(graph/builder.py)와 완전히 분리.
run_loop.py의 run_one_cycle() 함수 순차 호출을 이 그래프로 교체.

흐름:
  EMILY → STOCK_ANALYSIS → BACKTESTER → MEETINGS → CALIBRATION
  → RELIABILITY_UPDATE → PORTFOLIO_MANAGER → DAVE
  → [route_after_dave]
      risk > 0.7 (첫 번째만) → BACKTESTER(defensive) → PORTFOLIO_MANAGER → DAVE
      else                    → OTTO
  → [route_after_otto]
      rejected + retry_count <= 2 → PORTFOLIO_MANAGER (otto_retry_count++)
      else                  → END
"""
from langgraph.graph import StateGraph, END

from graph.bc_state import SystemStateBC
from graph.nodes.bc_emily      import bc_emily_node
from graph.nodes.bc_stock      import bc_stock_node
from graph.nodes.bc_backtester import bc_backtester_node
from graph.nodes.bc_meetings   import bc_meetings_node
from graph.nodes.bc_calibration        import bc_calibration_node
from graph.nodes.bc_reliability_update import bc_reliability_update_node
from graph.nodes.bc_portfolio          import bc_portfolio_node
from graph.nodes.bc_dave       import bc_dave_node
from graph.nodes.bc_otto       import bc_otto_node


# ─── Conditional edge 함수 ───────────────────────────────────────────────────

def route_after_backtester(state: SystemStateBC) -> str:
    """
    Backtester 이후 분기.
    - dave_rerun_triggered=True  : Dave 재실행 경로 → PORTFOLIO_MANAGER (Meetings/Cal 스킵)
    - dave_rerun_triggered=False : 정상 경로 → MEETINGS
    """
    if state.get("dave_rerun_triggered", False):
        return "BC_PORTFOLIO_MANAGER"
    return "BC_MEETINGS"


def route_after_dave(state: SystemStateBC) -> str:
    """
    Dave 이후 분기.
    - risk_score > 0.7 AND 아직 rerun 안 했음 → BACKTESTER (defensive 모드)
    - else → OTTO
    """
    dave        = state.get("dave_output") or {}
    risk_score  = float(dave.get("risk_score", 0))
    already_rerun = state.get("dave_rerun_triggered", False)

    if risk_score > 0.7 and not already_rerun:
        return "BC_BACKTESTER_DEFENSIVE"
    return "BC_OTTO"


def route_after_otto(state: SystemStateBC) -> str:
    """
    Otto 이후 분기.
    - rejected AND retry_count <= 2 → PORTFOLIO_MANAGER (재실행)
    - else → END
    """
    otto        = state.get("otto_output") or {}
    retry_count = state.get("otto_retry_count", 0)

    if otto.get("approval_status") == "rejected" and retry_count <= 2:
        return "BC_PORTFOLIO_MANAGER"
    return END


# ─── Defensive Backtester 래퍼 ───────────────────────────────────────────────

def bc_backtester_defensive_node(state: dict) -> dict:
    """
    Dave risk > 0.7 트리거 시 실행되는 defensive 모드 Backtester.
    state에 risk_mode="defensive", dave_rerun_triggered=True 세트 후 bc_backtester_node 호출.
    """
    patched = dict(state)
    patched["risk_mode"] = "defensive"
    result = bc_backtester_node(patched)
    result["risk_mode"]            = "defensive"
    result["dave_rerun_triggered"] = True
    return result


# ─── 그래프 조립 ─────────────────────────────────────────────────────────────

def build_bc_graph() -> StateGraph:
    """B/C 파이프라인 LangGraph 조립."""
    graph = StateGraph(SystemStateBC)

    # 노드 등록
    graph.add_node("BC_EMILY",              bc_emily_node)
    graph.add_node("BC_STOCK_ANALYSIS",     bc_stock_node)
    graph.add_node("BC_BACKTESTER",         bc_backtester_node)
    graph.add_node("BC_BACKTESTER_DEFENSIVE", bc_backtester_defensive_node)
    graph.add_node("BC_MEETINGS",           bc_meetings_node)
    graph.add_node("BC_CALIBRATION",         bc_calibration_node)
    graph.add_node("BC_RELIABILITY_UPDATE",  bc_reliability_update_node)
    graph.add_node("BC_PORTFOLIO_MANAGER",   bc_portfolio_node)
    graph.add_node("BC_DAVE",               bc_dave_node)
    graph.add_node("BC_OTTO",               bc_otto_node)

    # 시작 노드
    graph.set_entry_point("BC_EMILY")

    # 정방향 엣지 (무조건)
    graph.add_edge("BC_EMILY",          "BC_STOCK_ANALYSIS")
    graph.add_edge("BC_STOCK_ANALYSIS", "BC_BACKTESTER")

    # Backtester 이후 분기: 정상 → Meetings, dave_rerun → Portfolio 직행
    graph.add_conditional_edges(
        "BC_BACKTESTER",
        route_after_backtester,
        {
            "BC_MEETINGS":           "BC_MEETINGS",
            "BC_PORTFOLIO_MANAGER":  "BC_PORTFOLIO_MANAGER",
        },
    )

    graph.add_edge("BC_MEETINGS",           "BC_CALIBRATION")
    graph.add_edge("BC_CALIBRATION",        "BC_RELIABILITY_UPDATE")
    graph.add_edge("BC_RELIABILITY_UPDATE", "BC_PORTFOLIO_MANAGER")
    graph.add_edge("BC_PORTFOLIO_MANAGER", "BC_DAVE")

    # Dave 이후 분기: risk > 0.7 → Defensive Backtester, else → Otto
    graph.add_conditional_edges(
        "BC_DAVE",
        route_after_dave,
        {
            "BC_BACKTESTER_DEFENSIVE": "BC_BACKTESTER_DEFENSIVE",
            "BC_OTTO":                 "BC_OTTO",
        },
    )

    # Defensive Backtester → Portfolio (Meetings/Cal 스킵)
    graph.add_edge("BC_BACKTESTER_DEFENSIVE", "BC_PORTFOLIO_MANAGER")

    # Otto 이후 분기: rejected → Portfolio 재실행, else → END
    graph.add_conditional_edges(
        "BC_OTTO",
        route_after_otto,
        {
            "BC_PORTFOLIO_MANAGER": "BC_PORTFOLIO_MANAGER",
            END:                    END,
        },
    )

    return graph


def compile_bc_graph():
    """B/C 그래프 컴파일 및 반환."""
    return build_bc_graph().compile()
