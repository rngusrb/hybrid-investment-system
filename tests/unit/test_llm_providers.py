"""
tests.unit.test_llm_providers - Unit tests for LLM provider implementations.
실제 API 호출 없이 unittest.mock으로 모든 동작 검증.

openai, ollama 패키지가 설치되지 않은 환경에서도 동작하도록
sys.modules에 mock을 등록하는 방식 사용.
"""

import json
import os
import sys
import importlib
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# 패키지 미설치 환경 대응: sys.modules mock 헬퍼
# ---------------------------------------------------------------------------

def _register_mock_module(module_name: str) -> MagicMock:
    """sys.modules에 mock 모듈을 등록하고 반환. 이미 있으면 기존 것 반환."""
    if module_name not in sys.modules:
        mock_mod = MagicMock()
        sys.modules[module_name] = mock_mod
        return mock_mod
    return sys.modules[module_name]


def _unregister_mock_module(module_name: str):
    """테스트 후 sys.modules에서 mock 모듈 제거."""
    sys.modules.pop(module_name, None)


# openai와 ollama가 없으면 미리 mock으로 등록
_OPENAI_REAL = "openai" in sys.modules
_OLLAMA_REAL = "ollama" in sys.modules

if not _OPENAI_REAL:
    _openai_mock = MagicMock()
    _openai_mock_client_cls = MagicMock()
    _openai_mock.OpenAI = _openai_mock_client_cls
    sys.modules["openai"] = _openai_mock

if not _OLLAMA_REAL:
    _ollama_mock = MagicMock()
    sys.modules["ollama"] = _ollama_mock


# ---------------------------------------------------------------------------
# Provider 모듈을 깨끗하게 리로드하기 위한 헬퍼
# ---------------------------------------------------------------------------

def _reload_provider(module_path: str):
    """provider 모듈을 sys.modules에서 제거 후 재임포트."""
    sys.modules.pop(module_path, None)


# ---------------------------------------------------------------------------
# 1. BaseLLMProvider ABC 검증
# ---------------------------------------------------------------------------

class TestBaseLLMProvider:
    """BaseLLMProvider가 올바른 ABC인지 검증."""

    def test_cannot_instantiate_directly(self):
        """BaseLLMProvider를 직접 인스턴스화하면 TypeError 발생."""
        from llm.base import BaseLLMProvider
        with pytest.raises(TypeError):
            BaseLLMProvider()

    def test_subclass_without_chat_raises(self):
        """chat()을 구현하지 않은 서브클래스는 인스턴스화 불가."""
        from llm.base import BaseLLMProvider

        class IncompleteProvider(BaseLLMProvider):
            def name(self) -> str:
                return "incomplete"
            # chat() 미구현

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_without_name_raises(self):
        """name()을 구현하지 않은 서브클래스는 인스턴스화 불가."""
        from llm.base import BaseLLMProvider

        class IncompleteProvider(BaseLLMProvider):
            def chat(self, messages, system=None, response_format=None,
                     temperature=0.2, max_tokens=4096) -> str:
                return ""
            # name() 미구현

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_passes_abc(self):
        """chat()과 name() 모두 구현한 서브클래스는 정상 인스턴스화."""
        from llm.base import BaseLLMProvider

        class ConcreteProvider(BaseLLMProvider):
            def chat(self, messages, system=None, response_format=None,
                     temperature=0.2, max_tokens=4096) -> str:
                return "response"

            def name(self) -> str:
                return "concrete"

        provider = ConcreteProvider()
        assert provider.name() == "concrete"

    def test_chat_json_delegates_to_chat(self):
        """chat_json()이 chat(response_format=...)으로 위임되는지 확인."""
        from llm.base import BaseLLMProvider

        class ConcreteProvider(BaseLLMProvider):
            def chat(self, messages, system=None, response_format=None,
                     temperature=0.2, max_tokens=4096) -> str:
                return json.dumps({"delegated": True, "schema": response_format})

            def name(self) -> str:
                return "concrete"

        provider = ConcreteProvider()
        schema = {"type": "object", "properties": {"key": {"type": "string"}}}
        result = provider.chat_json(
            messages=[{"role": "user", "content": "hello"}],
            system="sys",
            json_schema=schema,
            temperature=0.5,
            max_tokens=1000,
        )
        parsed = json.loads(result)
        assert parsed["delegated"] is True
        assert parsed["schema"] == schema

    def test_chat_json_with_none_schema(self):
        """chat_json()에 schema=None이면 response_format=None으로 위임."""
        from llm.base import BaseLLMProvider

        class ConcreteProvider(BaseLLMProvider):
            def chat(self, messages, system=None, response_format=None,
                     temperature=0.2, max_tokens=4096) -> str:
                assert response_format is None
                return "ok"

            def name(self) -> str:
                return "concrete"

        provider = ConcreteProvider()
        result = provider.chat_json(
            messages=[{"role": "user", "content": "hello"}],
            json_schema=None,
        )
        assert result == "ok"


