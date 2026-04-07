"""
llm.providers.anthropic_provider - Anthropic Claude provider implementation.
"""

import json
import os
from typing import List, Optional

from llm.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """LLM provider backed by Anthropic Claude models."""

    def __init__(self, model: str = "claude-opus-4-5", **kwargs):
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Copy .env.example to .env and fill in the key."
                )
            self._client = anthropic.Anthropic(api_key=api_key)
            self._anthropic_module = anthropic
        except ImportError:
            self._client = None
            self._anthropic_module = None
        self.model = model
        self.kwargs = kwargs

    def chat(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        response_format: Optional[dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """동기 chat completion. 항상 문자열 반환."""
        if self._client is None:
            raise RuntimeError("anthropic package not installed")

        # response_format이 있으면 JSON 응답 강제
        system_prompt = system or ""
        if response_format:
            system_prompt += (
                f"\n\nRespond ONLY with valid JSON matching this schema:\n"
                f"{json.dumps(response_format, indent=2)}"
            )

        # system이 빈 문자열이면 NOT_GIVEN 사용
        if system_prompt:
            system_arg = system_prompt
        else:
            try:
                import anthropic as _anthropic
                system_arg = _anthropic.NOT_GIVEN
            except ImportError:
                system_arg = None

        create_kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            temperature=temperature,
        )
        if system_arg is not None and not (hasattr(system_arg, '__class__') and system_arg.__class__.__name__ == 'NotGiven'):
            create_kwargs["system"] = system_arg
        elif system_prompt:
            create_kwargs["system"] = system_prompt

        response = self._client.messages.create(**create_kwargs)
        return response.content[0].text

    def name(self) -> str:
        return "anthropic"
