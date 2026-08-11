"""Regression tests for the loopback-server hardening in app/security.py.

Every test here corresponds to something that was exploitable before the
guards existed - each one passes trivially if init_security is removed from
the app factory, so they are worth keeping.
"""
from __future__ import annotations

import re

from app.extensions import Session
from app.models.fighter import Fighter
from app.security import _hostname
from app.services.updates import _safe_http_url


# --- Host allowlist / DNS rebinding -----------------------------------


def test_foreign_host_header_is_rejected(client):
    """The rebinding case: browser resolves evil.com to 127.0.0.1, then
    reads our responses as evil.com's own origin. Refusing the Host is what
    breaks the chain."""
    resp = client.get("/", headers={"Host": "evil.example.com"})
    assert resp.status_code == 403


def test_foreign_host_is_rejected_even_on_health(client):
    # /health is the most innocuous route; the guard must not have holes
    # punched in it for convenience.
    resp = client.get("/health", headers={"Host": "attacker.test"})
    assert resp.status_code == 403


def test_loopback_hosts_are_allowed(client):
    for host in ("127.0.0.1:8765", "localhost:8765", "localhost", "[::1]:8765"):
        resp = client.get("/health", headers={"Host": host})
        assert resp.status_code == 200, f"{host} should be allowed"


def test_hostname_parsing():
    assert _hostname("127.0.0.1:8765") == "127.0.0.1"
    assert _hostname("[::1]:8765") == "::1"
    assert _hostname("http://127.0.0.1:8765") == "127.0.0.1"
    assert _hostname("https://evil.example.com") == "evil.example.com"
    # "null" Origin (sandboxed iframe / data: document) has no hostname, so
    # it fails the allowlist rather than looking like an absent header.
    assert _hostname("null") == "null"
    assert _hostname("") == ""


def test_env_allowlist_extends_hosts(client, monkeypatch):
    monkeypatch.setenv("UFC_PREDICTOR_ALLOWED_HOSTS", "mydesktop.lan")
    assert client.get("/health", headers={"Host": "mydesktop.lan:8765"}).status_code == 200
    assert client.get("/health", headers={"Host": "evil.example.com"}).status_code == 403


# --- CSRF -------------------------------------------------------------


def test_cross_origin_post_is_rejected(client):
    """A cross-origin form POST is a "simple request" - it is sent without a
    preflight, so nothing about CORS stops it arriving."""
    resp = client.post(
        "/chat/new",
        headers={"Origin": "https://evil.example.com", "Content-Type": "text/plain"},
        data="x",
    )
    assert resp.status_code == 403


def test_cross_site_scraper_trigger_is_rejected(client):
    """The worst CSRF target: no body required, and it starts a multi-hour
    scrape of ufc.com from the user's own IP."""
    resp = client.post(
        "/settings/sync-fighters",
        headers={"Origin": "https://evil.example.com", "Content-Type": "text/plain"},
        data="x",
    )
    assert resp.status_code == 403


def test_cross_site_provider_write_is_rejected(client):
    # Would otherwise let a foreign page overwrite the stored API key.
    resp = client.post(
        "/settings/provider",
        json={"provider": "openai", "api_key": "sk-attacker"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403


def test_sec_fetch_site_header_alone_is_enough_to_reject(client):
    # Browsers set this even when Origin is absent.
    resp = client.post("/chat/new", headers={"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 403


def test_same_origin_post_is_allowed(client):
    resp = client.post(
        "/chat/new",
        headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["conversation_id"]


def test_post_without_browser_headers_is_allowed(client):
    """curl and the packaged app's own probes send neither header. Rejecting
    them would break non-browser callers without closing anything: a browser
    always labels a genuine cross-origin POST."""
    assert client.post("/chat/new").status_code == 200


def test_cross_site_get_is_not_blocked(client):
    # Safe methods are unaffected; the Host check is what protects reads.
    resp = client.get("/health", headers={"Sec-Fetch-Site": "cross-site"})
    assert resp.status_code == 200


# --- Response headers -------------------------------------------------


def test_security_headers_present(client):
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    # script-src must not fall back to unsafe-inline - the nonce is the
    # whole point of keeping it strict.
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_csp_nonce_matches_the_inline_script(client):
    """If these ever drift, the pre-paint sidebar script is silently blocked
    and the UI regains the flash it was written to prevent."""
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    header_nonce = re.search(r"'nonce-([\w-]+)'", csp).group(1)
    body = resp.get_data(as_text=True)
    assert f'<script nonce="{header_nonce}">' in body


def test_nonce_differs_between_responses(client):
    def nonce_of(resp):
        return re.search(r"'nonce-([\w-]+)'", resp.headers["Content-Security-Policy"]).group(1)

    assert nonce_of(client.get("/")) != nonce_of(client.get("/"))


# --- LIKE wildcard handling -------------------------------------------


def test_autocomplete_escapes_like_wildcards(app, client):
    with app.app_context():
        session = Session()
        session.add_all(
            [
                Fighter(ufc_slug="jon-jones", name="Jon Jones"),
                Fighter(ufc_slug="literal-pct", name="100% Savage"),
            ]
        )
        session.commit()
        Session.remove()

    # "%" is a literal search term, not "match every row".
    rows = client.get("/api/fighters/autocomplete?q=%25%25").get_json()
    assert [r["name"] for r in rows] == []

    rows = client.get("/api/fighters/autocomplete?q=00%25").get_json()
    assert [r["name"] for r in rows] == ["100% Savage"]

    # "_" is likewise literal rather than "any single character".
    rows = client.get("/api/fighters/autocomplete?q=J_n").get_json()
    assert rows == []


# --- Untrusted URLs from the update manifest --------------------------


def test_safe_http_url_filters_dangerous_schemes():
    assert _safe_http_url("https://example.com/a.zip") == "https://example.com/a.zip"
    assert _safe_http_url("http://example.com/a.zip") == "http://example.com/a.zip"
    # Would run in the app's own origin once placed in an href.
    assert _safe_http_url("javascript:fetch('/settings/provider')") is None
    assert _safe_http_url("data:text/html,<script>alert(1)</script>") is None
    assert _safe_http_url("file:///C:/Windows/System32/calc.exe") is None
    assert _safe_http_url(None) is None
    assert _safe_http_url("") is None
    assert _safe_http_url(12345) is None
