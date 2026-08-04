from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    """Raised for any user-facing AI provider failure: no key configured,
    auth rejected, network unreachable, malformed response, etc. Routes
    catch this and surface `str(exc)` directly to the UI.
    """


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...]
        Returns the assistant's reply text (or a JSON string when json_mode=True).
        """
        raise NotImplementedError

    def list_models(self) -> list[str]:
        """Only meaningful for providers with a discoverable local model list
        (Ollama). Cloud providers return a small curated static list.
        """
        return []
