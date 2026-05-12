"""
Baseline 비교군 — v3.6 섹션 12.6 기준 9개.

baselines:
1. buy_and_hold
2. mean_variance
3. single_agent_llm
4. multi_agent_no_sim_trading
5. multi_agent_no_risk_alert
6. multi_agent_no_memory
7. multi_agent_no_calibration
8. multi_agent_no_propagation_audit
9. full_hybrid_system
"""
from typing import List, Dict
from dataclasses import dataclass

BASELINE_NAMES = [
    "buy_and_hold",
    "mean_variance",
    "single_agent_llm",
    "multi_agent_no_sim_trading",
    "multi_agent_no_risk_alert",
    "multi_agent_no_memory",
    "multi_agent_no_calibration",
    "multi_agent_no_propagation_audit",
    "full_hybrid_system",
]


@dataclass
class BaselineConfig:
    name: str
    description: str
    disabled_components: List[str]  # 비활성화된 컴포넌트 목록


BASELINE_CONFIGS = {
    "buy_and_hold": BaselineConfig(
        name="buy_and_hold",
        description="단순 buy-and-hold 인덱스",
        disabled_components=["all_agents", "meetings", "risk_alert", "memory"],
    ),
    "mean_variance": BaselineConfig(
        name="mean_variance",
        description="Mean-Variance 최적화 allocator",
        disabled_components=["llm_agents", "meetings", "debate"],
    ),
    "single_agent_llm": BaselineConfig(
        name="single_agent_llm",
        description="단일 LLM agent (multi-agent 없음)",
        disabled_components=["bob", "dave", "meetings", "risk_alert"],
    ),
    "multi_agent_no_sim_trading": BaselineConfig(
        name="multi_agent_no_sim_trading",
        description="simulated trading 없는 multi-agent",
        disabled_components=["simulated_reward"],
    ),
    "multi_agent_no_risk_alert": BaselineConfig(
        name="multi_agent_no_risk_alert",
        description="Risk Alert Meeting 없는 multi-agent",
        disabled_components=["risk_alert_meeting"],
    ),
    "multi_agent_no_memory": BaselineConfig(
        name="multi_agent_no_memory",
        description="memory retrieval 없는 multi-agent",
        disabled_components=["market_memory", "strategy_memory", "retrieval"],
    ),
    "multi_agent_no_calibration": BaselineConfig(
        name="multi_agent_no_calibration",
        description="calibration layer 없는 multi-agent",
        disabled_components=["calibration"],
    ),
    "multi_agent_no_propagation_audit": BaselineConfig(
        name="multi_agent_no_propagation_audit",
        description="propagation audit 없는 multi-agent",
        disabled_components=["propagation_audit"],
    ),
    "full_hybrid_system": BaselineConfig(
        name="full_hybrid_system",
        description="전체 hybrid system (모든 컴포넌트 활성)",
        disabled_components=[],
    ),
}


def get_baseline_config(name: str) -> BaselineConfig:
    if name not in BASELINE_CONFIGS:
        raise ValueError(f"Unknown baseline: {name}. Available: {list(BASELINE_CONFIGS.keys())}")
    return BASELINE_CONFIGS[name]


def list_baselines() -> List[str]:
    return list(BASELINE_NAMES)


# ── 실제 시그널/수익률 계산 ──────────────────────────────────────────────────

def _ema(data: List[float], period: int) -> List[float]:
    """EMA 계산 (단순 loop, pandas 미사용)."""
    if not data:
        return []
    k = 2.0 / (period + 1)
    result = [data[0]]
    for x in data[1:]:
        result.append(x * k + result[-1] * (1 - k))
    return result


def compute_macd_signal(bars: List[dict]) -> int:
    """
    MACD(12, 26, 9) 시그널: 마지막 바 기준.
    Returns 1 (MACD > Signal → long) or 0 (flat).
    bars 부족(<26)이면 기본값 1 반환.
    """
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    if len(closes) < 26:
        return 1
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    # signal line은 macd_line 전체 대상
    signal_line = _ema(macd_line, 9)
    return 1 if macd_line[-1] > signal_line[-1] else 0


def compute_sma_signal(bars: List[dict], period: int = 20) -> int:
    """
    SMA(period) 시그널: 현재가 > SMA → long(1), else flat(0).
    bars 부족이면 기본값 1 반환.
    """
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]
    if len(closes) < period:
        return 1
    sma = sum(closes[-period:]) / period
    return 1 if closes[-1] > sma else 0


def compute_baseline_returns(
    system_dates: List[str],
    aapl_prices: List[float],   # 각 날짜의 AAPL 현재가
    aapl_bars_by_date: Dict[str, List[dict]],  # 날짜 → AAPL bars (시그널용)
) -> Dict[str, List[float]]:
    """
    BnH / MACD / SMA 베이스라인 수익률 시계열 계산.

    system_dates[i] → system_dates[i+1] 기간의 수익률.
    → len(system_dates) - 1 개의 수익률 반환.

    Args:
        system_dates: 포트폴리오 실행 날짜 목록 (시간순)
        aapl_prices:  각 날짜의 AAPL 현재가 (len == len(system_dates))
        aapl_bars_by_date: 날짜 → 해당 날짜까지의 AAPL OHLCV bars
    """
    bnh, macd_ret, sma_ret = [], [], []

    for i in range(len(system_dates) - 1):
        p0 = aapl_prices[i]
        p1 = aapl_prices[i + 1]
        if p0 and p0 > 0 and p1 and p1 > 0:
            period_ret = p1 / p0 - 1.0
        else:
            period_ret = 0.0

        bnh.append(period_ret)

        bars = aapl_bars_by_date.get(system_dates[i], [])
        macd_sig = compute_macd_signal(bars)
        sma_sig  = compute_sma_signal(bars)

        macd_ret.append(period_ret if macd_sig == 1 else 0.0)
        sma_ret.append(period_ret if sma_sig  == 1 else 0.0)

    return {
        "buy_and_hold": bnh,
        "macd":         macd_ret,
        "sma":          sma_ret,
    }
