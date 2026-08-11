from __future__ import annotations

import json

import pytest
import responses

from app.services import updates
from app.version import DEV_VERSION, is_newer, parse_version, set_current_version

MANIFEST_URL = "https://example.test/version.json"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(updates.Config, "UPDATE_MANIFEST_URL", MANIFEST_URL)
    monkeypatch.setattr(updates.Config, "DOWNLOAD_PAGE_URL", "https://example.test/download")
    updates.reset_cache_for_tests()
    set_current_version("1.2.0")
    yield
    set_current_version(None)
    updates.reset_cache_for_tests()


def _manifest(version="1.3.0", **extra):
    body = {"version": version, "downloadUrl": f"/downloads/app-{version}.exe", **extra}
    responses.add(responses.GET, MANIFEST_URL, body=json.dumps(body), status=200)


# --- version comparison -------------------------------------------------


@pytest.mark.parametrize(
    "candidate,current,expected",
    [
        ("1.3.0", "1.2.0", True),
        ("1.2.0", "1.2.0", False),
        ("1.1.9", "1.2.0", False),
        # The reason this isn't a string comparison.
        ("0.10.0", "0.9.0", True),
        ("0.9.0", "0.10.0", False),
        ("1.2.10", "1.2.9", True),
        # A prerelease is older than its own release, not newer.
        ("1.3.0-rc1", "1.3.0", False),
        ("1.3.0", "1.3.0-rc1", True),
        # Garbage never triggers an update prompt.
        ("not-a-version", "1.2.0", False),
        ("1.3.0", "garbage", False),
        ("", "1.2.0", False),
    ],
)
def test_is_newer(candidate, current, expected):
    assert is_newer(candidate, current) is expected


def test_parse_version_rejects_malformed():
    assert parse_version("1.2") is None
    assert parse_version("v1.2.3") is None
    assert parse_version("1.2.3") == (1, 2, 3, 1)


# --- update check -------------------------------------------------------


@responses.activate
def test_reports_available_update_with_notes():
    _manifest("1.3.0", releaseNotes=["Faster chat", "Fixed the dashboard"], releasedAt="2026-08-04")

    result = updates.check_for_update()
    assert result["status"] == "available"
    assert result["latestVersion"] == "1.3.0"
    assert result["currentVersion"] == "1.2.0"
    assert result["releaseNotes"] == ["Faster chat", "Fixed the dashboard"]
    assert result["downloadPageUrl"] == "https://example.test/download"


@responses.activate
def test_reports_current_when_up_to_date():
    _manifest("1.2.0")
    assert updates.check_for_update()["status"] == "current"


@responses.activate
def test_older_published_version_is_not_an_update():
    """A rollback on the site must not prompt users to 'update' downwards."""
    _manifest("1.1.0")
    assert updates.check_for_update()["status"] == "current"


def test_dev_build_skips_the_network_entirely():
    """No responses are registered, so any HTTP call would error - a dev
    build must not have a version to compare in the first place.
    """
    set_current_version(None)
    result = updates.check_for_update()
    assert result["status"] == "dev"
    assert result["currentVersion"] == DEV_VERSION


@responses.activate
def test_unreachable_server_degrades_quietly():
    responses.add(responses.GET, MANIFEST_URL, status=500)
    result = updates.check_for_update()
    assert result["status"] == "unknown"


@responses.activate
def test_malformed_manifest_does_not_raise():
    responses.add(responses.GET, MANIFEST_URL, body="<html>not json</html>", status=200)
    assert updates.check_for_update()["status"] == "unknown"


@responses.activate
def test_manifest_without_version_is_unknown():
    responses.add(responses.GET, MANIFEST_URL, body=json.dumps({"downloadUrl": "/x.exe"}), status=200)
    assert updates.check_for_update()["status"] == "unknown"


@responses.activate
def test_result_is_cached_between_calls():
    _manifest("1.3.0")
    updates.check_for_update()
    updates.check_for_update()
    # Only one registered response, and `responses` would raise on a second
    # unmatched request - so this asserts the cache actually held.
    assert len(responses.calls) == 1


@responses.activate
def test_force_bypasses_the_cache():
    _manifest("1.3.0")
    responses.add(responses.GET, MANIFEST_URL, body=json.dumps({"version": "1.4.0"}), status=200)

    assert updates.check_for_update()["latestVersion"] == "1.3.0"
    assert updates.check_for_update(force=True)["latestVersion"] == "1.4.0"


# --- minSupportedVersion kill switch ------------------------------------


@responses.activate
def test_update_is_required_when_below_min_supported():
    # Current is 1.2.0 (see the _isolate fixture).
    _manifest("1.3.0", minSupportedVersion="1.2.5")
    result = updates.check_for_update()
    assert result["status"] == "required"
    assert result["detail"]


@responses.activate
def test_update_stays_optional_at_or_above_min_supported():
    _manifest("1.3.0", minSupportedVersion="1.2.0")
    assert updates.check_for_update()["status"] == "available"


@responses.activate
def test_absent_min_supported_is_an_optional_update():
    _manifest("1.3.0")
    assert updates.check_for_update()["status"] == "available"


@responses.activate
def test_malformed_min_supported_does_not_force_an_update():
    """A typo in the manifest must not escalate every user to a forced
    update - unparseable input fails towards the ordinary path."""
    _manifest("1.3.0", minSupportedVersion="not-a-version")
    assert updates.check_for_update()["status"] == "available"


@responses.activate
def test_min_supported_does_not_invent_an_update_when_current():
    # Nothing newer exists, so there is nothing to require regardless.
    _manifest("1.2.0", minSupportedVersion="9.9.9")
    assert updates.check_for_update()["status"] == "current"


# --- endpoint -----------------------------------------------------------


def test_update_endpoint_returns_json(client):
    resp = client.get("/api/updates/check")
    assert resp.status_code == 200
    assert "status" in resp.get_json()
