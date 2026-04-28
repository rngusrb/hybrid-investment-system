"""integration/emily_context.py — Emily SPY 레짐 분석 + Portfolio Manager 컨텍스트 포맷.

Pipeline B/C용 어댑터: EmilyAgent를 run_loop에서 직접 실행하고
결과를 Portfolio Manager user 메시지에 주입할 문자열로 변환.

orchestrator.py의 LangGraph 노드는 건드리지 않음 (Pipeline A 독립 실행 보존).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.emily import EmilyAgent

_EMILY_CONFIG = {
    "name": "Emily",
    "system_prompt_path": "prompts/emily_system.md",
    "temperature": 0.2,
    "max_tokens": 4096,
    "max_retries": 3,
    "agent_confidence_floor": 0.45,
}

# SPY 입력 최대 bars 수 (컨텍스트 절약)
_MAX_BARS = 60
_MAX_ARTICLES = 20


def run_emily_for_context(llm, spy_data: dict, date: str) -> tuple[dict, str]:
    """
    Emily 에이전트 실행 후 (emily_output_dict, prompt_context_str) 반환.

    Args:
        llm: LLM provider (analyst tier 사용)
        spy_data: fetch_data("SPY", date) 결과. bars, articles 포함.
        date: 실행 날짜 (YYYY-MM-DD)

    Returns:
        (emily_output_dict, formatted_context_str)
        실패 시 ({}, "") — 호출자가 graceful fallback 처리.
    """
    agent = EmilyAgent(llm=llm, config=_EMILY_CONFIG)

    # Emily는 SPY bars + articles만 받음. 개별 종목 데이터 포함 금지.
    input_packet = {
        "ticker": "SPY",
        "date": date,
        "bars": spy_data.get("bars", [])[-_MAX_BARS:],
        "articles": spy_data.get("articles", [])[:_MAX_ARTICLES],
        "current_price": spy_data.get("current_price"),
    }

    emily_output = agent.run(input_packet, state={"current_date": date})
    context_str = format_emily_for_prompt(emily_output)
    return emily_output, context_str


def format_emily_for_prompt(emily_output: dict) -> str:
    """
    Portfolio Manager user 메시지에 주입할 텍스트 블록 반환.

    형식:
      === MARKET CONTEXT (Emily — SPY Macro Analysis) ===
      Regime: risk_on (confidence=0.82)
      Market Bias: selective_long
      Technical: up-trend (conf=0.77  reversal_risk=0.21)
      Macro: rates=+0.30  growth=+0.40  liquidity=+0.20  sentiment=+0.10
      Bull catalysts: [...]
      Bear catalysts: [...]
      Sector preference: semiconductor, tech
      Avoid sectors: utilities
      Risk flags: [...]

    빈 dict 입력 시 빈 문자열 반환 (caller에서 if emily_context: 분기 가능).
    """
    if not emily_output:
        return ""

    ts = emily_output.get("technical_signal_state") or {}
    ms = emily_output.get("macro_state") or {}
    sp = emily_output.get("sector_preference") or []

    preferred = [s["sector"] for s in sp if isinstance(s, dict) and s.get("score", 0) >= 0.6]
    avoid = [s["sector"] for s in sp if isinstance(s, dict) and s.get("score", 0) < 0.4]

    bull = emily_output.get("bull_catalysts") or []
    bear = emily_output.get("bear_catalysts") or []

    lines = [
        "=== MARKET CONTEXT (Emily — SPY Macro Analysis) ===",
        (
            f"Regime: {emily_output.get('market_regime', 'unknown')}  "
            f"(confidence={emily_output.get('regime_confidence', 0):.2f})"
        ),
        f"Market Bias: {emily_output.get('recommended_market_bias', 'neutral')}",
        (
            f"Technical: {ts.get('trend_direction', '?')}-trend  "
            f"(conf={ts.get('technical_confidence', 0):.2f}  "
            f"reversal_risk={ts.get('reversal_risk', 0):.2f})"
        ),
        (
            f"Macro: rates={ms.get('rates', 0):+.2f}  "
            f"growth={ms.get('growth', 0):+.2f}  "
            f"liquidity={ms.get('liquidity', 0):+.2f}  "
            f"sentiment={ms.get('risk_sentiment', 0):+.2f}"
        ),
    ]

    if bull:
        lines.append(f"Bull catalysts: {bull[:3]}")
    if bear:
        lines.append(f"Bear catalysts: {bear[:3]}")
    if preferred:
        lines.append(f"Sector preference: {', '.join(preferred[:5])}")
    if avoid:
        lines.append(f"Avoid sectors: {', '.join(avoid[:3])}")

    risk_flags = emily_output.get("risk_flags") or []
    if risk_flags:
        lines.append(f"Risk flags: {risk_flags[:3]}")

    return "\n".join(lines)
