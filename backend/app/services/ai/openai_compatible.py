from __future__ import annotations

from openai import APIConnectionError, AuthenticationError, OpenAI, OpenAIError

from app.services.ai.base import AIProvider, ProviderError


class OpenAICompatibleProvider(AIProvider):
    """Shared implementation for any provider exposing an OpenAI-compatible
    /chat/completions surface. OpenAIProvider and DeepseekProvider differ only
    in base_url/default model - Deepseek's API is OpenAI-compatible.
    """

    name = "openai_compatible"
    default_model = "gpt-4o-mini"

    def __init__(self, api_key: str, base_url: str | None = None, model: str | None = None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model or self.default_model

    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=payload_messages, **kwargs
            )
        except AuthenticationError as exc:
            raise ProviderError(f"{self.name}: API key was rejected") from exc
        except APIConnectionError as exc:
            raise ProviderError(f"{self.name}: could not connect") from exc
        except OpenAIError as exc:
            raise ProviderError(f"{self.name}: request failed: {exc}") from exc
        return resp.choices[0].message.content or ""

    def list_models(self) -> list[str]:
        return [self.default_model]


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key=api_key, base_url=None, model=model)

    def list_models(self) -> list[str]:
        return ["gpt-4o-mini", "gpt-4o", "gpt-4.1"]


class DeepseekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    default_model = "deepseek-chat"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key=api_key, base_url="https://api.deepseek.com", model=model)

    def list_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner"]
