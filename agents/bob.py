"""Bob — Strategy Analyst agent."""
import json
from typing import List
from agents.base_agent import BaseAgent
from schemas.bob_schema import BobOutput, BobToDavePacket, BobToExecutionPacket
from pydantic import ValidationError


TECHNICAL_CONFIDENCE_THRESHOLD = 0.6   # 이 이상이면 technical-aligned candidate 필수
TECHNICAL_ALIGNMENT_FLOOR = 0.5        # technical-aligned로 인정할 최소 alignment


class BobAgent(BaseAgent):
    """
    Emily packet을 전략 후보 집합으로 변환 + simulated trading 검증.
    technical_confidence >= 0.6이면 technical-aligned candidate 최소 1개 포함 (하드 강제).
    """

    def __init__(self, llm, config: dict, trading_engine=None):
        super().__init__(llm, config)
        self._input_technical_confidence: float = 0.0  # _should_retry에서 참조
        self._trading_engine = trading_engine  # None이면 LLM 값 그대로 사용

    def run(self, input_packet: dict, state: dict) -> dict:
        """input_packet에서 technical_confidence를 저장한 후 상위 run() 실행."""
        self._input_technical_confidence = float(
            input_packet.get("technical_confidence", 0.0)
        )
        output = super().run(input_packet, state)
        if self._trading_engine is not None:
            output = self._enrich_with_real_sim_metrics(output)
        return output

    # LLM이 자주 잘못 쓰는 strategy type 매핑
    _TYPE_ALIASES = {
        "technical_momentum": "momentum",
        "momentum_long": "momentum",
        "trend_following": "momentum",
        "sector_rotation": "directional",
        "sector_long": "directional",
        "directional_long": "directional",
        "hedged_long": "hedged",
        "risk_management": "hedged",
        "volatility_protection": "hedged",
        "long_short": "market_neutral",
        "pairs_trading": "market_neutral",
        "conservative": "defensive",
        "risk_off": "defensive",
    }

    # sim_metrics 필드명 LLM 변형 → 스키마 표준 이름 매핑
    _SIM_METRICS_ALIASES = {
        "expected_return": "return",
        "total_return": "return",
        "annualized_return": "return",
        "win_rate": "hit_rate",
        "winning_rate": "hit_rate",
        "sharpe_ratio": "sharpe",
        "sortino_ratio": "sortino",
        "max_drawdown": "mdd",
        "maximum_drawdown": "mdd",
        "avg_turnover": "turnover",
        "average_turnover": "turnover",
    }

    def _validate_output(self, output: dict) -> dict:
        output = dict(output)

        candidates = output.get("candidate_strategies", [])
        fixed_candidates = []
        for c in candidates:
            c = dict(c)

            # type alias 교정
            raw_type = c.get("type", "")
            c["type"] = self._TYPE_ALIASES.get(raw_type, raw_type)

            # regime_fit / technical_alignment: string이면 float 변환 시도, 실패 시 0.5
            for field in ("regime_fit", "technical_alignment"):
                v = c.get(field)
                if isinstance(v, str):
                    try:
                        c[field] = float(v)
                    except (ValueError, TypeError):
                        c[field] = 0.5

            # optimization_suggestions: string → list
            os_ = c.get("optimization_suggestions")
            if isinstance(os_, str):
                c["optimization_suggestions"] = [os_] if os_ else []
            elif os_ is None:
                c["optimization_suggestions"] = []

            # sim_metrics 자동 교정
            sm = c.get("sim_metrics")
            if isinstance(sm, dict):
                sm = dict(sm)
                # 필드명 alias 교정
                for alias, canonical in self._SIM_METRICS_ALIASES.items():
                    if alias in sm and canonical not in sm:
                        sm[canonical] = sm.pop(alias)
                # mdd 음수/퍼센트 교정
                if "mdd" in sm and sm["mdd"] is not None:
                    try:
                        v = float(sm["mdd"])
                        if v < 0:
                            v = abs(v)
                        if v > 1.0:
                            v = v / 100.0
                        sm["mdd"] = min(v, 1.0)
                    except (TypeError, ValueError):
                        sm["mdd"] = 0.1
                c["sim_metrics"] = sm

            fixed_candidates.append(c)
        output["candidate_strategies"] = fixed_candidates

        # selected_for_review: list of dicts → list of strings (이름만 추출)
        sfr = output.get("selected_for_review")
        if isinstance(sfr, list):
            fixed_sfr = []
            for item in sfr:
                if isinstance(item, dict):
                    name = item.get("strategy_name") or item.get("name") or item.get("strategy_id", "")
                    fixed_sfr.append(str(name))
                elif isinstance(item, str):
                    fixed_sfr.append(item)
            output["selected_for_review"] = fixed_sfr
        elif not sfr:
            # selected_for_review 누락 시 첫 번째 candidate 이름으로 fallback
            names = [c.get("name", "") for c in fixed_candidates if c.get("name")]
            output["selected_for_review"] = names[:1] if names else []

        validated = BobOutput(**output)
        return validated.model_dump()

    def _build_prompt(self, input_packet: dict, state: dict) -> List[dict]:
        retrieved = state.get("retrieved_strategy_cases", [])
        content_parts = [
            f"Emily Packet + State:\n{json.dumps(input_packet, indent=2, default=str)}"
        ]
        if retrieved:
            content_parts.append(
                f"\nRelevant Historical Strategies:\n{json.dumps(retrieved, indent=2, default=str)}"
            )
        return [{"role": "user", "content": "\n".join(content_parts)}]

    def _should_retry(self, output: dict, attempt: int) -> tuple:
        """
        1. candidate가 없으면 재시도
        2. sim_window 또는 failure_conditions 누락 시 재시도
        3. technical_confidence >= 0.6인데 technical-aligned candidate 없으면 재시도 (하드 강제)
        """
        candidates = output.get("candidate_strategies", [])
        if not candidates:
            return True, "No candidate strategies generated"

        for c in candidates:
            if not c.get("sim_window", {}).get("train_start"):
                return True, f"Strategy '{c.get('name')}' missing sim_window — future data usage risk"
            if not c.get("failure_conditions"):
                return True, f"Strategy '{c.get('name')}' missing failure_conditions"

        # technical_confidence >= 0.6 → technical-aligned candidate 필수 (설계 원칙 강제)
        if self._input_technical_confidence >= TECHNICAL_CONFIDENCE_THRESHOLD:
            has_technical_aligned = any(
                c.get("technical_alignment", 0.0) >= TECHNICAL_ALIGNMENT_FLOOR
                for c in candidates
            )
            if not has_technical_aligned:
                return (
                    True,
                    f"technical_confidence={self._input_technical_confidence:.2f} >= {TECHNICAL_CONFIDENCE_THRESHOLD} "
                    f"but no technical-aligned candidate (alignment >= {TECHNICAL_ALIGNMENT_FLOOR}). "
                    "Must include at least one technical-aligned strategy.",
                )

        # Bear Critique: 모든 candidate가 downside 분석 없이 낙관적이면 재시도
        # failure_conditions가 너무 적으면 단방향 낙관론으로 간주
        total_failure_conditions = sum(
            len(c.get("failure_conditions", [])) for c in candidates
        )
        if len(candidates) > 0 and total_failure_conditions < len(candidates):
            return (
                True,
                "Bear critique failed: each strategy must have at least 1 failure_condition. "
                "Consider downside risks, regime reversals, or liquidity constraints.",
            )

        # Bear Critique: regime_fit이 모두 0.85 이상이면 지나치게 낙관적 — 재시도
        if len(candidates) >= 2:
            all_high_regime_fit = all(c.get("regime_fit", 0.0) >= 0.85 for c in candidates)
            if all_high_regime_fit:
                return (
                    True,
                    "Bear critique failed: all candidates have regime_fit >= 0.85. "
                    "At least one candidate should reflect a more conservative/hedged posture.",
                )

        return False, ""

    def to_dave_packet(self, bob_output: dict, date: str) -> dict:
        """Bob strategy → Dave risk packet."""
        selected = bob_output.get("selected_for_review", [])
        candidates = {c["name"]: c for c in bob_output.get("candidate_strategies", [])}

        if selected and selected[0] in candidates:
            strategy = candidates[selected[0]]
        elif candidates:
            strategy = list(candidates.values())[0]
        else:
            return {}

        packet = BobToDavePacket(
            source_agent="Bob",
            target_agent="Dave",
            date=date,
            strategy_name=strategy["name"],
            expected_turnover=strategy.get("sim_metrics", {}).get("turnover", 0.3),
            sector_bias=[],
            expected_vol_profile=strategy.get("sim_metrics", {}).get("mdd", 0.1),
            failure_conditions=strategy.get("failure_conditions", []),
            strategy_confidence=strategy.get("confidence", 0.5),
            technical_alignment=strategy.get("technical_alignment", 0.5),
        )
        return packet.model_dump()

    def to_execution_packet(self, bob_output: dict, date: str) -> dict:
        """Bob strategy → Execution feasibility packet.
        transforms/bob_to_execution.py의 로직에 위임 (urgency/hedge는 전략 특성 기반).
        """
        from transforms.bob_to_execution import transform_bob_to_execution
        return transform_bob_to_execution(bob_output, date)

    def _enrich_with_real_sim_metrics(self, output: dict) -> dict:
        """
        LLM이 생성한 sim_metrics를 실제 백테스트 결과로 교체.
        백테스트 실패 시 LLM 값 유지 (fallback).
        """
        candidates = output.get("candidate_strategies", [])
        enriched = []
        for c in candidates:
            try:
                real_metrics = self._trading_engine.run_strategy(
                    strategy_type=c.get("type", "momentum"),
                    sim_window=c.get("sim_window", {}),
                    regime_fit=float(c.get("regime_fit", 0.5)),
                    technical_alignment=float(c.get("technical_alignment", 0.5)),
                )
                if real_metrics is not None:
                    c = dict(c)
                    # data_source 필드: synthetic이면 순환 논리 경고
                    data_source = real_metrics.pop("data_source", "synthetic")
                    c["sim_metrics"] = real_metrics
                    if data_source == "synthetic":
                        c["sim_note"] = "synthetic_data: metrics derived from LLM quality estimates, not market data"
                    else:
                        c.pop("sim_note", None)  # real data면 경고 제거
            except Exception:
                pass  # 백테스트 실패 시 LLM 값 유지
            enriched.append(c)
        output = dict(output)
        output["candidate_strategies"] = enriched
        return output
