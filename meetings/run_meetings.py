"""
meetings/run_meetings.py — Pipeline B/C용 MAM/SDM/RAM 어댑터

run_loop.py의 run_one_cycle 내에서 stock_results(B/C 파이프라인)와
sim_results(backtester)를 받아 3개 미팅 실행.

흐름:
  stock_results + sim_results
  → MAM (시장 분석: Bull/Bear 집계, 시그널 충돌 감지)
  → SDM (전략 개발: 전략 Pool 필터링, 실행 힌트)
  → RAM (리스크 알럿: risk_level 기준 조건부 트리거)
  → format_meetings_for_prompt() → Portfolio Manager 주입

기존 meetings/{market_analysis,strategy_development,risk_alert}.py는
Pipeline A(LangGraph SystemState)용이므로 여기서는 재사용하지 않음.
B/C 파이프라인의 출력(stock_results/sim_results)을 직접 처리.
"""

RISK_ALERT_THRESHOLD = 0.75   # risk_score > 0.75 → RAM 트리거
DEBATE_SKIP_CONFIDENCE = 0.80  # consensus ≥ 0.80 → debate 간소화

# risk_level 문자열 → 수치
_RISK_LEVEL_SCORES = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.75,
    "critical": 0.95,
}


# ─── MAM ────────────────────────────────────────────────────────────────────

def run_mam(stock_results: list[dict], sim_results: dict, run_date: str) -> dict:
    """
    Market Analysis Meeting — B/C pipeline 출력 기반 시장 분석.

    반환:
        {
          date, market_regime, market_bias,
          bull_tickers, bear_tickers, neutral_tickers,
          signal_conflicts: [{ticker, conflict, resolution}, ...],
          debate_skipped, consensus_score,
        }
    """
    bull_tickers: list[str] = []
    bear_tickers: list[str] = []
    neutral_tickers: list[str] = []
    conflicts: list[dict] = []

    for r in stock_results:
        ticker = r.get("ticker", "?")
        trader = r.get("trader") or {}
        rm = r.get("risk_manager") or {}
        tech = r.get("technical") or {}
        fundamental = r.get("fundamental") or {}
        researcher = r.get("researcher") or {}

        final_action = rm.get("final_action") or trader.get("action") or "HOLD"
        consensus = researcher.get("consensus", "neutral")

        if final_action == "BUY" or consensus == "bullish":
            bull_tickers.append(ticker)
        elif final_action == "SELL" or consensus == "bearish":
            bear_tickers.append(ticker)
        else:
            neutral_tickers.append(ticker)

        # 충돌 1: trader → risk_manager 액션 변경
        if rm.get("action_changed"):
            conflicts.append({
                "ticker": ticker,
                "conflict": (
                    f"trader={trader.get('action')} → "
                    f"rm={rm.get('final_action')}"
                ),
                "resolution": "risk_manager override applied",
            })

        # 충돌 2: 기술적 강세 + 펀더멘털 약세
        tech_score = tech.get("technical_score", 5)
        fund_score = fundamental.get("fundamental_score", 5)
        if isinstance(tech_score, (int, float)) and isinstance(fund_score, (int, float)):
            if tech_score >= 7 and fund_score <= 3:
                conflicts.append({
                    "ticker": ticker,
                    "conflict": (
                        f"tech_strong({tech_score}) vs fund_weak({fund_score})"
                    ),
                    "resolution": "reduce position size, validate fundamentals",
                })
            elif tech_score <= 3 and fund_score >= 7:
                conflicts.append({
                    "ticker": ticker,
                    "conflict": (
                        f"tech_weak({tech_score}) vs fund_strong({fund_score})"
                    ),
                    "resolution": "wait for technical confirmation before entry",
                })

    total = max(len(stock_results), 1)
    bull_ratio = len(bull_tickers) / total
    bear_ratio = len(bear_tickers) / total

    if bull_ratio >= 0.6:
        market_regime = "risk_on"
        market_bias = "selective_long"
    elif bear_ratio >= 0.6:
        market_regime = "risk_off"
        market_bias = "defensive"
    else:
        market_regime = "mixed"
        market_bias = "neutral"

    consensus_score = max(bull_ratio, bear_ratio)
    debate_skipped = consensus_score >= DEBATE_SKIP_CONFIDENCE

    return {
        "date": run_date,
        "market_regime": market_regime,
        "market_bias": market_bias,
        "bull_tickers": bull_tickers,
        "bear_tickers": bear_tickers,
        "neutral_tickers": neutral_tickers,
        "signal_conflicts": conflicts,
        "debate_skipped": debate_skipped,
        "consensus_score": round(consensus_score, 4),
    }


