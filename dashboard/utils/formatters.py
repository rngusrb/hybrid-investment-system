"""dashboard/utils/formatters.py — UI 표시용 순수 변환 함수 (st.* 없음)."""
from typing import Optional


ACTION_ICON = {"BUY": "🟢 BUY", "SELL": "🔴 SELL", "HOLD": "🟡 HOLD"}
RISK_COLOR  = {"low": "🟢", "moderate": "🟡", "high": "🔴", "extreme": "🔴"}


def action_icon(action: str) -> str:
    return ACTION_ICON.get(action, f"⚪ {action}")


def risk_icon(level: str) -> str:
    return RISK_COLOR.get(level, "⚪")


def pct_str(value: float) -> str:
    """0.08 → '8.0%'"""
    return f"{value * 100:.1f}%"


def price_str(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def agent_flow_steps() -> list[dict]:
    """에이전트 실행 순서를 반환 (라벨 + 설명)."""
    return [
        {"id": "data",        "label": "📥 데이터 수집",        "desc": "Polygon: OHLCV + 뉴스 + 재무제표"},
        {"id": "fundamental", "label": "🏦 Fundamental",       "desc": "EPS, PER, 매출 성장률, 내재가치"},
        {"id": "sentiment",   "label": "💬 Sentiment",         "desc": "뉴스 감성 분석, 지배 감정"},
        {"id": "news",        "label": "📰 News",              "desc": "거시경제 영향, 이벤트 리스크"},
        {"id": "technical",   "label": "📈 Technical",         "desc": "RSI, MACD, 볼린저, 지지/저항"},
        {"id": "researcher",  "label": "🔬 Researcher",        "desc": "Bull/Bear 토론 → 합의"},
        {"id": "trader",      "label": "💼 Trader",            "desc": "BUY/SELL/HOLD 초안 결정"},
        {"id": "risk",        "label": "🛡️ Risk Manager",      "desc": "3인 토론 → 포지션 조정"},
        {"id": "portfolio",   "label": "🗂️ Portfolio Manager", "desc": "종목 간 배분 + 현금/헤지"},
    ]


def extract_articles_table(articles: list) -> list[dict]:
    """뉴스 articles 리스트 → 테이블용 dict 리스트."""
    rows = []
    for a in articles:
        rows.append({
            "날짜":   a.get("published_utc", "")[:10],
            "제목":   a.get("title", ""),
            "출처":   a.get("publisher", {}).get("name", "") if isinstance(a.get("publisher"), dict) else "",
            "URL":   a.get("article_url", ""),
        })
    return rows


def extract_ohlcv_table(bars: list) -> list[dict]:
    """bars 리스트 → 차트용 dict 리스트."""
    return [
        {
            "date":   b.get("date", ""),
            "open":   b.get("open"),
            "high":   b.get("high"),
            "low":    b.get("low"),
            "close":  b.get("close"),
            "volume": b.get("volume"),
        }
        for b in bars
    ]


def build_pipeline_trace(result: dict) -> list[dict]:
    """단일 종목 result dict → 파이프라인 단계별 trace 리스트.
    각 항목: {step, label, emoji, input_summary, output_summary, meeting_lines, key_output}
    """
    ticker = result.get("ticker", "?")
    price  = result.get("current_price", 0)
    bars   = result.get("bars", [])
    arts   = result.get("articles", [])
    fins   = result.get("financials", [])
    fund   = result.get("fundamental", {})
    sent   = result.get("sentiment", {})
    news   = result.get("news", {})
    tech   = result.get("technical", {})
    res    = result.get("researcher", {})
    trader = result.get("trader", {})
    rm     = result.get("risk_manager", {})

    trace = []

    # ── Step 0: 데이터 수집 ──────────────────────────────────
    trace.append({
        "step":    0,
        "label":   "데이터 수집",
        "emoji":   "📥",
        "input_summary": f"Polygon API 호출 → {ticker}",
        "output_summary": (
            f"OHLCV {len(bars)}봉 (180일) | "
            f"뉴스 {len(arts)}건 (30일) | "
            f"재무제표 {len(fins)}건"
        ),
        "meeting_lines": [],
        "key_output": {
            "현재가": f"${price:.2f}",
            "OHLCV 봉수": len(bars),
            "뉴스 건수": len(arts),
            "재무 연도": len(fins),
        },
    })

    # ── Step 1: Fundamental Analyst ──────────────────────────
    trace.append({
        "step":    1,
        "label":   "Fundamental Analyst",
        "emoji":   "🏦",
        "input_summary": f"재무제표 {len(fins)}년 + EPS/PE",
        "output_summary": (
            f"Score {fund.get('fundamental_score', '?')} | "
            f"{fund.get('intrinsic_value_signal', '?')} | "
            f"PE {fund.get('pe_ratio', '?')}"
        ),
        "meeting_lines": [
            ("🏦 Fundamental", fund.get("summary", "") or
             f"Score {fund.get('fundamental_score','?')}: "
             f"{', '.join(fund.get('key_strengths', [])[:2])}. "
             f"리스크: {', '.join(fund.get('key_risks', [])[:2])}."),
        ],
        "key_output": {
            "Score": fund.get("fundamental_score"),
            "내재가치": fund.get("intrinsic_value_signal"),
            "PE": fund.get("pe_ratio"),
            "매출성장": fund.get("revenue_growth_yoy"),
        },
    })

    # ── Step 2: Sentiment Analyst ────────────────────────────
    trace.append({
        "step":    2,
        "label":   "Sentiment Analyst",
        "emoji":   "💬",
        "input_summary": f"뉴스 헤드라인 {min(len(arts), 20)}건",
        "output_summary": (
            f"Score {sent.get('sentiment_score', '?')} | "
            f"{sent.get('dominant_emotion', '?')}"
        ),
        "meeting_lines": [
            ("💬 Sentiment", sent.get("summary", "") or
             f"감성 점수 {sent.get('sentiment_score','?')}, "
             f"지배 감정: {sent.get('dominant_emotion','?')}. "
             f"주요 테마: {', '.join(sent.get('key_themes', [])[:3])}."),
        ],
        "key_output": {
            "Score": sent.get("sentiment_score"),
            "감정": sent.get("dominant_emotion"),
            "불확실성": sent.get("uncertainty"),
        },
    })

    # ── Step 3: News Analyst ─────────────────────────────────
    trace.append({
        "step":    3,
        "label":   "News Analyst",
        "emoji":   "📰",
        "input_summary": f"뉴스 기사 {min(len(arts), 15)}건",
        "output_summary": (
            f"Macro {news.get('macro_impact', '?'):+.2f} | "
            f"Event Risk {news.get('event_risk_level', '?')}"
        ) if news.get("macro_impact") is not None else "분석 결과 없음",
        "meeting_lines": [
            ("📰 News", news.get("summary", "") or
             f"거시 영향: {news.get('macro_impact','?')}, "
             f"이벤트 리스크: {news.get('event_risk_level','?')}. "
             f"촉매: {', '.join(news.get('catalyst_signals', [])[:2])}."),
        ],
        "key_output": {
            "Macro Impact": news.get("macro_impact"),
            "Event Risk": news.get("event_risk_level"),
            "이벤트": news.get("company_events", [])[:2],
        },
    })

    # ── Step 4: Technical Analyst ────────────────────────────
    trace.append({
        "step":    4,
        "label":   "Technical Analyst",
        "emoji":   "📈",
        "input_summary": f"OHLCV {len(bars)}봉 + 사전계산 지표",
        "output_summary": (
            f"Score {tech.get('technical_score', '?')} | "
            f"Trend {tech.get('trend_direction', '?')} | "
            f"RSI {tech.get('rsi', '?')} | "
            f"Signal {tech.get('entry_signal', '?')}"
        ),
        "meeting_lines": [
            ("📈 Technical", tech.get("summary", "") or
             f"트렌드 {tech.get('trend_direction','?')}, "
             f"RSI {tech.get('rsi','?')}, MACD {tech.get('macd_signal','?')}. "
             f"신호: {tech.get('entry_signal','?')}. "
             f"지지 ${tech.get('support_level','?')} / 저항 ${tech.get('resistance_level','?')}."),
        ],
        "key_output": {
            "Score": tech.get("technical_score"),
            "Trend": tech.get("trend_direction"),
            "RSI": tech.get("rsi"),
            "Signal": tech.get("entry_signal"),
        },
    })

    # ── Step 5: Researcher (Bull/Bear 토론) ──────────────────
    bull = res.get("bull_thesis", "")
    bear = res.get("bear_thesis", "")
    debate_pts = res.get("key_debate_points", [])
    meeting_lines_res = [("🐂 Bull Analyst", bull)] if bull else []
    meeting_lines_res += [("🐻 Bear Analyst", bear)] if bear else []
    for pt in debate_pts:
        meeting_lines_res.append(("⚡ 논점", pt))
    consensus = res.get("consensus", "?")
    conviction = res.get("conviction", 0)
    meeting_lines_res.append((
        "🔬 Researcher 합의",
        f"**{consensus.upper()}** (확신도 {conviction:.0%}) — {res.get('summary', '')}",
    ))

    trace.append({
        "step":    5,
        "label":   "Researcher 회의 (Bull/Bear 토론)",
        "emoji":   "🔬",
        "input_summary": "Fundamental + Sentiment + News + Technical 4개 보고서",
        "output_summary": (
            f"합의: {consensus} | 확신도 {conviction:.0%} | "
            f"R/R {res.get('risk_reward_ratio', '?')}x"
        ),
        "meeting_lines": meeting_lines_res,
        "key_output": {
            "합의": consensus,
            "확신도": conviction,
            "R/R Ratio": res.get("risk_reward_ratio"),
        },
    })

    # ── Step 6: Trader ───────────────────────────────────────
    t_action = trader.get("action", "?")
    t_pos    = trader.get("position_size_pct", 0)
    reasoning_lines = [("💼 Trader", r) for r in trader.get("reasoning", [])]
    reasoning_lines.append((
        "💼 결정",
        f"**{t_action}** | 확신도 {trader.get('confidence',0):.0%} | "
        f"포지션 {pct_str(t_pos)} | "
        f"목표 ${trader.get('target_price','?')} / 손절 ${trader.get('stop_loss_price','?')}",
    ))

    trace.append({
        "step":    6,
        "label":   "Trader 초안 결정",
        "emoji":   "💼",
        "input_summary": "Researcher 합의 + 4개 Analyst 점수",
        "output_summary": (
            f"{t_action} | 확신도 {trader.get('confidence',0):.0%} | "
            f"포지션 {pct_str(t_pos)}"
        ),
        "meeting_lines": reasoning_lines,
        "key_output": {
            "Action": t_action,
            "확신도": trader.get("confidence"),
            "포지션": t_pos,
            "목표가": trader.get("target_price"),
            "손절가": trader.get("stop_loss_price"),
        },
    })

    # ── Step 7: Risk Manager (3인 토론) ──────────────────────
    f_action = rm.get("final_action", "?")
    changed  = rm.get("action_changed", False)
    meeting_lines_rm = []
    if rm.get("aggressive_view"):
        meeting_lines_rm.append(("😤 Aggressive Rick", rm["aggressive_view"]))
    if rm.get("conservative_view"):
        meeting_lines_rm.append(("🛡️ Conservative Clara", rm["conservative_view"]))
    if rm.get("neutral_view"):
        meeting_lines_rm.append(("⚖️ Neutral Nathan", rm["neutral_view"]))
    for flag in rm.get("risk_flags", []):
        meeting_lines_rm.append(("⚠️ 리스크 플래그", flag))
    meeting_lines_rm.append((
        "🛡️ 최종 합의",
        rm.get("consensus_reasoning", ""),
    ))

    change_note = f" (**{t_action}→{f_action} 변경됨**)" if changed else ""
    trace.append({
        "step":    7,
        "label":   "Risk Manager 회의 (3인 토론)",
        "emoji":   "🛡️",
        "input_summary": f"Trader 초안({t_action}) + 전체 리스크 지표",
        "output_summary": (
            f"{f_action}{change_note} | "
            f"포지션 {pct_str(rm.get('final_position_size_pct',0))} | "
            f"현금 {pct_str(rm.get('cash_reserve_pct',0))} | "
            f"리스크 {rm.get('risk_level','?').upper()}"
        ),
        "meeting_lines": meeting_lines_rm,
        "key_output": {
            "최종 결정": f_action,
            "변경 여부": changed,
            "포지션": rm.get("final_position_size_pct"),
            "현금 권고": rm.get("cash_reserve_pct"),
            "리스크": rm.get("risk_level"),
        },
    })

    return trace


def build_allocation_rows(portfolio: dict) -> list[dict]:
    """portfolio dict → 배분 테이블 rows."""
    rows = []
    for a in portfolio.get("allocations", []):
        rows.append({
            "종목":   a.get("ticker", ""),
            "결정":   action_icon(a.get("action", "HOLD")),
            "비중":   pct_str(a.get("weight", 0)),
            "근거":   a.get("rationale", ""),
        })
    rows.append({
        "종목":  "💵 현금",
        "결정":  "—",
        "비중":  pct_str(portfolio.get("cash_pct", 0)),
        "근거":  "현금 보유",
    })
    hedge = portfolio.get("hedge_pct", 0)
    if hedge > 0:
        inst = portfolio.get("hedge_instrument", "hedge")
        rows.append({
            "종목":  f"🛡️ 헤지({inst})",
            "결정":  "—",
            "비중":  pct_str(hedge),
            "근거":  "리스크 헤지",
        })
    return rows
