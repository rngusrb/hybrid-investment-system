"""
BaseAgent — 모든 agent의 공통 로직.
retry, schema validation, logging, calibration 통과 포함.
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Type, Any
from pydantic import BaseModel, ValidationError
from llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# LLM 응답 최대 허용 크기 (50KB). 이 이상이면 prompt injection 또는 비정상 응답으로 간주.
_MAX_RESPONSE_BYTES = 50_000

# 시스템 프롬프트 경로 허용 루트 (이 디렉토리 밖은 차단)
_PROMPT_ROOT = Path(__file__).parent.parent.resolve()


class BaseAgent:
    def __init__(self, llm: BaseLLMProvider, config: dict):
        self.llm = llm
        self.config = config
        self.max_retries = config.get("max_retries", 3)
        self.agent_name = config.get("name", "Agent")

    def run(self, input_packet: dict, state: dict) -> dict:
        """
        1. system prompt 로드
        2. retrieval context 붙이기 (있으면)
        3. LLM 호출
        4. schema validation
        5. 실패 시 retry (max_retries까지)
        6. 결과 반환
        """
        system_prompt = self._load_system_prompt()
        messages = self._build_prompt(input_packet, state)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                raw = self.llm.chat(
                    messages=messages,
                    system=system_prompt,
                    temperature=self.config.get("temperature", 0.2),
                    max_tokens=self.config.get("max_tokens", 4096),
                )
                output = self._parse_output(raw)
                validated = self._validate_output(output)

                should_retry, retry_reason = self._should_retry(validated, attempt)
                if should_retry:
                    logger.warning(
                        f"{self.agent_name} retry {attempt + 1}/{self.max_retries}: {retry_reason}"
                    )
                    messages = self._build_retry_prompt(messages, retry_reason)
                    last_error = retry_reason
                    continue

                return validated

            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                logger.warning(
                    f"{self.agent_name} attempt {attempt + 1} failed: {last_error}"
                )
                if attempt < self.max_retries - 1:
                    messages = self._build_retry_prompt(messages, last_error)

        raise RuntimeError(
            f"{self.agent_name} failed after {self.max_retries} retries. Last error: {last_error}"
        )

    def _load_system_prompt(self) -> str:
        prompt_path = self.config.get("system_prompt_path", "")
        if not prompt_path:
            return f"You are {self.agent_name}."
        try:
            p = Path(prompt_path)
            if p.is_absolute():
                resolved = p.resolve()
            else:
                resolved = (_PROMPT_ROOT / p).resolve()
                if not str(resolved).startswith(str(_PROMPT_ROOT)):
                    raise ValueError(
                        f"Path traversal detected in system_prompt_path: {prompt_path}"
                    )
            with open(resolved, "r") as f:
                return f.read()
        except (FileNotFoundError, IOError):
            return f"You are {self.agent_name}."

    def _build_prompt(self, input_packet: dict, state: dict) -> List[dict]:
        """기본 구현 — subclass에서 override."""
        content = f"Input:\n{json.dumps(input_packet, indent=2, default=str)}"
        return [{"role": "user", "content": content}]

    def _parse_output(self, raw: str) -> dict:
        """JSON 파싱. 실패 시 ValueError."""
        if len(raw.encode("utf-8")) > _MAX_RESPONSE_BYTES:
            raise ValueError(
                f"LLM response exceeds maximum allowed size "
                f"({len(raw.encode('utf-8'))} bytes > {_MAX_RESPONSE_BYTES}). "
                "Possible prompt injection or runaway generation."
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 첫 번째 '{' 부터 마지막 '}' 까지만 추출 (크기 재확인 포함)
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = raw[start : end + 1]
                return json.loads(candidate)
            raise ValueError(f"Cannot parse JSON from: {raw[:200]}")

    def _validate_output(self, output: dict) -> dict:
        """기본 구현 — subclass에서 schema class로 override."""
        return output

    def _should_retry(self, output: dict, attempt: int) -> tuple:
        """
        LLM 판단 기반 재시도 여부 결정.
        confidence가 threshold 미달이면 재시도.
        """
        confidence_floor = self.config.get("agent_confidence_floor", 0.45)
        confidence = output.get("confidence", output.get("regime_confidence", 1.0))

        if isinstance(confidence, (int, float)) and confidence < confidence_floor:
            return True, f"Confidence {confidence} below floor {confidence_floor}"
        return False, ""

    def _build_retry_prompt(self, messages: List[dict], error_reason: str) -> List[dict]:
        """재시도 시 에러 이유를 추가한 prompt."""
        retry_msg = {
            "role": "user",
            "content": (
                f"Your previous response had issues: {error_reason}\n"
                "Please try again with higher confidence and valid JSON output."
            ),
        }
        return messages + [retry_msg]
