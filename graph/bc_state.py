"""
graph/bc_state.py — B/C 파이프라인 LangGraph 전용 State 정의.

Pipeline A의 SystemState(graph/state.py)와 완전히 분리.
graph/state.py, graph/builder.py 수정 없음.
"""
from typing import TypedDict, Optional


class SystemStateBC(TypedDict, total=False):
    # ── 실행 컨텍스트 ──────────────────────────────────────────────────────────
    current_date: str
    tickers: list

    # LLM providers (run_loop에서 initial state로 주입)
    _llm_analyst: object
    _llm_decision: object

    # ── 사전 로드 컨텍스트 (graph 진입 전 run_loop에서 준비) ───────────────────
    memory_context: str
    prev_r_real: Optional[float]
    w_real: float
    gating: dict

    # ── 노드별 산출물 ──────────────────────────────────────────────────────────
    emily_output: dict
    emily_context: str

    stock_results: list          # [{ticker, current_price, bars, fundamental, ...}, ...]
    sim_results: dict            # {ticker: backtest_all() 결과}
    sim_context: str
    risk_mode: str               # "normal" | "defensive"  (Dave 트리거로 변경)
    dave_rerun_triggered: bool   # True = Backtester가 이미 defensive 재실행됨

    meetings: dict
    meetings_context: str

    calibration: dict
    calibration_context: str

    otto_feedback: str           # Otto rejected 시 PM에 주입할 거부 이유
    portfolio: dict
    dave_output: dict
    otto_output: dict

    # ── 제어 카운터 ────────────────────────────────────────────────────────────
    otto_retry_count: int        # PM→Dave→Otto 재실행 횟수 (max 2)

    # ── 에러 수집 ──────────────────────────────────────────────────────────────
    errors: list                 # [{"node": str, "error": str}, ...]


def make_initial_bc_state(
    current_date: str,
    tickers: list,
    llm_analyst,
    llm_decision,
    memory_context: str = "",
    prev_r_real: Optional[float] = None,
    w_real: float = 0.5,
    gating: Optional[dict] = None,
) -> SystemStateBC:
    """B/C 그래프 초기 state 생성."""
    return {
        "current_date":       current_date,
        "tickers":            tickers,
        "_llm_analyst":       llm_analyst,
        "_llm_decision":      llm_decision,
        "memory_context":     memory_context,
        "prev_r_real":        prev_r_real,
        "w_real":             w_real,
        "gating":             gating or {},
        "emily_output":       {},
        "emily_context":      "",
        "stock_results":      [],
        "sim_results":        {},
        "sim_context":        "",
        "risk_mode":          "normal",
        "dave_rerun_triggered": False,
        "meetings":           {},
        "meetings_context":   "",
        "calibration":        {},
        "calibration_context": "",
        "otto_feedback":      "",
        "portfolio":          {},
        "dave_output":        {},
        "otto_output":        {},
        "otto_retry_count":   0,
        "errors":             [],
    }
