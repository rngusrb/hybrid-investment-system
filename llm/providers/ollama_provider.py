"""
llm.providers.ollama_provider - Ollama local model provider implementation.
Supports locally-hosted open-source models via the Ollama runtime.
"""

import json
from typing import List, Optional

from llm.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """LLM provider backed by a locally-running Ollama instance."""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434", **kwargs):
        try:
            import ollama
            self._ollama = ollama
        except ImportError:
            self._ollama = None
        self.model = model
        self.base_url = base_url
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
        if self._ollama is None:
            raise RuntimeError("ollama package not installed")

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

        options = {"temperature": temperature, "num_predict": max_tokens}
        response = self._ollama.chat(
            model=self.model,
            messages=all_messages,
            options=options,
        )
        return response["message"]["content"]

    def name(self) -> str:
        return "ollama"
