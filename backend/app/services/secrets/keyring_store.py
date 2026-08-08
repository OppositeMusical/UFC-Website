"""Primary secret store: the OS keyring, with the backend explicitly
selected per platform rather than left to auto-detection.

Why explicit: `keyring`'s backend auto-detection walks installed-package
entry points via importlib.metadata, which is unreliable once the app is
frozen by PyInstaller (dist-info metadata is often not preserved in the
bundle), and can silently resolve to `keyring.backends.fail.Keyring` (which
raises on every call). Naming the backend at startup avoids depending on
that discovery working post-freeze.

  Windows -> WinVaultKeyring (Credential Manager)
  macOS   -> keyring.backends.macOS.Keyring (Keychain)

The reasoning is identical on both, so the macOS branch is not optional
politeness - without it a frozen mac build would quietly fall back to the
encrypted-file store even though a real Keychain is available.
"""
from __future__ import annotations

import logging
import sys
import threading

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

# Unchanged despite the MMA Assist rename: this is the key under which
# existing installs' secrets are filed in the OS credential store. Renaming
# it would orphan every saved API key.
SERVICE_NAME = "UFCPredictor"

_lock = threading.Lock()
_configured = False


def _configure_backend() -> None:
    global _configured
    with _lock:
        if _configured:
            return
        # Either branch failing leaves whatever backend keyring already
        # resolved; secret_manager catches errors from get_key/set_key and
        # falls back to the encrypted file, so a missing Keychain or Vault
        # degrades rather than breaking startup.
        #
        # The failure is LOGGED, not swallowed. A bare `except: pass` here is
        # how frozen Windows builds silently stored every API key in the
        # encrypted-file fallback while the docs claimed Credential Manager -
        # the bug was invisible because nothing recorded why the backend
        # never loaded.
        try:
            if sys.platform == "win32":
                from keyring.backends.Windows import WinVaultKeyring

                backend = WinVaultKeyring()
            elif sys.platform == "darwin":
                from keyring.backends.macOS import Keyring as MacKeyring

                backend = MacKeyring()
            else:
                backend = None

            if backend is not None:
                # priority raises when the backend's platform support is
                # missing, which is the real signal - constructing it does not
                # fail on its own.
                _ = backend.priority
                keyring.set_keyring(backend)
                logger.info("OS keyring backend: %s", type(backend).__name__)
        except Exception:
            logger.warning(
                "Could not select the native keyring backend for %s; "
                "secrets will use the encrypted-file fallback",
                sys.platform,
                exc_info=True,
            )
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
