"""Hardening for a server that listens on loopback inside a desktop app.

Binding 127.0.0.1 keeps the port off the network, but it does NOT make the
app private: the user's browser can still reach it, and so can any page the
user visits. Three separate holes follow from that, and each needs its own
guard.

1. DNS rebinding (`_check_host`). "Only listens on localhost" is not an
   access control. An attacker registers evil.com, points it at 127.0.0.1
   after the first page load, and the browser then sends requests to this
   server carrying `Host: evil.com` - and, crucially, treats the responses
   as belonging to evil.com's origin. The same-origin policy is satisfied,
   so CORS never enters into it and the attacker reads every response:
   chat history, saved predictions, provider settings. The fix is to
   check the Host header, because a rebound request cannot claim to be
   127.0.0.1 without giving up the origin it wants to read from.

2. CSRF (`_check_cross_site`). A cross-origin form POST is a "simple
   request" - no preflight, no CORS opt-in required to *send* it. The JSON
   endpoints happen to shrug those off because `get_json()` insists on
   `Content-Type: application/json` (which does force a preflight), but two
   endpoints take no body at all and were fully exposed: `/chat/new`, and
   `/settings/sync-fighters` - which kicks off a multi-hour scrape of
   ufc.com from the user's own IP address. Incidental protection from a
   content-type check is not protection; this checks the origin explicitly.

3. Missing response headers (`_set_security_headers`). Defence in depth for
   the chat page, which renders text an LLM produced.

Note that (1) and (2) reinforce each other: the Host check alone defeats
rebinding, and the origin check alone defeats ordinary CSRF, but a rebound
request looks same-origin to the browser, so only the Host check stops it
from passing the origin test too.
"""
from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import urlsplit

from flask import Flask, Response, g, request

logger = logging.getLogger(__name__)

# Loopback names only. Anything else means the request was routed here by a
# name we do not control, which is the rebinding signature.
DEFAULT_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Escape hatch for the deliberate `--host 0.0.0.0` case (reaching the app
# from a phone on the same LAN, say). Comma-separated hostnames. Off by
# default: exposing this app to a network is a choice that should be typed
# out, not one that happens because the guard was lenient.
ENV_ALLOWED_HOSTS = "UFC_PREDICTOR_ALLOWED_HOSTS"


def _hostname(value: str) -> str:
    """Bare hostname from a Host header or an Origin URL, lowercased.

    Handles ports and bracketed IPv6 ("[::1]:8765" -> "::1"). Returns "" for
    anything unparseable, which never matches the allowlist.
    """
    value = (value or "").strip()
    if not value:
        return ""
    try:
        # A Host header has no scheme, so give urlsplit a netloc to chew on.
        # An Origin already has one and is unaffected by the prefix.
        parsed = urlsplit(value if "//" in value else f"//{value}")
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def allowed_hosts() -> frozenset[str]:
    extra = os.environ.get(ENV_ALLOWED_HOSTS, "")
    if not extra.strip():
        return DEFAULT_ALLOWED_HOSTS
    names = {_hostname(part) for part in extra.split(",")}
    return DEFAULT_ALLOWED_HOSTS | {n for n in names if n}


def _check_host() -> Response | None:
    host = _hostname(request.headers.get("Host", ""))
    if host in allowed_hosts():
        return None
    logger.warning(
        "rejected request for %s with non-loopback Host %r - possible DNS rebinding",
        request.path,
        request.headers.get("Host", ""),
    )
    return Response(
        "This application only accepts requests addressed to localhost.",
        status=403,
        mimetype="text/plain",
    )


def _check_cross_site() -> Response | None:
    """Blocks state-changing requests that a browser marked as cross-site.

    Both signals are set by the browser and cannot be forged by page script,
    which is what makes them usable. Neither is *required* to be present:
    curl, the test client and the packaged app's own health probe send
    neither, and rejecting those would break non-browser callers without
    closing anything - a browser always labels a genuine cross-origin POST.
    """
    if request.method in SAFE_METHODS:
        return None

    # Sec-Fetch-Site is the precise signal where it exists: "same-origin" for
    # our own UI, "none" for a typed URL, "cross-site"/"same-site" otherwise.
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        origin_desc = fetch_site
    else:
        origin = request.headers.get("Origin")
        # "null" (sandboxed iframe, data: document) parses to no hostname and
        # correctly fails the allowlist rather than being treated as absent.
        if origin and _hostname(origin) not in allowed_hosts():
            origin_desc = origin
        else:
            return None

    logger.warning("rejected cross-site %s %s (origin: %s)", request.method, request.path, origin_desc)
    return Response(
        "Cross-site requests are not allowed.",
        status=403,
        mimetype="text/plain",
    )


def _set_security_headers(response: Response) -> Response:
    # script-src is strict: 'self' plus a per-response nonce for the one
    # inline block in base.html (it must run before first paint to stop a
    # collapsed sidebar flashing open, so it cannot become a deferred file).
    #
    # style-src keeps 'unsafe-inline' because a handful of templates carry
    # style="" attributes, and CSP has no nonce mechanism for those. That is
    # the deliberately weaker half: style injection cannot execute code, and
    # the directive that actually stops XSS - script-src - stays clean.
    csp = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{getattr(g, 'csp_nonce', '')}'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # The app is local-only; none of these are used and a compromised page
    # should not be able to start asking for them.
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
    )
    return response


def init_security(app: Flask) -> None:
    @app.before_request
    def _guard():  # type: ignore[misc]
        g.csp_nonce = secrets.token_urlsafe(16)
        return _check_host() or _check_cross_site()

    @app.after_request
    def _headers(response: Response) -> Response:  # type: ignore[misc]
        return _set_security_headers(response)

    @app.context_processor
    def _nonce():  # type: ignore[misc]
        return {"csp_nonce": getattr(g, "csp_nonce", "")}
