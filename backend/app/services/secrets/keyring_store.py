"""Primary secret store: OS keyring, with the Windows backend explicitly
selected rather than left to auto-detection.

Why explicit: `keyring`'s backend auto-detection walks installed-package
entry points via importlib.metadata, which is unreliable once the app is
frozen by PyInstaller (dist-info metadata is often not preserved in the
bundle), and can silently resolve to `keyring.backends.fail.Keyring` (which
raises on every call). Selecting `WinVaultKeyring` explicitly at startup
avoids depending on that discovery working correctly post-freeze.
"""
from __future__ import annotations

import sys
import threading

import keyring
import keyring.errors

SERVICE_NAME = "UFCPredictor"

_lock = threading.Lock()
_configured = False


def _configure_backend() -> None:
    global _configured
    with _lock:
        if _configured:
            return
        if sys.platform == "win32":
            try:
                from keyring.backends.Windows import WinVaultKeyring

                keyring.set_keyring(WinVaultKeyring())
            except Exception:
                # Leave whatever backend keyring already resolved; secret_manager
                # will catch failures from get_key/set_key and use the fallback.
                pass
        _configured = True


def set_key(provider: str, value: str) -> None:
    _configure_backend()
    keyring.set_password(SERVICE_NAME, provider, value)


def get_key(provider: str) -> str | None:
    _configure_backend()
    return keyring.get_password(SERVICE_NAME, provider)


def delete_key(provider: str) -> None:
    _configure_backend()
    try:
        keyring.delete_password(SERVICE_NAME, provider)
    except keyring.errors.PasswordDeleteError:
        pass