# ─── SDM ────────────────────────────────────────────────────────────────────

def run_sdm(stock_results: list[dict], sim_results: dict, run_date: str) -> dict:
    """
    Strategy Development Meeting — Bob 시뮬 결과 기반 실행 힌트.

    반환:
        {
          date, strategy_recommendations: {ticker: {...}},
          dominant_strategy, high_turnover_warnings,
          low_sharpe_warnings, strategy_distribution,
        }
    """
    strategy_recommendations: dict[str, dict] = {}
    high_turnover_warnings: list[str] = []
    low_sharpe_warnings: list[str] = []
    strategy_distribution: dict[str, int] = {}

    for ticker, sim in sim_results.items():
        best = sim.get("best") or {}
        strategy = sim.get("selected_strategy", "defensive")
        sharpe = best.get("sharpe", 0.0)
        turnover = best.get("turnover", 0.0)
        mdd = best.get("mdd", 0.0)

        hints: list[str] = []
        if turnover > 0.5:
            hints.append(f"high_turnover={turnover:.2f} → staggered entry")
            high_turnover_warnings.append(ticker)
        if sharpe < 0.3:
            hints.append(f"low_sharpe={sharpe:.2f} → reduce position size")
            low_sharpe_warnings.append(ticker)
        if mdd > 0.15:
            hints.append(f"high_mdd={mdd:.1%} → add stop-loss")

        strategy_recommendations[ticker] = {
            "selected_strategy": strategy,
            "sharpe": round(sharpe, 4),
            "mdd": round(mdd, 4),
            "execution_hints": hints,
        }
        strategy_distribution[strategy] = strategy_distribution.get(strategy, 0) + 1

    dominant_strategy = (
        max(strategy_distribution, key=lambda k: strategy_distribution[k])
        if strategy_distribution else "defensive"
    )

    return {
        "date": run_date,
        "strategy_recommendations": strategy_recommendations,
        "dominant_strategy": dominant_strategy,
        "high_turnover_warnings": high_turnover_warnings,
        "low_sharpe_warnings": low_sharpe_warnings,
        "strategy_distribution": strategy_distribution,
    }


# ─── RAM ────────────────────────────────────────────────────────────────────

def run_ram(stock_results: list[dict], run_date: str) -> dict:
    """
    Risk Alert Meeting — risk_level 기준 조건부 트리거.
    RAM은 이벤트 기반: max_risk_score > RISK_ALERT_THRESHOLD 일 때만 triggered=True.

    반환:
        {
          date, triggered, avg_risk_score, max_risk_score,
          high_risk_tickers, emergency_controls, all_risk_flags,
        }
    """
    risk_scores: list[float] = []
    high_risk_tickers: list[str] = []
    all_risk_flags: list[str] = []

    for r in stock_results:
        rm = r.get("risk_manager") or {}
        risk_level = rm.get("risk_level", "medium")
        score = _RISK_LEVEL_SCORES.get(risk_level, 0.5)
        risk_scores.append(score)

        flags = rm.get("risk_flags") or []
        if isinstance(flags, list):
            all_risk_flags.extend(flags)

        if score >= RISK_ALERT_THRESHOLD:
            high_risk_tickers.append(r.get("ticker", "?"))

    avg_risk = sum(risk_scores) / max(len(risk_scores), 1)
    max_risk = max(risk_scores) if risk_scores else 0.0
    triggered = max_risk >= RISK_ALERT_THRESHOLD

    emergency_controls: list[str] = []
    if triggered:
        if max_risk > 0.85:
            emergency_controls.extend(
                ["immediate_de_risk", "reduce_gross_exposure_to_50pct"]
            )
        else:
            emergency_controls.append("reduce_directional_exposure")
        if avg_risk > 0.6:
            emergency_controls.append("add_hedge_position")
        if avg_risk > 0.75:
            emergency_controls.append("consider_full_exit")

    return {
        "date": run_date,
        "triggered": triggered,
        "avg_risk_score": round(avg_risk, 4),
        "max_risk_score": round(max_risk, 4),
        "high_risk_tickers": high_risk_tickers,
        "emergency_controls": emergency_controls,
        "all_risk_flags": list(set(all_risk_flags)),
    }


