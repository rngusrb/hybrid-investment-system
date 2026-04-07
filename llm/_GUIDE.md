# llm/ — LLM Provider 레이어 가이드

## 역할
LLM API 추상화. config 한 줄로 provider 교체 가능하도록 설계.
실제 API 호출은 여기서만 — agents/는 BaseLLMProvider 인터페이스만 사용.

---

## 핵심 패턴

### provider 교체는 config에서만
```yaml
# config/system_config.yaml
llm:
  provider: "anthropic"   # → "openai" 또는 "ollama"로 교체
  model: "claude-haiku-4-5-20251001"
```

### BaseLLMProvider 인터페이스
```python
class BaseLLMProvider(ABC):
    def chat(self, messages, system, temperature, max_tokens) -> str
    def name(self) -> str
```
새 provider 추가 시 이 두 메서드만 구현하면 됨.

### JSON 강제 응답
```python
# AnthropicProvider: system prompt에 JSON schema 지시 삽입
# OpenAIProvider: response_format={"type": "json_object"}
```

---

## 금지사항

### ❌ agents/에서 직접 anthropic/openai 패키지 import
```python
# 금지
import anthropic
client = anthropic.Anthropic()

# 반드시 factory 통해서
from llm.factory import create_llm_provider
llm = create_llm_provider(config)
```

### ❌ API key를 코드에 하드코딩
.env 파일 또는 환경변수에서만 읽을 것.

### ❌ 50KB 초과 응답 허용
base_agent.py에서 차단하지만, provider에서도 이상한 응답은 조기 탐지 권장.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `base.py` | BaseLLMProvider ABC |
| `factory.py` | config 읽고 provider 인스턴스 반환 |
| `providers/anthropic_provider.py` | Claude API (기본 사용) |
| `providers/openai_provider.py` | OpenAI API |
| `providers/ollama_provider.py` | 로컬 Ollama |

---

## 하네스

```
tests:
  - tests/unit/test_llm_providers.py
```

```bash
python scripts/harness.py llm/
```

---

## 최근 변경

| 날짜 | 파일 | 변경 내용 |
|------|------|----------|
| 2026-04-01 | providers/ | 3개 provider 초기 구현 |
