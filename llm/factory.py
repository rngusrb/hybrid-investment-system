"""LLM Provider Factory — config 한 줄로 provider 교체."""

import os
from pathlib import Path
from typing import Optional

import yaml

from llm.base import BaseLLMProvider

_CONFIG_ROOT = Path(__file__).parent.parent.resolve()


def create_provider(config_path: str = "config/system_config.yaml", node_role: str = "decision") -> BaseLLMProvider:
    """system_config.yaml을 읽어 적절한 provider 인스턴스 반환.

    Args:
        config_path: YAML 설정 파일 경로 (절대경로 또는 project root 기준 상대경로)
        node_role: 노드 역할 — "decision"(heavy model) 또는 "analyst"(light model).
                   model_roles가 config에 없으면 기존 model 필드로 fallback.
    """
    p = Path(config_path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        # 상대경로는 project root 기준으로 resolve — 루트 탈출 차단
        resolved = (_CONFIG_ROOT / p).resolve()
        if not str(resolved).startswith(str(_CONFIG_ROOT)):
            raise ValueError(f"Path traversal detected in config_path: {config_path}")
    with open(resolved, "r") as f:
        config = yaml.safe_load(f)

    llm_config = config.get("llm", {})
    provider_name = llm_config.get("provider", "anthropic")
    temperature = llm_config.get("temperature", 0.2)
    max_tokens = llm_config.get("max_tokens", 4096)

    # model_roles가 있으면 node_role에 맞는 모델 선택, 없으면 기존 model 필드 fallback
    model_roles = llm_config.get("model_roles", None)
    if model_roles and node_role in model_roles:
        model = model_roles[node_role]
    else:
        model = llm_config.get("model", None)

    return _build_provider(provider_name, model=model, temperature=temperature, max_tokens=max_tokens)


def _build_provider(provider_name: str, model: Optional[str] = None, **kwargs) -> BaseLLMProvider:
    """provider_name에 해당하는 provider 인스턴스 생성."""
    if provider_name == "anthropic":
        from llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model or "claude-opus-4-5", **kwargs)
    elif provider_name == "openai":
        from llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model or "gpt-4o", **kwargs)
    elif provider_name == "ollama":
        from llm.providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=model or "llama3.1", **kwargs)
    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. Must be one of: anthropic, openai, ollama"
        )
