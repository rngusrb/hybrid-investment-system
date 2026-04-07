"""
Otto — Fund Manager agent.
HARD CONSTRAINT: raw data 접근 절대 불가.
공식 packet만 통합하여 최종 policy 선택.
"""
import json
import math
from typing import List
from agents.base_agent import BaseAgent
from schemas.otto_schema import OttoOutput
from pydantic import ValidationError
from utils.utility import compute_utility, DEFAULT_LAMBDAS

# Otto가 절대 받으면 안 되는 raw field 목록
_FORBIDDEN_RAW_FIELDS = frozenset([
    "raw_news",
    "raw_ohlcv",
    "raw_market_data",
    "ohlcv",
    "news_articles",
    "raw_financial_data",
    "raw_price_data",
    "price_history",
])


class OttoAgent(BaseAgent):
    """
    Fund Manager — 공식 packet만 통합, raw data 접근 차단.
    dual reward + risk-adjusted utility로 최종 policy 선택.
    """

    def run(self, input_packet: dict, state: dict) -> dict:
        """raw data 포함 여부 사전 차단 후 실행."""
        self._block_raw_data_access(input_packet)
        return super().run(input_packet, state)

    def _block_raw_data_access(self, input_packet: dict):
        """raw data field가 있으면 즉시 차단 — 설계 원칙 강제."""
        forbidden_found = _FORBIDDEN_RAW_FIELDS.intersection(input_packet.keys())
        if forbidden_found:
            raise ValueError(
                f"Otto MUST NOT receive raw data. Forbidden fields found: {forbidden_found}. "
                "Only official transformation packets are allowed."
            )

    # entry_style / rebalance_frequency LLM 변형 → 스키마 표준 매핑
    _ENTRY_ALIASES = {
        "market": "immediate",
        "market_order": "immediate",
        "limit": "staggered",
        "limit_order": "staggered",
        "twap": "phased",
        "vwap": "phased",
        "gradual": "phased",
        "passive": "hold",
        "no_trade": "hold",
    }
    _FREQ_ALIASES = {
        "day": "daily",
        "week": "weekly",
        "month": "monthly",
        "event": "event_driven",
        "event-driven": "event_driven",
        "on_event": "event_driven",
    }

    def _validate_output(self, output: dict) -> dict:
        output = dict(output)

        # candidate_policies: list of strings 보장
        cp = output.get("candidate_policies")
        if isinstance(cp, str):
            output["candidate_policies"] = [cp]
        elif isinstance(cp, list):
            output["candidate_policies"] = [str(x) if not isinstance(x, str) else x for x in cp]
        elif not cp:
            sp = output.get("selected_policy", "hold")
            output["candidate_policies"] = [str(sp)] if sp else ["hold"]

        # adaptive_weights: lookback_steps / w_sim / w_real 기본값 보정
        aw = output.get("adaptive_weights")
        if isinstance(aw, dict):
            aw = dict(aw)
            if "lookback_steps" not in aw or aw["lookback_steps"] is None:
                aw["lookback_steps"] = 10
            else:
                try:
                    aw["lookback_steps"] = max(1, int(aw["lookback_steps"]))
                except (TypeError, ValueError):
                    aw["lookback_steps"] = 10
            for k in ("w_sim", "w_real"):
                if k not in aw:
                    aw[k] = 0.5
                else:
                    try:
                        v = float(aw[k])
                        aw[k] = min(max(v, 0.0), 1.0)
                    except (TypeError, ValueError):
                        aw[k] = 0.5
            output["adaptive_weights"] = aw
        elif not aw:
            output["adaptive_weights"] = {"w_sim": 0.5, "w_real": 0.5, "lookback_steps": 10}

        # allocation: 퍼센트 교정 + [0,1] clamp
        alloc = output.get("allocation")
        if isinstance(alloc, dict):
            alloc = dict(alloc)
            for k in ("equities", "hedge", "cash"):
                v = alloc.get(k, 0.0)
                try:
                    v = float(v)
                    if v > 1.0:
                        v = v / 100.0
                    alloc[k] = min(max(v, 0.0), 1.0)
                except (TypeError, ValueError):
                    alloc[k] = 0.3
            output["allocation"] = alloc
        elif not alloc:
            output["allocation"] = {"equities": 0.6, "hedge": 0.1, "cash": 0.3}

        # execution_plan: Literal 교정
        ep = output.get("execution_plan")
        if isinstance(ep, dict):
            ep = dict(ep)
            es = str(ep.get("entry_style", "")).lower().strip()
            valid_es = {"immediate", "staggered", "phased", "hold"}
            ep["entry_style"] = self._ENTRY_ALIASES.get(es, es if es in valid_es else "staggered")

            rf = str(ep.get("rebalance_frequency", "")).lower().strip()
            valid_rf = {"daily", "weekly", "monthly", "event_driven"}
            ep["rebalance_frequency"] = self._FREQ_ALIASES.get(rf, rf if rf in valid_rf else "weekly")

            sl = ep.get("stop_loss", 0.05)
            try:
                sl = float(sl)
                if sl > 1.0:
                    sl = sl / 100.0
                ep["stop_loss"] = min(max(sl, 0.0), 1.0)
            except (TypeError, ValueError):
                ep["stop_loss"] = 0.05
            output["execution_plan"] = ep
        elif not ep:
            output["execution_plan"] = {"entry_style": "staggered", "rebalance_frequency": "weekly", "stop_loss": 0.05}

        # policy_reasoning_summary: string → list
        prs = output.get("policy_reasoning_summary")
        if isinstance(prs, str):
            output["policy_reasoning_summary"] = [prs] if prs else ["Policy selected based on risk-adjusted utility"]
        elif not prs:
            output["policy_reasoning_summary"] = ["Policy selected based on risk-adjusted utility"]

        # approval_status 소문자 정규화
        status = output.get("approval_status", "")
        if isinstance(status, str):
            output["approval_status"] = status.lower()

        validated = OttoOutput(**output)
        return validated.model_dump()

    def _build_prompt(self, input_packet: dict, state: dict) -> List[dict]:
        """Otto는 공식 packet summary만 받음."""
        content = f"Official Packets for Policy Selection:\n{json.dumps(input_packet, indent=2, default=str)}"
        return [{"role": "user", "content": content}]

    def _should_retry(self, output: dict, attempt: int) -> tuple:
        """approval_status가 valid 값인지 확인."""
        valid_statuses = {"approved", "approved_with_modification", "conditional_approval", "rejected"}
        status = output.get("approval_status", "")
        if status not in valid_statuses:
            return True, f"Invalid approval_status: '{status}'. Must be one of {valid_statuses}"
        if not output.get("selected_policy"):
            return True, "selected_policy is missing"
        return False, ""

    def compute_utility(
        self,
        combined_reward: float,
        risk_score: float,
        constraint_violation: float = 0.0,
        market_alignment_penalty: float = 0.0,
        execution_feasibility_penalty: float = 0.0,
        agent_reliability_penalty: float = 0.0,
        lambdas: dict = None,
    ) -> float:
        """
        Utility_t(μ) = CombinedReward - λ1*RiskScore - λ2*ConstraintViolation
                      - λ3*MarketAlignment - λ4*ExecutionFeasibility - λ5*AgentReliability

        utils.utility.compute_utility()에 위임 — policy 노드와 동일한 공식 사용.
        """
        lam = {**DEFAULT_LAMBDAS, **(self.config.get("dual_reward", {})), **(lambdas or {})}
        return compute_utility(
            combined_reward=combined_reward,
            risk_score=risk_score,
            constraint_violation=constraint_violation,
            market_alignment_penalty=market_alignment_penalty,
            execution_feasibility_penalty=execution_feasibility_penalty,
            agent_reliability_penalty=agent_reliability_penalty,
            lambdas=lam,
        )

    def compute_adaptive_weights(self, reward_history: List[dict]) -> dict:
        """
        w_sim = sigmoid(sum(r_sim) / sum(r_sim + r_real + eps))
        w_real = 1 - w_sim
        """
        eps = 1e-8
        if not reward_history:
            return {"w_sim": 0.5, "w_real": 0.5}

        sum_sim = sum(r.get("r_sim", 0.0) for r in reward_history)
        sum_total = sum(
            r.get("r_sim", 0.0) + r.get("r_real", 0.0) + eps for r in reward_history
        )

        ratio = sum_sim / (sum_total + eps)
        w_sim = 1.0 / (1.0 + math.exp(-ratio))
        return {"w_sim": round(w_sim, 4), "w_real": round(1.0 - w_sim, 4)}