# ─── 오케스트레이터 ───────────────────────────────────────────────────────────

def run_all_meetings(
    stock_results: list[dict],
    sim_results: dict,
    run_date: str,
) -> dict:
    """
    MAM → SDM → RAM (조건부) 순서로 실행.

    반환:
        { mam: {...}, sdm: {...}, ram: {...}, ram_triggered: bool }
    """
    mam = run_mam(stock_results, sim_results, run_date)
    sdm = run_sdm(stock_results, sim_results, run_date)
    ram = run_ram(stock_results, run_date)

    return {
        "mam": mam,
        "sdm": sdm,
        "ram": ram,
        "ram_triggered": ram["triggered"],
    }


# ─── Portfolio Manager 프롬프트 포맷 ─────────────────────────────────────────

def format_meetings_for_prompt(meetings: dict) -> str:
    """
    {mam, sdm, ram} → Portfolio Manager 프롬프트 삽입용 텍스트.
    meetings가 비어있으면 빈 문자열.
    """
    if not meetings:
        return ""

    mam = meetings.get("mam") or {}
    sdm = meetings.get("sdm") or {}
    ram = meetings.get("ram") or {}

    lines = ["=== 3 MEETINGS (MAM/SDM/RAM) ===", ""]

    # MAM
    lines.append("[MAM] Market Analysis Meeting")
    lines.append(
        f"  시장 국면: {mam.get('market_regime', '?')}  |  "
        f"바이어스: {mam.get('market_bias', '?')}"
    )
    lines.append(
        f"  Bull: {mam.get('bull_tickers', [])}  "
        f"Bear: {mam.get('bear_tickers', [])}  "
        f"Neutral: {mam.get('neutral_tickers', [])}"
    )
    conflicts = mam.get("signal_conflicts") or []
    if conflicts:
        lines.append(f"  시그널 충돌 ({len(conflicts)}건):")
        for c in conflicts[:3]:
            lines.append(
                f"    · [{c['ticker']}] {c['conflict']} → {c['resolution']}"
            )
    if mam.get("debate_skipped"):
        lines.append(
            f"  ※ debate 간소화 (consensus={mam.get('consensus_score', 0):.0%})"
        )
    lines.append("")

    # SDM
    lines.append("[SDM] Strategy Development Meeting")
    lines.append(
        f"  지배 전략: {sdm.get('dominant_strategy', '?')}  |  "
        f"분포: {sdm.get('strategy_distribution', {})}"
    )
    recs = sdm.get("strategy_recommendations") or {}
    for ticker, rec in recs.items():
        hints = rec.get("execution_hints") or []
        hint_str = " | ".join(hints) if hints else "정상"
        lines.append(
            f"  [{ticker}] {rec.get('selected_strategy')}  "
            f"Sharpe={rec.get('sharpe', 0):.2f}  힌트: {hint_str}"
        )
    lines.append("")

    # RAM
    lines.append("[RAM] Risk Alert Meeting")
    if ram.get("triggered"):
        lines.append(
            f"  ⚠️  경보 발동! 고위험 종목: {ram.get('high_risk_tickers', [])}"
        )
        lines.append(f"  긴급 조치: {ram.get('emergency_controls', [])}")
    else:
        lines.append(
            f"  정상 (max_risk={ram.get('max_risk_score', 0):.2f})"
        )
    risk_flags = ram.get("all_risk_flags") or []
    if risk_flags:
        lines.append(f"  리스크 플래그: {risk_flags}")
    lines.append("")

    lines.append("=== END 3 MEETINGS ===")
    return "\n".join(lines)