# ---------------------------------------------------------------------------
# 2. AnthropicProvider 테스트
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    """AnthropicProvider 핵심 동작 검증."""

    def _make_mock_client(self, response_text: str = '{"result": "ok"}'):
        """anthropic client mock 생성 헬퍼."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_text)]
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def _make_provider(self, model: str = "claude-opus-4-5"):
        """AnthropicProvider 인스턴스를 mock client와 함께 생성."""
        # anthropic은 설치되어 있으므로 patch 사용
        with patch("anthropic.Anthropic"):
            from llm.providers import anthropic_provider
            # 모듈 캐시 무효화 후 재임포트
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model=model)
        return provider

    def test_name_returns_anthropic(self):
        """name()이 'anthropic'을 반환해야 함."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            assert provider.name() == "anthropic"

    def test_chat_basic(self):
        """기본 chat() 호출이 문자열을 반환하는지 확인."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-opus-4-5")
            provider._client = self._make_mock_client("hello world")

            result = provider.chat(
                messages=[{"role": "user", "content": "test"}],
            )
            assert result == "hello world"

    def test_chat_with_response_format_injects_json_instruction(self):
        """response_format이 주어지면 system prompt에 JSON schema 지시가 삽입됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-opus-4-5")
            mock_client = self._make_mock_client('{"result": "ok"}')
            provider._client = mock_client

            schema = {"type": "object", "properties": {"result": {"type": "string"}}}
            result = provider.chat(
                messages=[{"role": "user", "content": "test"}],
                response_format=schema,
            )
            assert result == '{"result": "ok"}'

            call_kwargs = mock_client.messages.create.call_args
            # system 인자에 JSON 지시가 포함됐는지 확인
            assert "JSON" in str(call_kwargs)
            assert "properties" in str(call_kwargs)

    def test_chat_with_system_and_response_format(self):
        """system과 response_format 동시 사용 시 system prompt에 모두 포함."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-opus-4-5")
            mock_client = self._make_mock_client('{"key": "value"}')
            provider._client = mock_client

            schema = {"type": "object", "properties": {"key": {"type": "string"}}}
            provider.chat(
                messages=[{"role": "user", "content": "test"}],
                system="You are a helpful assistant.",
                response_format=schema,
            )

            call_kwargs = mock_client.messages.create.call_args
            call_str = str(call_kwargs)
            assert "You are a helpful assistant." in call_str
            assert "JSON" in call_str

    def test_chat_passes_temperature_and_max_tokens(self):
        """temperature와 max_tokens가 API 호출에 전달됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-opus-4-5")
            mock_client = self._make_mock_client("response")
            provider._client = mock_client

            provider.chat(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.7,
                max_tokens=2048,
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 2048

    def test_chat_raises_when_client_none(self):
        """anthropic 패키지 미설치 시 RuntimeError 발생."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            provider._client = None

            with pytest.raises(RuntimeError, match="anthropic package not installed"):
                provider.chat(messages=[{"role": "user", "content": "test"}])

    def test_chat_json_delegates_response_format(self):
        """chat_json()이 chat()의 response_format 파라미터로 위임됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-opus-4-5")
            mock_client = self._make_mock_client('{"x": 1}')
            provider._client = mock_client

            schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
            result = provider.chat_json(
                messages=[{"role": "user", "content": "give me json"}],
                json_schema=schema,
            )
            assert result == '{"x": 1}'

            call_kwargs = mock_client.messages.create.call_args
            assert "JSON" in str(call_kwargs)

    def test_model_attribute_stored(self):
        """생성자에 전달된 model이 저장됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
            assert provider.model == "claude-3-5-sonnet-20241022"

    def test_chat_passes_messages(self):
        """messages가 API에 그대로 전달됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            mock_client = self._make_mock_client("ok")
            provider._client = mock_client

            messages = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "bye"},
            ]
            provider.chat(messages=messages)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["messages"] == messages


