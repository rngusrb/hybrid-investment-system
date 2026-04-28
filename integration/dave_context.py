"""integration/dave_context.py — Dave 포트폴리오 레벨 리스크 평가.

Pipeline B/C용 어댑터: Portfolio Manager 출력 + 종목 분석 결과를
Dave 에이전트 입력으로 변환하고 실행.

실행 순서: Portfolio Manager 완료 이후에만 호출 가능.
portfolio가 비어있으면 ({}, "") graceful skip.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.dave import DaveAgent

_DAVE_CONFIG = {
    "name": "Dave",
    "system_prompt_path": "prompts/dave_system.md",
    "temperature": 0.2,
    "max_tokens": 4096,
    "max_retries": 3,
}

# risk_level → volatility proxy 매핑
_RISK_LEVEL_VOL = {"low": 0.2, "medium": 0.4, "high": 0.7, "critical": 0.9}


def build_dave_input(portfolio: dict, stock_results: list, date: str) -> dict:
    """
    Portfolio Manager 출력 + 종목 분석 결과로 Dave 입력 패킷 구성.

    포트폴리오 레벨 risk_components 사전 계산 (Dave _validate_output이
    컴포넌트 가중합으로 risk_score를 강제 덮어씀 — DEV_GUIDE.md 전역 금지사항 2번):
      - beta:                technical_score 기반 proxy (0.5~1.5 → [0,1] 정규화)
      - illiquidity:         hedge_pct / (total_equity + hedge_pct)
      - sector_concentration: HHI (Herfindahl-Hirschman Index)
      - volatility:          risk_level 기반 proxy 가중평균

    raw market data(bars, articles)는 포함하지 않음.
    """
    allocations = portfolio.get("allocations") or []

    weight_map: dict[str, float] = {}
    for a in allocations:
        t = a.get("ticker", "")
        w = a.get("weight", 0.0)
        if t:
            try:
                weight_map[t] = float(w)
            except (TypeError, ValueError):
                weight_map[t] = 0.0

    total_equity = float(portfolio.get("total_equity_pct") or sum(weight_map.values()) or 0.0)
    stock_map = {r["ticker"]: r for r in stock_results}

    weighted_beta = 0.0
    weighted_vol = 0.0
    sector_weights: dict[str, float] = {}

    for ticker, weight in weight_map.items():
        r = stock_map.get(ticker, {})
        tech = r.get("technical") or {}

        # technical_score [0,1] → beta proxy [0.5, 1.5] → 정규화 [0, 1]
        tech_score = float(tech.get("technical_score") or 0.5)
        beta_proxy = 0.5 + min(max(tech_score, 0.0), 1.0)
        beta_norm = min(max((beta_proxy - 0.5) / 1.0, 0.0), 1.0)
        weighted_beta += weight * beta_norm

        # volatility: risk_manager risk_level 기반
        risk_level = (r.get("risk_manager") or {}).get("risk_level", "medium")
        vol_proxy = _RISK_LEVEL_VOL.get(risk_level, 0.4)
        weighted_vol += weight * vol_proxy

        # sector: fundamental에서 추출
        sector = (r.get("fundamental") or {}).get("sector", "unknown")
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    # HHI: Σ(normalized_weight_i^2)
    total_w = sum(weight_map.values()) or 1.0
    hhi = sum((w / total_w) ** 2 for w in sector_weights.values())

    # illiquidity: hedge 비율 (헤지가 많을수록 유동성 제약)
    hedge_pct = float(portfolio.get("hedge_pct") or 0.0)
    illiquidity = hedge_pct / (total_equity + hedge_pct + 1e-8)
    illiquidity = min(max(illiquidity, 0.0), 1.0)

    return {
        "date": date,
        "portfolio_summary": {
            "total_equity_pct": round(total_equity, 4),
            "cash_pct": round(float(portfolio.get("cash_pct") or 0.0), 4),
            "hedge_pct": round(hedge_pct, 4),
            "n_positions": len(weight_map),
            "portfolio_risk_level": portfolio.get("portfolio_risk_level", "medium"),
            "rebalance_urgency": round(float(portfolio.get("rebalance_urgency") or 0.5), 4),
        },
        "allocations": [
            {
                "ticker": a.get("ticker"),
                "weight": a.get("weight"),
                "action": a.get("action"),
            }
            for a in allocations
        ],
        "pre_computed_risk_components": {
            "beta": round(min(weighted_beta, 1.0), 4),
            "illiquidity": round(illiquidity, 4),
            "sector_concentration": round(hhi, 4),
            "volatility": round(min(weighted_vol, 1.0), 4),
        },
        "sector_breakdown": {k: round(v, 4) for k, v in sector_weights.items()},
    }


def run_dave_for_portfolio(
    llm_decision,
    portfolio: dict,
    stock_results: list,
    date: str,
) -> tuple[dict, str]:
    """
    Dave 포트폴리오 리스크 평가 실행.

    Args:
        llm_decision: LLM provider (decision tier)
        portfolio: run_portfolio_manager() 출력
        stock_results: run_single_stock() 결과 리스트
        date: 실행 날짜 (YYYY-MM-DD)

    Returns:
        (dave_output_dict, formatted_context_str)
        portfolio가 비어있으면 ({}, "") graceful skip.
    """
    if not portfolio or not portfolio.get("allocations"):
        return {}, ""

    agent = DaveAgent(llm=llm_decision, config=_DAVE_CONFIG)
    input_packet = build_dave_input(portfolio, stock_results, date)
    dave_output = agent.run(input_packet, state={"current_date": date})
    context_str = format_dave_for_prompt(dave_output)
    return dave_output, context_str


def format_dave_for_prompt(dave_output: dict) -> str:
    """
    Portfolio Manager user 메시지에 주입할 Dave 리스크 요약.

    형식:
      === PORTFOLIO RISK (Dave — Portfolio Risk Assessment) ===
      Risk Score: 0.42  Level: medium
      Components: beta=0.35  illiquidity=0.12  sector_conc=0.28  vol=0.31
      Stress Test: worst_case=-14.2%  severity=0.45
      Controls: [...]
      ⚠️ Risk Alert: ... (risk_score > 0.75일 때만)
    """
    if not dave_output:
        return ""

    comp = dave_output.get("risk_components") or {}
    stress = dave_output.get("stress_test") or {}
    controls = dave_output.get("recommended_controls") or []

    lines = [
        "=== PORTFOLIO RISK (Dave — Portfolio Risk Assessment) ===",
        (
            f"Risk Score: {dave_output.get('risk_score', 0):.2f}  "
            f"Level: {dave_output.get('risk_level', '?')}"
        ),
        (
            f"Components: beta={comp.get('beta', 0):.2f}  "
            f"illiquidity={comp.get('illiquidity', 0):.2f}  "
            f"sector_conc={comp.get('sector_concentration', 0):.2f}  "
            f"vol={comp.get('volatility', 0):.2f}"
        ),
        (
            f"Stress Test: worst_case={stress.get('worst_case_drawdown', 0)*100:.1f}%  "
            f"severity={stress.get('severity_score', 0):.2f}"
        ),
    ]

    if controls:
        lines.append(f"Controls: {controls[:3]}")
    if dave_output.get("trigger_risk_alert_meeting"):
        lines.append("⚠️ Risk Alert: Portfolio risk exceeds threshold (0.75)")

    return "\n".join(lines)
