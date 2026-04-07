"""Dave — Risk Control Analyst agent."""
import json
from typing import List
from agents.base_agent import BaseAgent
from schemas.dave_schema import DaveOutput
from pydantic import ValidationError


class DaveAgent(BaseAgent):
    """
    전략을 제약과 경보가 있는 위험 공간 위에 올리는 agent.
    R_score > 0.75이면 즉시 Risk Alert Meeting 트리거.
    """

    RISK_ALERT_THRESHOLD = 0.75

    # R_score 가중치 (config에서 오버라이드 가능)
    DEFAULT_WEIGHTS = {
        "beta": 0.3,
        "illiquidity": 0.25,
        "sector_concentration": 0.25,
        "volatility": 0.2,
    }

    def _validate_output(self, output: dict) -> dict:
        output = dict(output)

        # 1. risk_score → 컴포넌트 가중합으로 덮어씀 (LLM 수치 신뢰 안 함)
        components = output.get("risk_components") or {}
        if components:
            output["risk_score"] = self.compute_risk_score(components)

        # 2. risk_level 대소문자 정규화 (LLM이 'MODERATE', 'LOW' 등 반환 시 처리)
        rl = output.get("risk_level", "")
        if isinstance(rl, str):
            output["risk_level"] = rl.lower()

        # 3. stress_test 자동 교정
        stress = output.get("stress_test")
        if isinstance(stress, dict):
            wcd = stress.get("worst_case_drawdown", 0.0)
            try:
                wcd = float(wcd)
                # LLM이 음수(부호 있는 퍼센트) 또는 100 초과(퍼센트 단위) 반환 시 교정
                if wcd < 0:
                    wcd = abs(wcd)
                if wcd > 1.0:
                    wcd = wcd / 100.0
                stress["worst_case_drawdown"] = min(max(wcd, 0.0), 1.0)
            except (TypeError, ValueError):
                stress["worst_case_drawdown"] = 0.1
            output["stress_test"] = stress

        # 4. risk_constraints 퍼센트 단위 자동 교정 (LLM이 30 대신 0.3으로 써야 하는데 30 씀)
        rc = output.get("risk_constraints")
        if isinstance(rc, dict):
            for field in ("max_single_sector_weight", "max_gross_exposure"):
                v = rc.get(field)
                if v is not None:
                    try:
                        v = float(v)
                        if v > 1.0:
                            rc[field] = v / 100.0
                    except (TypeError, ValueError):
                        pass
            output["risk_constraints"] = rc

        validated = DaveOutput(**output)
        # trigger_risk_alert_meeting이 threshold 기준과 일치하는지 강제
        if validated.risk_score > self.RISK_ALERT_THRESHOLD and not validated.trigger_risk_alert_meeting:
            validated = validated.model_copy(update={"trigger_risk_alert_meeting": True})
        return validated.model_dump()

    def _build_prompt(self, input_packet: dict, state: dict) -> List[dict]:
        content = f"Strategy Risk Assessment Input:\n{json.dumps(input_packet, indent=2, default=str)}"
        return [{"role": "user", "content": content}]

    def compute_risk_score(self, components: dict) -> float:
        """R_score = w1*beta + w2*illiquidity + w3*sector_concentration + w4*volatility
        각 component를 [0,1]로 clamp해 가중합이 항상 [0,1] 범위를 보장.
        """
        weights = self.config.get("risk_weights", self.DEFAULT_WEIGHTS)

        def _clamp(v: float) -> float:
            return max(0.0, min(1.0, float(v)))

        score = (
            weights.get("beta", 0.3) * _clamp(components.get("beta", 0.0))
            + weights.get("illiquidity", 0.25) * _clamp(components.get("illiquidity", 0.0))
            + weights.get("sector_concentration", 0.25) * _clamp(components.get("sector_concentration", 0.0))
            + weights.get("volatility", 0.2) * _clamp(components.get("volatility", 0.0))
        )
        return min(score, 1.0)

    def _should_retry(self, output: dict, attempt: int) -> tuple:
        """
        _validate_output에서 자동 교정 후에도 처리 불가한 케이스만 재시도.
        - risk_constraints 자체가 없는 경우
        - risk_components 자체가 없는 경우 (4개 필드 모두 없음)
        """
        rc = output.get("risk_constraints")
        if not rc or not isinstance(rc, dict) or "max_gross_exposure" not in rc:
            return True, "risk_constraints missing — must include max_single_sector_weight, max_beta, max_gross_exposure"

        components = output.get("risk_components") or {}
        if not any(k in components for k in ("beta", "illiquidity", "sector_concentration", "volatility")):
            return True, "risk_components missing required fields: beta, illiquidity, sector_concentration, volatility"

        return False, ""
