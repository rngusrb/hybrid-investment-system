"""
Calibration Layer — score drift 방지.
모든 score 기반 specialist output은 상위 단계 전달 전 이 calibrator를 통과해야 함.

4가지 calibration 방법:
1. rolling_standardization: agent별 rolling window에서 z-score 정규화
2. sector_relative: sector 평균 대비 상대값으로 정규화
3. shrinkage: confidence 낮으면 neutral(0.5) 방향으로 shrinkage
4. clipping: outlier를 [clip_min, clip_max]로 clamp
"""
import numpy as np
from typing import Optional, List, Dict
from collections import deque
from schemas.audit_schema import CalibrationLog


class AgentCalibrator:
    """
    agent별 rolling history를 유지하여 score drift 방지.
    각 agent가 CalibrationLog를 반환하여 상위 단계에서 추적 가능.
    """

    def __init__(
        self,
        agent_name: str,
        rolling_window: int = 20,
        shrinkage_factor: float = 0.3,
        clip_range: tuple = (0.0, 1.0),
        neutral_value: float = 0.5,
    ):
        self.agent_name = agent_name
        self.rolling_window = rolling_window
        self.shrinkage_factor = shrinkage_factor
        self.clip_min, self.clip_max = clip_range
        self.neutral_value = neutral_value
        self._history: Dict[str, deque] = {}  # field_name → deque of values

    def calibrate(
        self,
        field_name: str,
        raw_value: float,
        date: str,
        confidence: float = 1.0,
        method: str = "rolling_std",
    ) -> tuple:
        """
        단일 값 calibration.
        Returns: (calibrated_value, CalibrationLog)
        """
        if field_name not in self._history:
            self._history[field_name] = deque(maxlen=self.rolling_window)

        history = self._history[field_name]
        was_clipped = False
        was_shrunk = False
        calibrated = raw_value

        if method == "rolling_std" and len(history) >= 3:
            mean = np.mean(history)
            std = np.std(history) or 1.0
            calibrated = (raw_value - mean) / std
            # z-score를 [0, 1]로 rescale (sigmoid)
            calibrated = 1.0 / (1.0 + np.exp(-calibrated))

        elif method == "shrinkage":
            # confidence 낮으면 neutral 방향으로 shrinkage
            shrink = self.shrinkage_factor * (1.0 - confidence)
            calibrated = raw_value * (1.0 - shrink) + self.neutral_value * shrink
            was_shrunk = shrink > 0.01

        elif method == "clipping":
            clipped = np.clip(raw_value, self.clip_min, self.clip_max)
            was_clipped = bool(clipped != raw_value)
            calibrated = float(clipped)

        elif method == "sector_relative":
            # sector 평균 대비 상대값 (history를 sector samples로 사용)
            if len(history) >= 2:
                sector_mean = np.mean(history)
                calibrated = raw_value - sector_mean + 0.5  # center at 0.5
                calibrated = float(np.clip(calibrated, 0.0, 1.0))

        # 항상 clipping 마지막 적용 (안전장치)
        calibrated = float(np.clip(calibrated, self.clip_min, self.clip_max))

        # history 업데이트
        history.append(raw_value)

        log = CalibrationLog(
            date=date,
            agent=self.agent_name,
            field_name=field_name,
            raw_value=raw_value,
            calibrated_value=calibrated,
            method=method,
            was_clipped=was_clipped,
            was_shrunk=was_shrunk,
        )
        return calibrated, log

    def calibrate_packet(
        self,
        packet: dict,
        date: str,
        score_fields: List[str],
        confidence: float = 1.0,
        method: str = "rolling_std",
    ) -> tuple:
        """
        packet의 여러 score 필드를 한 번에 calibration.
        Returns: (calibrated_packet, List[CalibrationLog])
        """
        result = dict(packet)
        logs = []
        for field in score_fields:
            if field in result and isinstance(result[field], (int, float)):
                cal_val, log = self.calibrate(field, float(result[field]), date, confidence, method)
                result[field] = cal_val
                logs.append(log)
        return result, logs

    def reset_history(self, field_name: Optional[str] = None):
        """history 초기화 (테스트용)."""
        if field_name:
            self._history.pop(field_name, None)
        else:
            self._history.clear()
