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

import json
import re
import logging

logger = logging.getLogger(__name__)

RISK_ALERT_THRESHOLD = 0.75   # risk_score > 0.75 → RAM 트리거
DEBATE_SKIP_CONFIDENCE = 0.80  # consensus ≥ 0.80 → debate 간소화

# risk_level 문자열 → 수치
_RISK_LEVEL_SCORES = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.75,
    "critical": 0.95,
}


# ─── LLM 토론 헬퍼 ───────────────────────────────────────────────────────────

def _build_debate_signals(stock_results: list[dict], tickers: list[str]) -> list[dict]:
    """특정 ticker 목록에 해당하는 신호 요약 생성 (토론 입력용)."""
    signals = []
    for r in stock_results:
        if r.get("ticker") not in tickers:
            continue
        rm = r.get("risk_manager") or {}
        te = r.get("technical") or {}
        fu = r.get("fundamental") or {}
        re_ = r.get("researcher") or {}
        signals.append({
            "ticker":     r.get("ticker"),
            "action":     rm.get("final_action", "HOLD"),
            "risk_level": rm.get("risk_level", "medium"),
            "consensus":  re_.get("consensus", "neutral"),
            "conviction": re_.get("conviction", "medium"),
            "tech_score": te.get("technical_score", 5),
            "fund_score": fu.get("fundamental_score", 5),
            "risk_flags": rm.get("risk_flags") or [],
        })
    return signals


def _run_llm_debate(llm, bull_signals: list[dict], bear_signals: list[dict],
                    conflicts: list[dict], date: str) -> dict:
    """
    LLM Bull/Bear 토론 실행.

    debate_skipped=False(consensus < 0.80)일 때만 호출됨.
    실패 시 {} 반환 → 호출자가 heuristic _parse_mam_resolution()으로 fallback.
    """
    bull_text = "\n".join(
        f"  {s['ticker']}: action={s['action']} "
        f"tech={s['tech_score']} fund={s['fund_score']} conviction={s['conviction']}"
        for s in bull_signals
    ) or "  (없음)"
    bear_text = "\n".join(
        f"  {s['ticker']}: action={s['action']} "
        f"tech={s['tech_score']} fund={s['fund_score']} risk_flags={s['risk_flags']}"
        for s in bear_signals
    ) or "  (없음)"
    conflicts_text = "\n".join(
        f"  [{c['ticker']}] {c['conflict']}"
        for c in conflicts[:3]
    ) or "  (없음)"

    user = f"""Date: {date}

Bull 측 신호:
{bull_text}

Bear 측 신호:
{bear_text}

신호 충돌:
{conflicts_text}

위 신호를 분석하여 시장 토론 결과를 JSON으로 반환하라:
{{
  "consensus": "bullish" | "bearish" | "neutral" | "split",
  "key_risks": ["리스크1", "리스크2"],
  "recommended_bias": "risk_on" | "risk_off" | "neutral",
  "confidence": 0.0~1.0,
  "debate_summary": "한 문장 요약"
}}
JSON만 반환."""

    system = (
        "당신은 투자 전략 회의의 중재자입니다. "
        "Bull 측과 Bear 측 논거를 분석하여 합리적인 토론 결론을 내립니다."
    )

    try:
        raw = llm.chat(
            messages=[{"role": "user", "content": user}],
            system=system,
        )
        text = raw if isinstance(raw, str) else str(raw)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.warning(f"_run_llm_debate JSON 없음 (date={date}): {text[:80]!r}")
            return {}
        data = json.loads(match.group())
        if "consensus" not in data or "recommended_bias" not in data:
            logger.warning(f"_run_llm_debate 필수 필드 누락: {list(data.keys())}")
            return {}
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        return data
    except Exception as e:
        logger.warning(f"_run_llm_debate 실패: {e}", exc_info=True)
        return {}


# ─── MAM Resolution Parser ───────────────────────────────────────────────────