# ---------------------------------------------------------------------------
# 3. OpenAIProvider 테스트
# ---------------------------------------------------------------------------

def _make_openai_provider(model: str = "gpt-4o"):
    """
    OpenAIProvider를 mock openai 모듈로 생성하는 헬퍼.
    openai 패키지 미설치 환경 대응: sys.modules에 mock을 직접 등록.
    """
    # sys.modules에서 캐시 제거해서 fresh import 보장
    sys.modules.pop("llm.providers.openai_provider", None)

    # openai mock 설정
    mock_openai_module = MagicMock()
    mock_client_instance = MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client_instance
    sys.modules["openai"] = mock_openai_module

    from llm.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(model=model)
    return provider, mock_client_instance


class TestOpenAIProvider:
    """OpenAIProvider 핵심 동작 검증."""

    def _setup(self, response_text: str = '{"result": "ok"}', model: str = "gpt-4o"):
        """provider와 mock client를 함께 설정."""
        provider, mock_client = _make_openai_provider(model=model)

        mock_choice = MagicMock()
        mock_choice.message.content = response_text
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        return provider, mock_client

    def test_name_returns_openai(self):
        """name()이 'openai'를 반환해야 함."""
        provider, _ = self._setup()
        assert provider.name() == "openai"

    def test_chat_basic(self):
        """기본 chat() 호출이 문자열을 반환하는지 확인."""
        provider, mock_client = self._setup(response_text="hello")

        result = provider.chat(
            messages=[{"role": "user", "content": "test"}],
        )
        assert result == "hello"

    def test_chat_with_response_format_injects_json_instruction(self):
        """response_format이 주어지면 system message에 JSON schema 지시가 삽입됨."""
        provider, mock_client = self._setup(response_text='{"answer": 42}')

        schema = {"type": "object", "properties": {"answer": {"type": "integer"}}}
        result = provider.chat(
            messages=[{"role": "user", "content": "test"}],
            response_format=schema,
        )
        assert result == '{"answer": 42}'

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert messages_sent[0]["role"] == "system"
        assert "JSON" in messages_sent[0]["content"]
        assert "properties" in messages_sent[0]["content"]

    def test_chat_with_response_format_sets_json_mode(self):
        """response_format이 있으면 OpenAI json_object mode가 활성화됨."""
        provider, mock_client = self._setup(response_text='{}')

        schema = {"type": "object"}
        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            response_format=schema,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    def test_chat_without_response_format_no_json_mode(self):
        """response_format 없으면 json_object mode가 설정되지 않음."""
        provider, mock_client = self._setup(response_text="plain text")

        provider.chat(
            messages=[{"role": "user", "content": "test"}],
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "response_format" not in call_kwargs

    def test_chat_with_system_prepends_system_message(self):
        """system 파라미터가 messages 앞에 system role로 추가됨."""
        provider, mock_client = self._setup(response_text="ok")

        provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            system="You are a helpful assistant.",
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert messages_sent[0]["role"] == "system"
        assert messages_sent[0]["content"] == "You are a helpful assistant."

    def test_chat_with_system_and_response_format_merges(self):
        """system + response_format 동시 사용 시 system message에 JSON 지시 추가됨."""
        provider, mock_client = self._setup(response_text='{"ok": true}')

        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            system="Be concise.",
            response_format=schema,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert messages_sent[0]["role"] == "system"
        assert "Be concise." in messages_sent[0]["content"]
        assert "JSON" in messages_sent[0]["content"]

    def test_chat_passes_temperature_and_max_tokens(self):
        """temperature와 max_tokens가 API 호출에 전달됨."""
        provider, mock_client = self._setup(response_text="ok")

        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.9,
            max_tokens=512,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 512

    def test_chat_raises_when_client_none(self):
        """openai 패키지 미설치 시 RuntimeError 발생."""
        provider, _ = self._setup()
        provider._client = None

        with pytest.raises(RuntimeError, match="openai package not installed"):
            provider.chat(messages=[{"role": "user", "content": "test"}])

    def test_model_attribute_stored(self):
        """생성자에 전달된 model이 저장됨."""
        provider, _ = self._setup(model="gpt-3.5-turbo")
        assert provider.model == "gpt-3.5-turbo"


# ---------------------------------------------------------------------------
# 4. OllamaProvider 테스트
# ---------------------------------------------------------------------------

def _make_ollama_provider(model: str = "llama3.1"):
    """
    OllamaProvider를 mock ollama 모듈로 생성하는 헬퍼.
    ollama 패키지 미설치 환경 대응.
    """
    sys.modules.pop("llm.providers.ollama_provider", None)

    mock_ollama_module = MagicMock()
    sys.modules["ollama"] = mock_ollama_module

    from llm.providers.ollama_provider import OllamaProvider
    provider = OllamaProvider(model=model)
    provider._ollama = mock_ollama_module
    return provider, mock_ollama_module


class TestOllamaProvider:
    """OllamaProvider 핵심 동작 검증."""

    def _setup(self, response_text: str = '{"result": "ok"}', model: str = "llama3.1"):
        provider, mock_ollama = _make_ollama_provider(model=model)
        mock_ollama.chat.return_value = {"message": {"content": response_text}}
        return provider, mock_ollama

    def test_name_returns_ollama(self):
        """name()이 'ollama'를 반환해야 함."""
        provider, _ = self._setup()
        assert provider.name() == "ollama"

    def test_chat_basic(self):
        """기본 chat() 호출이 문자열을 반환하는지 확인."""
        provider, _ = self._setup(response_text="hello world")

        result = provider.chat(
            messages=[{"role": "user", "content": "test"}],
        )
        assert result == "hello world"

    def test_chat_with_response_format_injects_json_instruction(self):
        """response_format이 주어지면 system message에 JSON schema 지시가 삽입됨."""
        provider, mock_ollama = self._setup(response_text='{"answer": "yes"}')

        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        result = provider.chat(
            messages=[{"role": "user", "content": "test"}],
            response_format=schema,
        )
        assert result == '{"answer": "yes"}'

        call_kwargs = mock_ollama.chat.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert messages_sent[0]["role"] == "system"
        assert "JSON" in messages_sent[0]["content"]
        assert "properties" in messages_sent[0]["content"]

    def test_chat_with_system_and_response_format(self):
        """system + response_format 동시 사용 시 system message에 모두 포함됨."""
        provider, mock_ollama = self._setup(response_text='{"ok": true}')

        schema = {"type": "object"}
        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            system="You are a local model.",
            response_format=schema,
        )

        call_kwargs = mock_ollama.chat.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert messages_sent[0]["role"] == "system"
        assert "You are a local model." in messages_sent[0]["content"]
        assert "JSON" in messages_sent[0]["content"]

    def test_chat_passes_temperature_and_max_tokens_in_options(self):
        """temperature와 max_tokens가 options로 전달됨."""
        provider, mock_ollama = self._setup(response_text="ok")

        provider.chat(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.8,
            max_tokens=256,
        )

        call_kwargs = mock_ollama.chat.call_args[1]
        options = call_kwargs["options"]
        assert options["temperature"] == 0.8
        assert options["num_predict"] == 256

    def test_chat_raises_when_ollama_none(self):
        """ollama 패키지 미설치 시 RuntimeError 발생."""
        provider, _ = self._setup()
        provider._ollama = None

        with pytest.raises(RuntimeError, match="ollama package not installed"):
            provider.chat(messages=[{"role": "user", "content": "test"}])

    def test_model_and_base_url_stored(self):
        """생성자에 전달된 model과 base_url이 저장됨."""
        sys.modules.pop("llm.providers.ollama_provider", None)
        mock_ollama_module = MagicMock()
        sys.modules["ollama"] = mock_ollama_module

        from llm.providers.ollama_provider import OllamaProvider
        provider = OllamaProvider(model="mistral", base_url="http://localhost:9999")
        assert provider.model == "mistral"
        assert provider.base_url == "http://localhost:9999"

    def test_chat_without_system_no_system_message(self):
        """system이 없으면 system role 메시지가 추가되지 않음."""
        provider, mock_ollama = self._setup(response_text="ok")

        user_messages = [{"role": "user", "content": "hello"}]
        provider.chat(messages=user_messages)

        call_kwargs = mock_ollama.chat.call_args[1]
        messages_sent = call_kwargs["messages"]
        assert all(m["role"] != "system" for m in messages_sent)
        assert messages_sent == user_messages


