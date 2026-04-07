"""BaseLLMProvider — 모든 LLM provider가 구현해야 하는 ABC."""
from abc import ABC, abstractmethod
from typing import Optional, List


class BaseLLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        response_format: Optional[dict] = None,  # JSON schema 강제용
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """동기 chat completion. 항상 문자열 반환."""
        ...

    @abstractmethod
    def name(self) -> str:
        """provider 식별자 반환 (예: 'anthropic', 'openai', 'ollama')"""
        ...

    def chat_json(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        json_schema: Optional[dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """JSON 응답 강제 chat. response_format으로 schema 전달."""
        return self.chat(
            messages=messages,
            system=system,
            response_format=json_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )
