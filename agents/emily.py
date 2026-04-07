"""Emily — Market Analyst agent."""
import json
from typing import List
from agents.base_agent import BaseAgent
from schemas.emily_schema import EmilyOutput, EmilyToBobPacket
from pydantic import ValidationError


class EmilyAgent(BaseAgent):
    """
    시장 상태를 전략 가능한 feature space로 변환.
    technical signal을 공식 출력에 독립 필드로 포함.
    """

    _TREND_ALIASES = {
        "uptrend": "up", "up_trend": "up", "bullish": "up", "rising": "up",
        "downtrend": "down", "down_trend": "down", "bearish": "down", "falling": "down",
        "sideways": "mixed", "neutral": "mixed", "ranging": "mixed", "consolidating": "mixed",
    }
    _REGIME_ALIASES = {
        "risk on": "risk_on", "risk-on": "risk_on",
        "risk off": "risk_off", "risk-off": "risk_off",
        "rebound": "fragile_rebound", "recovering": "fragile_rebound",
        "transitioning": "transition", "uncertain": "mixed",
    }
    _BIAS_ALIASES = {
        "selective long": "selective_long", "selective-long": "selective_long",
        "long": "selective_long", "bullish": "selective_long",
        "defensive_long": "defensive", "risk_off": "defensive",
        "bear": "defensive", "short": "defensive",
        "hold": "neutral", "cash": "neutral", "flat": "neutral",
    }

    def _validate_output(self, output: dict) -> dict:
        output = dict(output)

        # date: AgentBaseOutput 필수 필드 — 누락 시 기본값
        if not output.get("date"):
            output["date"] = output.get("current_date", "")

        # market_regime 정규화
        regime = str(output.get("market_regime", "")).lower().strip()
        valid_regimes = {"risk_on", "risk_off", "mixed", "fragile_rebound", "transition"}
        output["market_regime"] = self._REGIME_ALIASES.get(regime, regime if regime in valid_regimes else "mixed")

        # recommended_market_bias 정규화
        bias = str(output.get("recommended_market_bias", "")).lower().strip()
        valid_biases = {"selective_long", "defensive", "neutral"}
        output["recommended_market_bias"] = self._BIAS_ALIASES.get(bias, bias if bias in valid_biases else "neutral")

        # technical_signal_state 교정
        tss = output.get("technical_signal_state")
        if isinstance(tss, dict):
            tss = dict(tss)
            td = str(tss.get("trend_direction", "")).lower().strip()
            valid_td = {"up", "down", "mixed"}
            tss["trend_direction"] = self._TREND_ALIASES.get(td, td if td in valid_td else "mixed")
            for field in ("continuation_strength", "reversal_risk", "technical_confidence"):
                v = tss.get(field)
                try:
                    tss[field] = min(max(float(v), 0.0), 1.0) if v is not None else 0.5
                except (TypeError, ValueError):
                    tss[field] = 0.5
            output["technical_signal_state"] = tss
        elif not tss:
            output["technical_signal_state"] = {
                "trend_direction": "mixed",
                "continuation_strength": 0.5,
                "reversal_risk": 0.3,
                "technical_confidence": 0.5,
            }

        # macro_state: 누락 필드 기본값 0.0, [-1,1] clamp
        ms = output.get("macro_state")
        if isinstance(ms, dict):
            ms = dict(ms)
            for field in ("rates", "inflation", "growth", "liquidity", "risk_sentiment"):
                v = ms.get(field, 0.0)
                try:
                    ms[field] = min(max(float(v), -1.0), 1.0)
                except (TypeError, ValueError):
                    ms[field] = 0.0
            output["macro_state"] = ms
        elif not ms:
            output["macro_state"] = {"rates": 0.0, "inflation": 0.0, "growth": 0.0, "liquidity": 0.0, "risk_sentiment": 0.0}

        # event_sensitivity_map: dict → list 교정
        esm = output.get("event_sensitivity_map")
        if isinstance(esm, dict):
            output["event_sensitivity_map"] = [{"event": k, "risk_level": v} for k, v in esm.items()]
        elif esm is None:
            output["event_sensitivity_map"] = []

        # list 필드 보장
        for field in ("risk_flags", "uncertainty_reasons", "bull_catalysts", "bear_catalysts", "technical_conflict_flags"):
            val = output.get(field)
            if isinstance(val, str):
                output[field] = [val] if val else []
            elif val is None:
                output[field] = []

        if output.get("sector_preference") is None:
            output["sector_preference"] = []

        validated = EmilyOutput(**output)
        return validated.model_dump()

    def _build_prompt(self, input_packet: dict, state: dict) -> List[dict]:
        # retrieval context가 있으면 포함
        retrieved = state.get("retrieved_market_cases", [])
        content_parts = [
            f"Market Data:\n{json.dumps(input_packet, indent=2, default=str)}"
        ]
        if retrieved:
            content_parts.append(
                f"\nRelevant Historical Cases:\n{json.dumps(retrieved, indent=2, default=str)}"
            )
        return [{"role": "user", "content": "\n".join(content_parts)}]

    def _should_retry(self, output: dict, attempt: int) -> tuple:
        """technical_signal_state 필드 누락 시 재시도."""
        if "technical_signal_state" not in output:
            return True, "Missing technical_signal_state field — this is a required independent field"
        confidence = output.get("regime_confidence", 1.0)
        floor = self.config.get("agent_confidence_floor", 0.45)
        if confidence < floor:
            return True, f"regime_confidence {confidence} below floor {floor}"
        return False, ""

    def to_bob_packet(self, emily_output: dict, date: str) -> dict:
        """Emily full output → Bob feature packet (transformation)."""
        ts = emily_output.get("technical_signal_state", {})
        packet = EmilyToBobPacket(
            source_agent="Emily",
            target_agent="Bob",
            date=date,
            regime=emily_output["market_regime"],
            regime_confidence=emily_output["regime_confidence"],
            preferred_sectors=[
                s["sector"]
                for s in emily_output.get("sector_preference", [])
                if s["score"] >= 0.6
            ],
            avoid_sectors=[
                s["sector"]
                for s in emily_output.get("sector_preference", [])
                if s["score"] < 0.4
            ],
            market_bias=emily_output["recommended_market_bias"],
            event_risk_level=(
                emily_output.get("event_sensitivity_map", [{}])[0].get("risk_level", 0.3)
                if emily_output.get("event_sensitivity_map")
                else 0.3
            ),
            market_uncertainty=min(len(emily_output.get("uncertainty_reasons", [])) * 0.1, 0.9),
            technical_direction=ts.get("trend_direction", "mixed"),
            technical_confidence=ts.get("technical_confidence", 0.5),
            reversal_risk=ts.get("reversal_risk", 0.3),
        )
        return packet.model_dump()