# ---------------------------------------------------------------------------
# 5. LLM Factory 테스트
# ---------------------------------------------------------------------------

class TestLLMFactory:
    """factory.create_provider()와 _build_provider() 검증."""

    def setup_method(self):
        """각 테스트 전 factory 모듈 캐시 초기화."""
        sys.modules.pop("llm.factory", None)
        sys.modules.pop("llm.providers.anthropic_provider", None)
        sys.modules.pop("llm.providers.openai_provider", None)
        sys.modules.pop("llm.providers.ollama_provider", None)

        # openai mock 재등록
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = MagicMock()
        sys.modules["openai"] = mock_openai

        # ollama mock 재등록
        mock_ollama = MagicMock()
        sys.modules["ollama"] = mock_ollama

    def test_build_provider_anthropic(self):
        """provider='anthropic'이면 AnthropicProvider 인스턴스 반환."""
        with patch("anthropic.Anthropic"):
            from llm.factory import _build_provider
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = _build_provider("anthropic", model="claude-opus-4-5")
            assert isinstance(provider, AnthropicProvider)

    def test_build_provider_openai(self):
        """provider='openai'이면 OpenAIProvider 인스턴스 반환."""
        from llm.factory import _build_provider
        from llm.providers.openai_provider import OpenAIProvider
        provider = _build_provider("openai", model="gpt-4o")
        assert isinstance(provider, OpenAIProvider)

    def test_build_provider_ollama(self):
        """provider='ollama'이면 OllamaProvider 인스턴스 반환."""
        from llm.factory import _build_provider
        from llm.providers.ollama_provider import OllamaProvider
        provider = _build_provider("ollama", model="llama3.1")
        assert isinstance(provider, OllamaProvider)

    def test_build_provider_unknown_raises_value_error(self):
        """알 수 없는 provider 이름이면 ValueError 발생."""
        from llm.factory import _build_provider
        with pytest.raises(ValueError, match="Unknown provider"):
            _build_provider("unknown_llm")

    def test_build_provider_unknown_error_message_contains_valid_options(self):
        """ValueError 메시지에 허용된 provider 목록이 포함됨."""
        from llm.factory import _build_provider
        with pytest.raises(ValueError) as exc_info:
            _build_provider("grok")
        error_msg = str(exc_info.value)
        assert "anthropic" in error_msg
        assert "openai" in error_msg
        assert "ollama" in error_msg

    def test_create_provider_from_config_returns_anthropic(self, tmp_path):
        """config의 provider='anthropic'이면 AnthropicProvider 반환."""
        config_content = """
llm:
  provider: "anthropic"
  model: "claude-opus-4-5"
  temperature: 0.2
  max_tokens: 4096
"""
        config_file = tmp_path / "system_config.yaml"
        config_file.write_text(config_content)

        with patch("anthropic.Anthropic"):
            from llm.factory import create_provider
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = create_provider(config_path=str(config_file))
            assert isinstance(provider, AnthropicProvider)

    def test_create_provider_from_config_returns_openai(self, tmp_path):
        """config의 provider='openai'이면 OpenAIProvider 반환."""
        config_content = """
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.3
  max_tokens: 2048
"""
        config_file = tmp_path / "system_config.yaml"
        config_file.write_text(config_content)

        from llm.factory import create_provider
        from llm.providers.openai_provider import OpenAIProvider
        provider = create_provider(config_path=str(config_file))
        assert isinstance(provider, OpenAIProvider)

    def test_create_provider_from_config_returns_ollama(self, tmp_path):
        """config의 provider='ollama'이면 OllamaProvider 반환."""
        config_content = """
llm:
  provider: "ollama"
  model: "llama3.1"
  temperature: 0.1
  max_tokens: 1024
"""
        config_file = tmp_path / "system_config.yaml"
        config_file.write_text(config_content)

        from llm.factory import create_provider
        from llm.providers.ollama_provider import OllamaProvider
        provider = create_provider(config_path=str(config_file))
        assert isinstance(provider, OllamaProvider)

    def test_create_provider_config_one_line_change(self, tmp_path):
        """config provider 값 한 줄만 바꾸면 provider가 교체됨."""
        config_anthropic = """
llm:
  provider: "anthropic"
  model: "claude-opus-4-5"
"""
        config_openai = """
llm:
  provider: "openai"
  model: "gpt-4o"
"""
        config_file = tmp_path / "system_config.yaml"

        with patch("anthropic.Anthropic"):
            from llm.factory import create_provider
            from llm.providers.anthropic_provider import AnthropicProvider
            from llm.providers.openai_provider import OpenAIProvider

            config_file.write_text(config_anthropic)
            provider_a = create_provider(config_path=str(config_file))
            assert isinstance(provider_a, AnthropicProvider)

            config_file.write_text(config_openai)
            provider_b = create_provider(config_path=str(config_file))
            assert isinstance(provider_b, OpenAIProvider)

    def test_build_provider_default_models(self):
        """model=None이면 각 provider의 기본 모델이 사용됨."""
        with patch("anthropic.Anthropic"):
            from llm.factory import _build_provider
            provider = _build_provider("anthropic", model=None)
            assert provider.model == "claude-opus-4-5"

        sys.modules.pop("llm.factory", None)
        sys.modules.pop("llm.providers.openai_provider", None)
        from llm.factory import _build_provider
        provider = _build_provider("openai", model=None)
        assert provider.model == "gpt-4o"

        sys.modules.pop("llm.factory", None)
        sys.modules.pop("llm.providers.ollama_provider", None)
        from llm.factory import _build_provider
        provider = _build_provider("ollama", model=None)
        assert provider.model == "llama3.1"

    def test_create_provider_uses_config_model(self, tmp_path):
        """config의 model 값이 provider에 전달됨."""
        config_content = """
llm:
  provider: "ollama"
  model: "mistral"
  temperature: 0.2
  max_tokens: 4096
"""
        config_file = tmp_path / "system_config.yaml"
        config_file.write_text(config_content)

        from llm.factory import create_provider
        provider = create_provider(config_path=str(config_file))
        assert provider.model == "mistral"


