"""
성과 지표 전체 — 브리핑/v3.6 섹션 12 기준.

카테고리:
1. 기본 성과: return, sharpe, sortino, calmar, mdd, turnover, win_rate
2. 안정성: regime_robustness, risk_alert_precision, policy_oscillation
3. 메모리/시스템: retrieval_usefulness, decision_reproducibility
4. explainability: decision_trace_completeness, evidence_action_consistency
5. propagation/signal: technical_signal_adoption_rate, semantic_similarity, dropped_critical_signal_rate
"""
import numpy as np
from typing import List, Dict, Optional


def compute_annualized_return(returns: List[float], periods_per_year: int = 252) -> float:
    """연간 수익률."""
    if not returns:
        return 0.0
    total = np.prod([1 + r for r in returns])
    n = len(returns)
    return float(total ** (periods_per_year / n) - 1)


def compute_sharpe(returns: List[float], risk_free: float = 0.0, periods_per_year: int = 252) -> float:
    """Sharpe ratio."""
    if not returns or len(returns) < 2:
        return 0.0
    excess = [r - risk_free / periods_per_year for r in returns]
    mean_excess = np.mean(excess)
    std_excess = np.std(excess, ddof=1) or 1e-8
    return float(mean_excess / std_excess * np.sqrt(periods_per_year))


def compute_sortino(returns: List[float], risk_free: float = 0.0, periods_per_year: int = 252) -> float:
    """Sortino ratio (downside deviation 사용)."""
    if not returns or len(returns) < 2:
        return 0.0
    excess = [r - risk_free / periods_per_year for r in returns]
    mean_excess = np.mean(excess)
    downside_dev = np.sqrt(np.mean([min(r, 0)**2 for r in excess]) or 1e-16)
    return float(mean_excess / downside_dev * np.sqrt(periods_per_year))


def compute_max_drawdown(returns: List[float]) -> float:
    """Max drawdown (0~1, 양수)."""
    if not returns:
        return 0.0
    cumulative = np.cumprod([1 + r for r in returns])
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / peak
    return float(np.max(drawdown))


def compute_calmar(returns: List[float], periods_per_year: int = 252) -> float:
    """Calmar ratio = annualized_return / max_drawdown.
    MDD=0이면 drawdown 없음 → return이 양수면 5.0 (상한), 음수면 -5.0 반환.
    """
    ann_ret = compute_annualized_return(returns, periods_per_year)
    mdd = compute_max_drawdown(returns)
    if mdd == 0:
        return 5.0 if ann_ret >= 0 else -5.0
    return float(ann_ret / mdd)


def compute_win_rate(returns: List[float]) -> float:
    """승률."""
    if not returns:
        return 0.0
    return float(sum(1 for r in returns if r > 0) / len(returns))


def compute_policy_oscillation(policies: List[str]) -> float:
    """정책 변경 빈도 (0=안정, 1=매번 변경)."""
    if len(policies) < 2:
        return 0.0
    changes = sum(1 for a, b in zip(policies, policies[1:]) if a != b)
    return float(changes / (len(policies) - 1))


def compute_technical_signal_adoption_rate(
    audit_logs: List[dict],
) -> float:
    """
    technical signal adoption rate.
    propagation audit log에서 technical_signal_adoption_rate 평균.
    """
    if not audit_logs:
        return 0.0
    rates = [log.get("technical_signal_adoption_rate", 0.0) for log in audit_logs]
    return float(np.mean(rates))


def compute_dropped_critical_signal_rate(audit_logs: List[dict]) -> float:
    """dropped critical signal rate 평균."""
    if not audit_logs:
        return 0.0
    rates = [log.get("dropped_critical_signal_rate", 0.0) for log in audit_logs]
    return float(np.mean(rates))


def compute_semantic_similarity(audit_logs: List[dict]) -> float:
    """source-to-manager semantic similarity 평균."""
    if not audit_logs:
        return 0.0
    scores = [log.get("semantic_similarity_score", 0.0) for log in audit_logs]
    return float(np.mean(scores))


def compute_total_return(returns: List[float]) -> float:
    """누적 총 수익률."""
    if not returns:
        return 0.0
    return float(np.prod([1 + r for r in returns]) - 1)


def compute_average_turnover(turnover_series: List[float]) -> float:
    """평균 일간 turnover."""
    if not turnover_series:
        return 0.0
    return float(np.mean(turnover_series))


def compute_all_metrics(
    returns: List[float],
    policies: List[str],
    audit_logs: List[dict],
    periods_per_year: int = 252,
    turnover_series: Optional[List[float]] = None,
) -> Dict[str, float]:
    """모든 지표 한 번에 계산 (spec 12.1~12.5 기준)."""
    return {
        "total_return": compute_total_return(returns),
        "annualized_return": compute_annualized_return(returns, periods_per_year),
        "sharpe_ratio": compute_sharpe(returns, periods_per_year=periods_per_year),
        "sortino_ratio": compute_sortino(returns, periods_per_year=periods_per_year),
        "max_drawdown": compute_max_drawdown(returns),
        "calmar_ratio": compute_calmar(returns, periods_per_year),
        "win_rate": compute_win_rate(returns),
        "average_turnover": compute_average_turnover(turnover_series or []),
        "policy_oscillation_index": compute_policy_oscillation(policies),
        "technical_signal_adoption_rate": compute_technical_signal_adoption_rate(audit_logs),
        "dropped_critical_signal_rate": compute_dropped_critical_signal_rate(audit_logs),
        "source_to_manager_semantic_similarity": compute_semantic_similarity(audit_logs),
    }
