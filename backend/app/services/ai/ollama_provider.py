from __future__ import annotations

import requests

from app.services.ai.base import AIProvider, ProviderError


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)
        payload = {"model": self.model, "messages": payload_messages, "stream": False}
        if json_mode:
            payload["format"] = "json"
        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=180)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ProviderError(
                f"Could not reach Ollama at {self.base_url}. Is it installed and running?"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            return []
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
