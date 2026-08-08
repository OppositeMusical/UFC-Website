"""HTTP calls to the accounts service.

Every method returns None on failure rather than raising. That is the whole
design: the caller is a background refresh whose only correct response to "the
server is down" is to carry on with the cached token. Propagating an exception
up would eventually reach a request handler, and a request handler is exactly
where a licence check must never be able to fail.

Timeouts are short and explicit for the same reason. The default in ``requests``
is no timeout at all, which turns an unreachable host into a hung thread.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

# (connect, read). A licence refresh is never urgent, but it must never linger.
DEFAULT_TIMEOUT = (3.05, 10)


class AccountsClient:
    def __init__(self, base_url: str, timeout: tuple[float, float] = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_licence(self, access_token: str) -> dict[str, Any] | None:
        """Ask for a licence for this install. The device comes from the token."""
        return self._post_json(
            "/v1/licence",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any] | None:
        """Exchange a refresh token for a new access token (and a new refresh token).

        A 401 here is meaningful rather than transient — it means the token was
        revoked or reused — so the caller is told the difference, and signs the
        user out instead of retrying forever.
        """
        try:
            response = requests.post(
                f"{self.base_url}/v1/auth/refresh",
                json={"refreshToken": refresh_token},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            log.info("licence refresh unreachable (%s)", exc)
            return None

        if response.status_code == 401:
            log.info("refresh token rejected; the install needs to sign in again")
            return {"unauthenticated": True}
        if not response.ok:
            log.info("licence refresh failed with %s", response.status_code)
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def fetch_public_keys(self) -> dict[str, bytes] | None:
        """Fetch the JWKS document, so a rotated signing key resolves without an update.

        Returns raw 32-byte Ed25519 keys by ``kid``, and drops any entry that is
        not an Ed25519 OKP key — this build has no way to check anything else,
        and silently ignoring the unknown is better than importing it.
        """
        try:
            response = requests.get(
                f"{self.base_url}/.well-known/jwks.json", timeout=self.timeout
            )
            response.raise_for_status()
            document = response.json()
        except (requests.RequestException, ValueError) as exc:
            log.info("could not fetch licence signing keys (%s)", exc)
            return None

        keys: dict[str, bytes] = {}
        for entry in document.get("keys", []):
            if entry.get("kty") != "OKP" or entry.get("crv") != "Ed25519":
                continue
            kid, encoded = entry.get("kid"), entry.get("x")
            if not isinstance(kid, str) or not isinstance(encoded, str):
                continue
            try:
                keys[kid] = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            except Exception:  # noqa: BLE001 - a malformed key is simply skipped
                log.warning("skipping malformed signing key %r", kid)
        return keys or None

    def _post_json(self, path: str, headers: dict[str, str]) -> dict[str, Any] | None:
        try:
            response = requests.post(
                f"{self.base_url}{path}", headers=headers, timeout=self.timeout
            )
            if not response.ok:
                log.info("%s returned %s", path, response.status_code)
                return None
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            log.info("%s unreachable (%s)", path, exc)
            return None
