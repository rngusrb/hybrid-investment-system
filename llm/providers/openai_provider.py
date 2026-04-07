"""
llm.providers.openai_provider - OpenAI GPT provider implementation.
"""

import json
import os
from typing import List, Optional

from llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """LLM provider backed by OpenAI GPT models."""

    def __init__(self, model: str = "gpt-4o", **kwargs):
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "OPENAI_API_KEY is not set. "
                    "Copy .env.example to .env and fill in the key."
                )
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            self._client = None
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
            raise RuntimeError("openai package not installed")

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})

        if response_format:
            schema_instruction = (
                f"\n\nRespond ONLY with valid JSON matching this schema:\n"
                f"{json.dumps(response_format, indent=2)}"
            )
            if all_messages and all_messages[0]["role"] == "system":
                all_messages[0]["content"] += schema_instruction
            else:
                all_messages.insert(0, {"role": "system", "content": schema_instruction})

        all_messages.extend(messages)

        create_kwargs = dict(
            model=self.model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # OpenAI JSON mode 지원
        if response_format:
            create_kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**create_kwargs)
        return response.choices[0].message.content

    def name(self) -> str:
        return "openai"
