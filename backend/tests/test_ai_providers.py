from __future__ import annotations

import pytest
import responses

from app.services.ai.base import ProviderError
from app.services.ai.factory import build_provider
from app.services.ai.ollama_provider import OllamaProvider


def test_ollama_connection_refused_raises_provider_error():
    provider = OllamaProvider(base_url="http://localhost:1", model="llama3.1")
    with pytest.raises(ProviderError):
        provider.generate(messages=[{"role": "user", "content": "hi"}])


@responses.activate
def test_ollama_generate_success():
    responses.add(
        responses.POST,
        "http://localhost:11434/api/chat",
        json={"message": {"content": "hello there"}},
        status=200,
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    reply = provider.generate(messages=[{"role": "user", "content": "hi"}])
    assert reply == "hello there"


@responses.activate
def test_ollama_list_models():
    responses.add(
        responses.GET,
        "http://localhost:11434/api/tags",
        json={"models": [{"name": "llama3.1"}, {"name": "mistral"}]},
        status=200,
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    assert provider.list_models() == ["llama3.1", "mistral"]


def test_ollama_list_models_unreachable_returns_empty_list():
    provider = OllamaProvider(base_url="http://localhost:1", model="llama3.1")
    assert provider.list_models() == []


def test_build_provider_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(tmp_path))
    with pytest.raises(ProviderError):
        build_provider("openai")


def test_build_provider_unknown_name_raises():
    with pytest.raises(ProviderError):
        build_provider("not-a-real-provider")
