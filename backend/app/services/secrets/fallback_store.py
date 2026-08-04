"""Fallback secret store used only when the OS keyring is unavailable.

A single JSON blob of {provider: api_key} is Fernet-encrypted with a key
that lives in its own file under the app's data directory. This protects
against casual disk inspection (e.g. someone browsing app data folders), not
a determined local attacker with full access to the same OS user account -
that tradeoff is documented and accepted in docs/SPEC.md for a single-user
local desktop tool.
"""
from __future__ import annotations

import json
import os

from cryptography.fernet import Fernet, InvalidToken

from app.config import Config


def _get_or_create_key() -> bytes:
    key_path = Config.fallback_key_path()
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass  # best-effort on platforms where chmod semantics differ (Windows)
    return key


def _load_all() -> dict[str, str]:
    path = Config.fallback_secrets_path()
    if not path.exists():
        return {}
    fernet = Fernet(_get_or_create_key())
    try:
        decrypted = fernet.decrypt(path.read_bytes())
        return json.loads(decrypted.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return {}


def _save_all(data: dict[str, str]) -> None:
    fernet = Fernet(_get_or_create_key())
    encrypted = fernet.encrypt(json.dumps(data).encode("utf-8"))
    Config.fallback_secrets_path().write_bytes(encrypted)


def set_key(provider: str, value: str) -> None:
    data = _load_all()
    data[provider] = value
    _save_all(data)


def get_key(provider: str) -> str | None:
    return _load_all().get(provider)


def delete_key(provider: str) -> None:
    data = _load_all()
    if provider in data:
        del data[provider]
        _save_all(data)
