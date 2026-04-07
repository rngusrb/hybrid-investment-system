"""
RiskAnalyzer — VaR, Portfolio Beta, Sector Concentration, Stress Test.
scipy + numpy 기반. 외부 API 불필요.
"""
import numpy as np
from typing import List, Dict, Optional
from scipy import stats


class RiskAnalyzer:

    def compute_var(self, returns: List[float], confidence: float = 0.95, method: str = "historical") -> float:
        """Value at Risk (양수, 손실 크기). 데이터 부족 시 0.0."""
        if len(returns) < 10:
            return 0.0
        arr = np.array(returns, dtype=float)
        if method == "parametric":
            mu, sigma = np.mean(arr), np.std(arr, ddof=1)
            var = float(-(mu + stats.norm.ppf(1 - confidence) * sigma))
        else:
            var = float(-np.percentile(arr, (1 - confidence) * 100))
        return round(max(0.0, var), 4)

    def compute_portfolio_beta(self, portfolio_returns: List[float], benchmark_returns: List[float]) -> float:
        """포트폴리오 베타 (CAPM). 데이터 부족 시 1.0."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 10:
            return 1.0
        p = np.array(portfolio_returns[:n], dtype=float)
        b = np.array(benchmark_returns[:n], dtype=float)
        cov = np.cov(p, b)
        var_b = cov[1, 1]
        if var_b < 1e-10:
            return 1.0
        return round(float(np.clip(cov[0, 1] / var_b, -5.0, 5.0)), 4)

    def compute_sector_concentration(self, sector_weights: Dict[str, float]) -> float:
        """섹터 집중도 HHI 기반 (0~1). 1에 가까울수록 집중."""
        if not sector_weights:
            return 0.0
        weights = np.array(list(sector_weights.values()), dtype=float)
        total = weights.sum()
        if total == 0:
            return 0.0
        norm = weights / total
        hhi = float(np.sum(norm ** 2))
        n = len(weights)
        min_hhi = 1.0 / n
        return round(float(np.clip((hhi - min_hhi) / (1.0 - min_hhi + 1e-8), 0.0, 1.0)), 4)

    def run_stress_test(self, returns: List[float], shock_scenarios: Optional[Dict[str, float]] = None) -> Dict:
        """스트레스 테스트. severity + worst_case_drawdown 반환."""
        if shock_scenarios is None:
            shock_scenarios = {
                "market_crash": -0.20,
                "moderate_correction": -0.10,
                "rate_spike": -0.08,
                "liquidity_crisis": -0.15,
            }
        if len(returns) < 10:
            return {"severity": 0.5, "worst_case_drawdown": 0.1, "scenario_losses": {}}
        arr = np.array(returns, dtype=float)
        beta_proxy = float(np.std(arr) / 0.012)
        scenario_losses = {
            s: round(float(np.clip(shock * beta_proxy, -0.99, 0.0)), 4)
            for s, shock in shock_scenarios.items()
        }
        worst = min(scenario_losses.values()) if scenario_losses else -0.1
        severity = float(np.clip(abs(worst), 0.0, 1.0))
        cumulative = np.cumprod(1 + arr)
        peak = np.maximum.accumulate(cumulative)
        hist_mdd = float(np.max((peak - cumulative) / (peak + 1e-8)))
        return {
            "severity": round(severity, 4),
            "worst_case_drawdown": round(float(np.clip(max(abs(worst), hist_mdd), 0.0, 0.99)), 4),
            "scenario_losses": scenario_losses,
        }
