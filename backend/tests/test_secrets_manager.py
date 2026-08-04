from __future__ import annotations

from app.services.secrets import fallback_store, keyring_store, secret_manager


def test_fallback_used_when_keyring_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(tmp_path))

    def boom(*args, **kwargs):
        raise RuntimeError("no keyring backend available")

    monkeypatch.setattr(keyring_store, "set_key", boom)
    monkeypatch.setattr(keyring_store, "get_key", boom)
    monkeypatch.setattr(keyring_store, "delete_key", boom)

    secret_manager.set_key("openai", "sk-abc123")
    assert secret_manager.has_key("openai") is True
    assert secret_manager.get_key("openai") == "sk-abc123"

    secret_manager.delete_key("openai")
    assert secret_manager.get_key("openai") is None


def test_fallback_roundtrip_directly(monkeypatch, tmp_path):
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(tmp_path))
    fallback_store.set_key("gemini", "key-value")
    assert fallback_store.get_key("gemini") == "key-value"
    fallback_store.delete_key("gemini")
    assert fallback_store.get_key("gemini") is None


def test_fallback_get_key_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(tmp_path))
    assert fallback_store.get_key("nonexistent-provider") is None