def _parse_mam_resolution(market_regime: str, market_bias: str,
                          conflicts: list[dict], consensus_score: float,
                          date: str) -> dict:
    """
    MAM 결과를 구조화된 DebateResolution dict로 변환.
    LLM 추가 호출 없이 기존 MAM 출력값으로부터 파싱.
    실패 시 {} 반환.
    """
    try:
        # consensus: regime 기반 매핑
        if market_regime == "risk_on":
            consensus = "bullish"
        elif market_regime == "risk_off":
            consensus = "bearish"
        elif market_regime == "mixed" and consensus_score < 0.5:
            consensus = "split"
        else:
            consensus = "neutral"

        # key_risks: conflict resolution 텍스트에서 추출 (최대 3개)
        key_risks: list[str] = []
        for c in conflicts[:3]:
            key_risks.append(f"[{c.get('ticker', '?')}] {c.get('conflict', '')}")

        # recommended_bias: consensus 기반
        if consensus == "bullish":
            recommended_bias = "risk_on"
        elif consensus == "bearish":
            recommended_bias = "risk_off"
        else:
            recommended_bias = "neutral"

        # confidence: consensus_score 그대로 사용 (0.0~1.0)
        confidence = max(0.0, min(1.0, consensus_score))

        return {
            "meeting_type": "MAM",
            "date": date,
            "consensus": consensus,
            "key_risks": key_risks,
            "recommended_bias": recommended_bias,
            "confidence": round(confidence, 4),
        }
    except Exception:
        logger.warning("_parse_mam_resolution failed, returning empty dict", exc_info=True)
        return {}


# ─── MAM ────────────────────────────────────────────────────────────────────

def run_mam(stock_results: list[dict], sim_results: dict, run_date: str,
            r_real: float | None = None, llm=None) -> dict:
    """
    Market Analysis Meeting — B/C pipeline 출력 기반 시장 분석.

    r_real: 이전 주기 실제 포트폴리오 수익률 (Polygon T+7 확정). 있으면 시장 평가에 반영.
    llm:    LLM provider. None이면 heuristic resolution만 사용 (하위 호환).
            debate_skipped=False(consensus < 0.80)일 때만 LLM 토론 실행.

    반환:
        {
          date, market_regime, market_bias,
          bull_tickers, bear_tickers, neutral_tickers,
          signal_conflicts: [{ticker, conflict, resolution}, ...],
          debate_skipped, consensus_score, llm_debate_used,
          prior_r_real, prior_performance,
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

    # r_real 기반 이전 성과 분류
    prior_performance: str | None = None
    if r_real is not None:
        if r_real >= 0.02:
            prior_performance = "prior_gain"       # +2% 이상 — 이전 전략 효과적
        elif r_real < 0:
            prior_performance = "prior_loss"       # 손실 — 이전 전략 재검토 필요
        else:
            prior_performance = "prior_neutral"    # 소폭 양성

    # LLM 토론: debate_skipped=False AND llm 있을 때만
    llm_debate_used = False
    if not debate_skipped and llm is not None:
        bull_signals = _build_debate_signals(stock_results, bull_tickers)
        bear_signals = _build_debate_signals(stock_results, bear_tickers)
        llm_result = _run_llm_debate(llm, bull_signals, bear_signals, conflicts, run_date)
        if llm_result:
            resolution = {
                "meeting_type":    "MAM",
                "date":            run_date,
                "consensus":       llm_result.get("consensus", "neutral"),
                "key_risks":       llm_result.get("key_risks", []),
                "recommended_bias": llm_result.get("recommended_bias", "neutral"),
                "confidence":      llm_result.get("confidence", consensus_score),
                "debate_summary":  llm_result.get("debate_summary", ""),
                "llm_debate":      True,
            }
            llm_debate_used = True
        else:
            # LLM 실패 → heuristic fallback
            resolution = _parse_mam_resolution(
                market_regime, market_bias, conflicts, consensus_score, run_date,
            )
    else:
        resolution = _parse_mam_resolution(
            market_regime, market_bias, conflicts, consensus_score, run_date,
        )

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
        "llm_debate_used": llm_debate_used,
        "resolution": resolution,
        "prior_r_real": r_real,
        "prior_performance": prior_performance,
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
    r_real: float | None = None,
    llm=None,
) -> dict:
    """
    MAM → SDM → RAM (조건부) 순서로 실행.

    r_real: 이전 주기 실제 수익률. MAM에 주입하여 시장 평가에 반영.
    llm:    LLM provider. None이면 heuristic만 사용 (하위 호환).

    반환:
        { mam: {...}, sdm: {...}, ram: {...}, ram_triggered: bool }
    """
    mam = run_mam(stock_results, sim_results, run_date, r_real=r_real, llm=llm)
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
    prior_r_real = mam.get("prior_r_real")
    prior_perf = mam.get("prior_performance")
    if prior_r_real is not None:
        sign = "+" if prior_r_real >= 0 else ""
        perf_label = {
            "prior_gain":    "✅ 이전 전략 효과적 — 같은 방향 유지 고려",
            "prior_loss":    "⚠️  이전 전략 손실 — 배분 축소 고려",
            "prior_neutral": "→ 이전 전략 소폭 양성 — 현상 유지",
        }.get(prior_perf, "")
        lines.append(f"  이전 주기 실제수익률: {sign}{prior_r_real*100:.1f}%  {perf_label}")
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