# ---------------------------------------------------------------------------
# 6. JSON schema 강제 end-to-end 동작 검증
# ---------------------------------------------------------------------------

class TestJsonSchemaEnforcement:
    """response_format이 실제로 schema 강제 로직을 포함하는지 검증."""

    def test_anthropic_schema_appears_in_system_prompt(self):
        """AnthropicProvider: schema 내용이 system에 직렬화되어 포함됨."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"score": 0.9}')]
            mock_client.messages.create.return_value = mock_response
            provider._client = mock_client

            schema = {
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["score", "reasoning"],
            }
            provider.chat(
                messages=[{"role": "user", "content": "analyze this"}],
                response_format=schema,
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            system_value = call_kwargs.get("system", "")
            assert "score" in system_value
            assert "reasoning" in system_value
            assert "required" in system_value

    def test_openai_schema_appears_in_system_message(self):
        """OpenAIProvider: schema 내용이 system 메시지에 직렬화되어 포함됨."""
        sys.modules.pop("llm.providers.openai_provider", None)
        mock_openai_module = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client_instance
        sys.modules["openai"] = mock_openai_module

        mock_choice = MagicMock()
        mock_choice.message.content = '{"score": 0.8}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response

        from llm.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()

        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "label": {"type": "string"},
            },
        }
        provider.chat(
            messages=[{"role": "user", "content": "classify this"}],
            response_format=schema,
        )

        call_kwargs = mock_client_instance.chat.completions.create.call_args[1]
        system_msg = call_kwargs["messages"][0]
        assert system_msg["role"] == "system"
        assert "score" in system_msg["content"]
        assert "label" in system_msg["content"]

    def test_ollama_schema_appears_in_system_message(self):
        """OllamaProvider: schema 내용이 system 메시지에 직렬화되어 포함됨."""
        sys.modules.pop("llm.providers.ollama_provider", None)
        mock_ollama_module = MagicMock()
        mock_ollama_module.chat.return_value = {"message": {"content": '{"action": "buy"}'}}
        sys.modules["ollama"] = mock_ollama_module

        from llm.providers.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        provider._ollama = mock_ollama_module

        schema = {
            "type": "object",
            "properties": {
                "action": {"enum": ["buy", "sell", "hold"]},
            },
        }
        provider.chat(
            messages=[{"role": "user", "content": "what to do?"}],
            response_format=schema,
        )

        call_kwargs = mock_ollama_module.chat.call_args[1]
        system_msg = call_kwargs["messages"][0]
        assert system_msg["role"] == "system"
        assert "action" in system_msg["content"]
        assert "buy" in system_msg["content"]

    def test_response_format_not_empty_shell(self):
        """response_format 처리가 빈 껍데기가 아님 — 실제로 schema를 주입함."""
        with patch("anthropic.Anthropic"):
            sys.modules.pop("llm.providers.anthropic_provider", None)
            from llm.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="{}")]
            mock_client.messages.create.return_value = mock_response
            provider._client = mock_client

            # response_format 없이 호출
            provider.chat(
                messages=[{"role": "user", "content": "test"}],
            )
            no_schema_kwargs = mock_client.messages.create.call_args[1]
            no_schema_system = no_schema_kwargs.get("system", "")

            mock_client.reset_mock()

            # response_format 있이 호출
            schema = {"type": "object", "properties": {"field": {"type": "string"}}}
            provider.chat(
                messages=[{"role": "user", "content": "test"}],
                response_format=schema,
            )
            with_schema_kwargs = mock_client.messages.create.call_args[1]
            with_schema_system = with_schema_kwargs.get("system", "")

            # schema가 있을 때는 system이 더 길어야 함 (JSON 지시가 추가됨)
            assert len(with_schema_system) > len(no_schema_system)
            assert "field" in with_schema_system
