from __future__ import annotations

from app.config import Config
from app.models.app_setting import KEY_ACTIVE_OLLAMA_MODEL, KEY_ACTIVE_PROVIDER
from app.services.ai.base import AIProvider, ProviderError
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.openai_compatible import DeepseekProvider, OpenAIProvider
from app.services.db.session import get_setting
from app.services.secrets import secret_manager

PROVIDER_NAMES = ["ollama", "openai", "gemini", "deepseek", "claude"]
DEFAULT_OLLAMA_MODEL = "llama3.1"


def get_active_provider() -> AIProvider:
    provider_name = get_setting(KEY_ACTIVE_PROVIDER, default="ollama") or "ollama"
    return build_provider(provider_name)


def build_provider(provider_name: str, model: str | None = None) -> AIProvider:
    if provider_name == "ollama":
        ollama_model = model or get_setting(KEY_ACTIVE_OLLAMA_MODEL, default=DEFAULT_OLLAMA_MODEL)
        return OllamaProvider(base_url=Config.OLLAMA_BASE_URL, model=ollama_model)

    if provider_name in ("openai", "deepseek", "gemini", "claude"):
        key = secret_manager.get_key(provider_name)
        if not key:
            raise ProviderError(
                f"No {provider_name} API key configured. Add one in Settings."
            )
        if provider_name == "openai":
            return OpenAIProvider(api_key=key, model=model)
        if provider_name == "deepseek":
            return DeepseekProvider(api_key=key, model=model)
        if provider_name == "gemini":
            return GeminiProvider(api_key=key, model=model)
        return AnthropicProvider(api_key=key, model=model)

    raise ProviderError(f"Unknown provider: {provider_name}")
