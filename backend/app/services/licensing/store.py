"""On-disk state for licensing: the cached token and this install's identity.

Both live in the app's data directory, which is the folder next to the
executable for a portable install (SPEC.md section 13.1). That placement is
deliberate and has a visible consequence: copying the folder to another machine
carries the activation with it. That is the intended behaviour for a portable
app, and the device cap is a courtesy limit rather than a security control.

Nothing here is secret in a way that would justify the OS keyring. The token is
signed, not encrypted — it says what the user already knows, and editing it
invalidates the signature.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LICENCE_FILENAME = "licence.json"
INSTALL_ID_FILENAME = "install_id"


def install_id(data_dir: Path) -> str:
    """This install's stable id, created on first use.

    A random UUID rather than a hardware fingerprint. The app is portable: the
    same install legitimately runs from a USB stick on several machines, and a
    machine-derived id would burn a fresh device slot on each one.
    """
    path = Path(data_dir) / INSTALL_ID_FILENAME
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("could not read install id (%s); using a temporary one", exc)
        return str(uuid.uuid4())

    generated = str(uuid.uuid4())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated, encoding="utf-8")
    except OSError as exc:
        # A read-only data directory should not stop the app working; it just
        # means this install re-registers next launch.
        log.warning("could not persist install id (%s)", exc)
    return generated


def load(data_dir: Path) -> dict[str, Any] | None:
    """The cached licence payload, or None if absent or unreadable."""
    path = Path(data_dir) / LICENCE_FILENAME
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        # A corrupt cache is not worth a crash, or even a prompt: the next
        # successful refresh replaces it.
        log.warning("discarding unreadable licence cache (%s)", exc)
        return None
    return payload if isinstance(payload, dict) else None


def save(data_dir: Path, payload: dict[str, Any]) -> None:
    """Write the licence cache, atomically."""
    directory = Path(data_dir)
    path = directory / LICENCE_FILENAME
    temporary = path.with_suffix(".tmp")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        # Replace rather than truncate-and-write: a crash mid-write would
        # otherwise leave a half-file that reads as "not entitled", quietly
        # downgrading somebody who paid.
        temporary.replace(path)
    except OSError as exc:
        log.warning("could not write licence cache (%s)", exc)


def clear(data_dir: Path) -> None:
    """Forget the licence, on sign-out."""
    try:
        (Path(data_dir) / LICENCE_FILENAME).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("could not clear licence cache (%s)", exc)
