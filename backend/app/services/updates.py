"""Checks the marketing site's version manifest for a newer release.

The app does not self-update. It tells the user a newer version exists and
sends them to the site to download the installer - which is the whole
distribution model, and avoids shipping an auto-updater that has to be
trusted to replace an executable on the user's machine.

The manifest is the same `version.json` the Download page reads, so
publishing a release (scripts/build_release.py) is what makes existing
installs notice it. Nothing else to update.
"""
from __future__ import annotations

import json
import logging
import time

import requests

from app.config import Config
from app.version import get_current_version, is_dev_build, is_newer

logger = logging.getLogger(__name__)

# Long enough that opening the app repeatedly in a session doesn't hammer
# the host, short enough that a release published today is noticed today.
CACHE_TTL_SECONDS = 6 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 6

_cache: dict | None = None
_cache_at: float = 0.0


def check_for_update(force: bool = False) -> dict:
    """Returns the update status for the UI.

    Never raises: this runs on a dashboard load, and an offline machine or a
    404 manifest must degrade to "couldn't check", not an error page. A
    local-first app has to stay fully usable with no network.
    """
    current = get_current_version()

    if is_dev_build():
        return {
            "status": "dev",
            "currentVersion": current,
            "detail": "Development build - update checks are disabled.",
        }

    manifest_url = Config.UPDATE_MANIFEST_URL
    if not manifest_url:
        return {
            "status": "disabled",
            "currentVersion": current,
            "detail": "No update manifest URL is configured.",
        }

    manifest = _fetch_manifest(manifest_url, force=force)
    if manifest is None:
        return {
            "status": "unknown",
            "currentVersion": current,
            "detail": "Could not reach the update server.",
        }

    latest = str(manifest.get("version", "")).strip()
    if not latest:
        return {
            "status": "unknown",
            "currentVersion": current,
            "detail": "The update manifest has no version field.",
        }

    if not is_newer(latest, current):
        return {"status": "current", "currentVersion": current, "latestVersion": latest}

    return {
        "status": "available",
        "currentVersion": current,
        "latestVersion": latest,
        # Point at the site's download page rather than the raw installer:
        # the page carries the SmartScreen warning and the checksum, and a
        # binary that starts downloading unprompted is hostile.
        "downloadPageUrl": Config.DOWNLOAD_PAGE_URL,
        "downloadUrl": manifest.get("downloadUrl"),
        "releaseNotes": manifest.get("releaseNotes") or [],
        "releasedAt": manifest.get("releasedAt"),
        "sizeBytes": manifest.get("sizeBytes"),
    }


def _fetch_manifest(url: str, force: bool = False) -> dict | None:
    global _cache, _cache_at

    if not force and _cache is not None and (time.time() - _cache_at) < CACHE_TTL_SECONDS:
        return _cache

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={
                "User-Agent": f"UFCPredictor/{get_current_version()}",
                # Manifests get served from CDNs and raw.githubusercontent;
                # a cached copy would hide the release we're checking for.
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as exc:
        logger.info("update check failed: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None

    _cache = payload
    _cache_at = time.time()
    return payload


def reset_cache_for_tests() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0
