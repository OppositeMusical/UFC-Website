from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import responses

from app.services.ai.anthropic_provider import AnthropicProvider
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


# --- Claude: the system parameter must be absent, never null -----------------
#
# v0.6.1 fixed a 400 from the real API - `system: Input should be a valid array`
# - that fired on every Settings -> Test Connection with a Claude key, because
# that is the one caller which passes no system prompt. These tests assert the
# *outgoing request*, not the reply: a provider that sends `system=None` still
# returns fine against a fake client, so asserting on the reply would pass while
# the real API rejected the call.


class _FakeMessages:
    """Captures create() kwargs and returns a minimal Anthropic-shaped response."""

    def __init__(self):
        self.captured: dict = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="OK")],
        )


def _claude_with_fake_client() -> tuple[AnthropicProvider, _FakeMessages]:
    provider = AnthropicProvider(api_key="sk-ant-not-a-real-key")
    fake = _FakeMessages()
    provider.client = SimpleNamespace(messages=fake)
    return provider, fake


def test_claude_omits_system_entirely_when_none():
    """The regression. `system` must not appear in the request at all - an
    explicit None serialises to `"system": null`, which the API rejects."""
    provider, fake = _claude_with_fake_client()
    reply = provider.generate(messages=[{"role": "user", "content": "Reply OK"}])
    assert "system" not in fake.captured
    assert reply == "OK"


def test_claude_sends_system_when_given():
    provider, fake = _claude_with_fake_client()
    provider.generate(messages=[{"role": "user", "content": "hi"}], system="Be terse.")
    assert fake.captured["system"] == "Be terse."


def test_claude_json_mode_without_system_sends_a_string_not_none():
    """json_mode builds a system prompt out of nothing. Guard against that
    concatenation ever yielding None and reintroducing the same 400."""
    provider, fake = _claude_with_fake_client()
    provider.generate(messages=[{"role": "user", "content": "hi"}], json_mode=True)
    assert isinstance(fake.captured["system"], str)
    assert "JSON" in fake.captured["system"]


def test_claude_json_mode_keeps_the_caller_system_prompt():
    provider, fake = _claude_with_fake_client()
    provider.generate(
        messages=[{"role": "user", "content": "hi"}],
        system="You price fights.",
        json_mode=True,
    )
    assert fake.captured["system"].startswith("You price fights.")


@responses.activate
def test_ollama_sends_no_system_message_when_none():
    """Same contract for the default provider: no system prompt means no system
    turn in the payload, not a turn whose content is null."""
    responses.add(
        responses.POST,
        "http://localhost:11434/api/chat",
        json={"message": {"content": "OK"}},
        status=200,
    )
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    provider.generate(messages=[{"role": "user", "content": "hi"}])
    sent = json.loads(responses.calls[0].request.body)
    assert [m["role"] for m in sent["messages"]] == ["user"]


# --- Claude: model list comes from the API, keyed to the user's key ----------
#
# v0.6.2 replaced the hardcoded model lineup with GET /v1/models, which is
# authenticated - so the Settings picker offers exactly the models the saved
# key can use, and new releases appear without shipping an app update.


def test_claude_list_models_returns_ids_from_the_api():
    provider, _ = _claude_with_fake_client()
    provider.client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: [
                SimpleNamespace(id="claude-opus-5"),
                SimpleNamespace(id="claude-sonnet-5"),
                SimpleNamespace(id="claude-haiku-4-5"),
            ]
        )
    )
    assert provider.list_models() == [
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    ]


def test_claude_list_models_rejected_key_raises_provider_error():
    import httpx
    from anthropic import AuthenticationError

    def raise_auth():
        request = httpx.Request("GET", "https://api.anthropic.com/v1/models")
        response = httpx.Response(401, request=request)
        raise AuthenticationError("unauthorized", response=response, body=None)

    provider, _ = _claude_with_fake_client()
    provider.client = SimpleNamespace(models=SimpleNamespace(list=raise_auth))
    with pytest.raises(ProviderError, match="rejected"):
        provider.list_models()


# --- Settings: the picked Claude model is persisted and actually used --------
#
# secret_manager is patched throughout: the real one reads the OS keyring, so
# an unpatched test could pick up a developer's genuine key and hit the API.


def _fake_secrets(monkeypatch, key: str | None):
    monkeypatch.setattr(
        "app.services.ai.factory.secret_manager",
        SimpleNamespace(get_key=lambda name: key),
    )


def test_claude_models_route_without_key_is_a_readable_400(client, monkeypatch):
    _fake_secrets(monkeypatch, None)
    resp = client.get("/settings/claude/models")
    assert resp.status_code == 400
    assert "claude" in resp.get_json()["error"]


def test_claude_models_route_reports_lineup_and_active_model(client, monkeypatch):
    _fake_secrets(monkeypatch, "sk-ant-not-a-real-key")
    monkeypatch.setattr(
        AnthropicProvider, "list_models", lambda self: ["claude-opus-5", "claude-haiku-4-5"]
    )
    data = client.get("/settings/claude/models").get_json()
    assert data["models"] == ["claude-opus-5", "claude-haiku-4-5"]
    # Nothing saved yet, so the active model is the provider default.
    assert data["active"] == "claude-opus-5"


def test_saved_claude_model_is_used_by_the_factory(client, app, monkeypatch):
    _fake_secrets(monkeypatch, "sk-ant-not-a-real-key")
    resp = client.post(
        "/settings/provider",
        json={"provider": "claude", "model": "claude-haiku-4-5"},
    )
    assert resp.get_json()["ok"] is True
    with app.app_context():
        provider = build_provider("claude")
    assert provider.model == "claude-haiku-4-5"


def test_explicit_model_overrides_the_saved_claude_setting(client, app, monkeypatch):
    """Test Connection sends the on-screen dropdown value; it must win over
    whatever was saved earlier."""
    _fake_secrets(monkeypatch, "sk-ant-not-a-real-key")
    client.post("/settings/provider", json={"provider": "claude", "model": "claude-haiku-4-5"})
    with app.app_context():
        provider = build_provider("claude", model="claude-sonnet-5")
    assert provider.model == "claude-sonnet-5"
