"""Unified secret access: keyring first, Fernet-file fallback on any failure.

This is the only module the rest of the app should import for API keys -
callers never talk to keyring_store/fallback_store directly.
"""
from __future__ import annotations

import logging

from app.services.secrets import fallback_store, keyring_store

logger = logging.getLogger(__name__)


def set_key(provider: str, value: str) -> None:
    try:
        keyring_store.set_key(provider, value)
    except Exception:
        logger.warning("OS keyring unavailable, storing '%s' key in local encrypted fallback", provider)
        fallback_store.set_key(provider, value)


def get_key(provider: str) -> str | None:
    value = None
    try:
        value = keyring_store.get_key(provider)
    except Exception:
        logger.warning("OS keyring unavailable, reading '%s' key from local encrypted fallback", provider)
    if value is not None:
        return value
    return fallback_store.get_key(provider)


def has_key(provider: str) -> bool:
    return bool(get_key(provider))


def delete_key(provider: str) -> None:
    try:
        keyring_store.delete_key(provider)
    except Exception:
        pass
    fallback_store.delete_key(provider)
