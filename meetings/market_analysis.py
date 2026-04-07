"""Weekly Market Analysis Meeting."""
from meetings.base_meeting import BaseMeeting
from schemas.meeting_schema import (
    DebateResolution, BullCase, BearCase,
    SignalConflictResolution, ConflictItem, WeeklyMarketReport,
)
from ledger.shared_ledger import SharedLedger
from typing import Optional
from tools.technical import TechnicalAnalyzer

DEBATE_SKIP_THRESHOLD = 0.85


class MarketAnalysisMeeting(BaseMeeting):

    _tech_analyzer = TechnicalAnalyzer()
    """
    Weekly Market Analysis Meeting.
    debate sub-step과 signal conflict resolution이 실제 로직으로 연결됨.
    """

    def run(self, state: dict) -> dict:
        updated = dict(state)
        date = state.get("current_date", "")
        emily = state.get("emily_output") or {}

        # Step 1: debate sub-step
        debate = self._run_debate(emily, state)
        updated["debate_resolution"] = debate.model_dump()

        # Step 2: signal conflict resolution
        ts = emily.get("technical_signal_state") or {}
        conflict = self._run_signal_conflict_resolution(emily, ts, state)
        updated["signal_conflict_resolution"] = conflict.model_dump()

        # Step 3: final market report 확정
        # 기술적 지표 계산 (raw_market_data에 OHLCV 있으면)
        raw_market = state.get("raw_market_data") or {}
        tech_indicators = {}
        closes = []

        # raw_market_data가 dict이고 bars/ohlcv 필드가 있으면 추출
        if isinstance(raw_market, dict):
            bars = raw_market.get("bars") or raw_market.get("ohlcv") or []
            if isinstance(bars, list) and len(bars) >= 20:
                closes = [float(b.get("close", 0)) for b in bars if b.get("close")]

        if len(closes) >= 20:
            tech_indicators = {
                "rsi": self._tech_analyzer.compute_rsi(closes),
                "macd": self._tech_analyzer.compute_macd(closes),
                "bollinger": self._tech_analyzer.compute_bollinger_bands(closes),
                "momentum_signal": self._tech_analyzer.compute_momentum_signal(closes),
            }

        # 기존 ts 기반 packet에 실제 지표 추가
        base_tech_packet = {
            "trend_direction": ts.get("trend_direction", "mixed"),
            "technical_confidence": ts.get("technical_confidence", 0.5),
            "reversal_risk": ts.get("reversal_risk", 0.3),
            "continuation_strength": ts.get("continuation_strength", 0.5),
        }
        if tech_indicators:
            base_tech_packet["computed_indicators"] = tech_indicators

        report = WeeklyMarketReport(
            date=date,
            market_regime=emily.get("market_regime", "mixed"),
            regime_confidence=emily.get("regime_confidence", 0.5) + debate.regime_confidence_adjustment,
            preferred_sectors=[s["sector"] for s in emily.get("sector_preference", []) if s.get("score", 0) >= 0.6],
            avoid_sectors=[s["sector"] for s in emily.get("sector_preference", []) if s.get("score", 1) < 0.4],
            unresolved_risks=debate.unresolved_issues,
            debate_resolution=debate,
            signal_conflict_resolution=conflict,
            technical_summary_packet=base_tech_packet,
        )
        updated["weekly_market_report"] = report.model_dump()

        # Step 4: Ledger 기록
        self._record_to_ledger("final_market_report", report.model_dump(), date, "MarketAnalysisMeeting")
        self._record_to_ledger("debate_resolution", debate.model_dump(), date, "MarketAnalysisMeeting")
        self._record_to_ledger("signal_conflict_resolution", conflict.model_dump(), date, "MarketAnalysisMeeting")
        self._record_to_ledger("technical_summary_packet", report.technical_summary_packet, date, "Emily")

        return updated

    def _run_debate(self, emily: dict, state: dict) -> DebateResolution:
        """
        bull/bear debate sub-step.
        Emily confidence 높으면 간소화 (실제 로직).
        """
        regime_confidence = emily.get("regime_confidence", 0.5)

        if regime_confidence >= DEBATE_SKIP_THRESHOLD:
            # 간소화: unresolved_issues 없음, regime_confidence_adjustment 0
            return DebateResolution(
                bull_case=BullCase(
                    growth_path="Strong regime confidence — bull path confirmed",
                    upside_catalysts=emily.get("bull_catalysts", []),
                    sustainability="High",
                ),
                bear_case=BearCase(
                    downside_risks=emily.get("bear_catalysts", []),
                    fragility="Low",
                    reversal_triggers=emily.get("technical_conflict_flags", []),
                ),
                moderator_summary="High confidence regime — debate simplified",
                unresolved_issues=[],
                regime_confidence_adjustment=0.0,
            )

        # 정상 debate: 불확실성 반영
        uncertainty_reasons = emily.get("uncertainty_reasons", [])
        risk_flags = emily.get("risk_flags", [])

        # 불확실성이 높으면 confidence 하향 조정
        confidence_adj = -0.05 * len(uncertainty_reasons)
        confidence_adj = max(confidence_adj, -0.2)  # 최대 -0.2

        return DebateResolution(
            bull_case=BullCase(
                growth_path=f"Regime: {emily.get('market_regime', 'mixed')} — upside path",
                upside_catalysts=emily.get("bull_catalysts", []),
                sustainability="Medium" if uncertainty_reasons else "High",
            ),
            bear_case=BearCase(
                downside_risks=emily.get("bear_catalysts", []),
                fragility="High" if risk_flags else "Medium",
                reversal_triggers=emily.get("technical_conflict_flags", []),
            ),
            moderator_summary=f"Debate completed. Unresolved: {len(uncertainty_reasons)} issues.",
            unresolved_issues=uncertainty_reasons[:3],  # 상위 3개
            regime_confidence_adjustment=confidence_adj,
        )

    def _run_signal_conflict_resolution(self, emily: dict, ts: dict, state: dict) -> SignalConflictResolution:
        """
        technical vs macro signal 충돌 실제 체크.
        방향 일치하면 conflict_matrix 비움 (스킵).
        """
        tech_dir = ts.get("trend_direction", "mixed")
        market_bias = emily.get("recommended_market_bias", "neutral")
        macro_regime = emily.get("market_regime", "mixed")

        conflicts = []

        # technical vs macro 충돌 체크
        tech_bullish = tech_dir == "up"
        macro_risk_off = macro_regime in ("risk_off", "transition")
        if tech_bullish and macro_risk_off:
            conflicts.append(ConflictItem(
                signal_a="technical_momentum_strong",
                signal_b="macro_risk_off",
                conflict_type="time_horizon_mismatch",
                resolution="reduce gross exposure, keep selective long",
            ))

        # technical vs market_bias 충돌
        tech_bearish = tech_dir == "down"
        bias_bullish = market_bias == "selective_long"
        if tech_bearish and bias_bullish:
            conflicts.append(ConflictItem(
                signal_a="technical_trend_down",
                signal_b="market_bias_selective_long",
                conflict_type="direction_conflict",
                resolution="reduce position size, add hedge",
            ))

        # reversal risk 높은데 directional bias
        reversal_risk = ts.get("reversal_risk", 0.0)
        if reversal_risk > 0.6 and market_bias == "selective_long":
            conflicts.append(ConflictItem(
                signal_a="high_reversal_risk",
                signal_b="selective_long_bias",
                conflict_type="magnitude_conflict",
                resolution="cut directional exposure, increase cash",
            ))

        # strategy tendency vs current risk regime 충돌
        # market_regime이 risk_off인데 bias가 selective_long이면 regime mismatch
        if macro_regime in ("risk_off", "fragile_rebound") and market_bias == "selective_long":
            conflicts.append(ConflictItem(
                signal_a="regime_risk_off",
                signal_b="bias_selective_long",
                conflict_type="regime_mismatch",
                resolution="reduce overall exposure, maintain only high-conviction positions",
            ))

        # sector preference vs concentration risk
        # bear_catalysts가 많은데 sector_preference가 집중된 경우
        bear_count = len(emily.get("bear_catalysts", []))
        sector_prefs = emily.get("sector_preference", [])
        high_score_sectors = [s for s in sector_prefs if isinstance(s, dict) and s.get("score", 0) >= 0.8]
        if bear_count >= 2 and len(high_score_sectors) <= 1 and high_score_sectors:
            conflicts.append(ConflictItem(
                signal_a="sector_concentration_high",
                signal_b="multiple_bear_catalysts",
                conflict_type="magnitude_conflict",
                resolution="diversify sector exposure, cap max single sector weight",
            ))

        return SignalConflictResolution(conflict_matrix=conflicts)
