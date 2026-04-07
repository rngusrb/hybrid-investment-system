"""Risk Alert Meeting — RiskAdjustedUtility 기반 긴급 policy 수정."""
import math
import numpy as np
from meetings.base_meeting import BaseMeeting
from ledger.shared_ledger import SharedLedger
from tools.risk import RiskAnalyzer
from tools.sentiment import SentimentAnalyzer


class RiskAlertMeeting(BaseMeeting):
    """
    Risk Alert Meeting.
    RiskAdjustedUtility = (1-λ)*CombinedReward - λ*RiskReward
    단순 warning log가 아니라 policy를 실제로 수정함.
    """

    DEFAULT_LAMBDA = 0.5

    _risk_analyzer = RiskAnalyzer()
    _sentiment_analyzer = SentimentAnalyzer()

    def run(self, state: dict) -> dict:
        updated = dict(state)
        date = state.get("current_date", "")

        dave = state.get("dave_output") or {}
        emily = state.get("emily_output") or {}
        otto = state.get("otto_output") or {}

        # RiskAdjustedUtility 계산
        risk_score = dave.get("risk_score", 0.5)
        ts = emily.get("technical_signal_state") or {}
        technical_reversal_penalty = ts.get("reversal_risk", 0.3)

        # sentiment_safety: tools로 계산 (raw_news 있으면)
        raw_news = state.get("raw_news") or []
        if raw_news and isinstance(raw_news, list):
            news_texts = [n.get("title", "") + " " + n.get("description", "")
                          for n in raw_news if isinstance(n, dict)]
            if news_texts:
                sentiment_result = self._sentiment_analyzer.analyze_batch(news_texts)
                # sentiment_score: -1~1 → safety: 0~1 (양수면 안전)
                raw_sentiment = sentiment_result["sentiment_score"]
                sentiment_safety = float((raw_sentiment + 1.0) / 2.0)  # -1~1 → 0~1
            else:
                sentiment_safety = 1.0 - emily.get("regime_confidence", 0.5)
        else:
            sentiment_safety = 1.0 - emily.get("regime_confidence", 0.5)

        # stress_severity: tools로 계산 (portfolio returns 있으면)
        # dave_output에서 risk_components 기반으로 proxy returns 생성 후 stress test
        dave_risk_components = dave.get("risk_components") or {}
        vol_proxy = dave_risk_components.get("volatility", 0.015)
        # proxy daily returns (30일치) — vol 기반 합성
        import hashlib
        current_date = state.get("current_date")
        date_seed = int(hashlib.md5(str(current_date or "2024-01-01").encode()).hexdigest(), 16) % (2**31)
        proxy_returns = (np.random.default_rng(date_seed).normal(0, max(vol_proxy, 0.005), 30)).tolist()
        stress_result = self._risk_analyzer.run_stress_test(proxy_returns)
        stress_severity = stress_result["severity"]
        # dave의 값과 평균 (둘 다 반영)
        dave_stress = (dave.get("stress_test") or {}).get("severity_score", stress_severity)
        stress_severity = (stress_severity + float(dave_stress)) / 2.0

        risk_reward = self._compute_risk_reward(
            risk_score=risk_score,
            stress_severity=stress_severity,
            sentiment_safety=sentiment_safety,
            technical_reversal_penalty=technical_reversal_penalty,
        )

        # CombinedReward = w_sim * r_sim + w_real * r_real
        # Risk Alert 시점에는 실시간 r_sim/r_real이 없으므로 adaptive_weights + 보수적 proxy 사용
        weights = otto.get("adaptive_weights") or {}
        w_sim = weights.get("w_sim", 0.5)
        w_real = weights.get("w_real", 0.5)
        # r_sim proxy: 현 시장 기술적 신호 기반 (reversal 낮을수록 sim 환경 양호)
        r_sim_proxy = max(0.0, 1.0 - technical_reversal_penalty)
        # r_real proxy: sentiment_safety (시장 안전 수준)
        r_real_proxy = sentiment_safety
        combined_reward = w_sim * r_sim_proxy + w_real * r_real_proxy

        lam = self.config.get("lambda", self.DEFAULT_LAMBDA)
        utility = (1 - lam) * combined_reward - lam * risk_reward

        # policy 수정 결정
        emergency_controls = self._determine_emergency_controls(risk_score, stress_severity, utility)

        risk_override = {
            "date": date,
            "trigger_reason": f"risk_score={risk_score:.2f}",
            "risk_adjusted_utility": round(utility, 4),
            "risk_reward": round(risk_reward, 4),
            "emergency_controls": emergency_controls,
            "original_approval": otto.get("approval_status"),
            "override_action": "de_risk" if risk_score > 0.85 else "reduce_exposure",
        }

        # Ledger에 risk override 기록
        self._record_to_ledger("risk_override_record", risk_override, date, "RiskAlertMeeting")

        updated["flow_decision_reason"] = f"risk_alert: utility={utility:.4f}, controls={emergency_controls}"
        return updated

    def _compute_risk_reward(
        self,
        risk_score: float,
        stress_severity: float,
        sentiment_safety: float,
        technical_reversal_penalty: float,
        a: float = 0.4, b: float = 0.3, c: float = 0.2, d: float = 0.1,
    ) -> float:
        """
        RiskReward = -a*R_score - b*StressSeverity + c*SentimentSafety - d*TechnicalReversalPenalty
        """
        return (
            -a * risk_score
            - b * stress_severity
            + c * sentiment_safety
            - d * technical_reversal_penalty
        )

    def _determine_emergency_controls(self, risk_score: float, stress_severity: float, utility: float) -> list:
        controls = []
        if risk_score > 0.85:
            controls.append("immediate_de_risk")
            controls.append("reduce_gross_exposure_to_50pct")
        elif risk_score > 0.75:
            controls.append("reduce_directional_exposure")
        if stress_severity > 0.7:
            controls.append("add_hedge_position")
        if utility < -0.2:
            controls.append("consider_full_exit")
        return controls
