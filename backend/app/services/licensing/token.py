"""Offline verification of the licence token issued by the accounts service.

The app has to work on a plane. That rules out asking a server whether the user
is Pro, so instead the server signs a short-lived statement and this module
checks the signature locally against a public key baked into the build.

Security notes, since this is a hand-rolled JWS verifier and those have a bad
reputation:

- **The algorithm is pinned.** ``alg`` must be exactly ``EdDSA``. The classic
  JWT disaster is a verifier that trusts the header's choice of algorithm and
  gets handed ``none`` or an HMAC keyed on the public key. Nothing here reads a
  key or a method out of the token.
- **The signature is checked before any claim is used.** The payload is
  attacker-controlled bytes until the signature has been verified over the exact
  ASCII of ``header.payload``.
- **Expiry is deliberately not checked here.** ``evaluate()`` in
  ``entitlement.py`` owns that, because "expired" is not a simple boolean once
  the grace period is involved.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Only ever this. See the module docstring.
_REQUIRED_ALGORITHM = "EdDSA"


class LicenceError(Exception):
    """The token is unusable. Callers fall back to the free tier."""


class UnknownSigningKey(LicenceError):
    """Signed with a key id this build does not know.

    Recoverable: the caller can fetch the JWKS document and retry, which is how
    a signing key rotates without shipping a new release.
    """

    def __init__(self, kid: str) -> None:
        super().__init__(f"unknown signing key id: {kid!r}")
        self.kid = kid


@dataclass(frozen=True)
class LicenceClaims:
    """The verified contents of a licence token."""

    account_id: str
    tier: str
    issued_at: int
    expires_at: int
    grace_days: int
    jti: str
    device_id: str | None = None
    email: str | None = None
    features: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_pro(self) -> bool:
        return self.tier == "pro"

    def feature(self, name: str) -> bool:
        return bool(self.features.get(name, False))


def _b64url_decode(segment: str) -> bytes:
    # JWS strips base64 padding; put it back before decoding.
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except Exception as exc:  # noqa: BLE001 - any decode failure is the same to us
        raise LicenceError("licence token is not valid base64url") from exc


def verify_token(
    token: str,
    public_keys: Mapping[str, bytes],
    *,
    issuer: str,
    audience: str,
) -> LicenceClaims:
    """Verify ``token`` and return its claims.

    :param public_keys: raw 32-byte Ed25519 public keys, keyed by ``kid``.
    :raises UnknownSigningKey: the ``kid`` is not in ``public_keys``.
    :raises LicenceError: anything else wrong with the token.
    """
    if not token or not isinstance(token, str):
        raise LicenceError("no licence token")

    parts = token.split(".")
    if len(parts) != 3:
        raise LicenceError("licence token is not a compact JWS")

    encoded_header, encoded_payload, encoded_signature = parts

    try:
        header = json.loads(_b64url_decode(encoded_header))
    except json.JSONDecodeError as exc:
        raise LicenceError("licence token header is not JSON") from exc
    if not isinstance(header, dict):
        raise LicenceError("licence token header is not an object")

    if header.get("alg") != _REQUIRED_ALGORITHM:
        raise LicenceError(
            f"unexpected signature algorithm {header.get('alg')!r}; only EdDSA is accepted"
        )

    kid = header.get("kid")
    if not isinstance(kid, str):
        raise LicenceError("licence token header has no key id")
    key_bytes = public_keys.get(kid)
    if key_bytes is None:
        raise UnknownSigningKey(kid)

    # Everything above this line comes from the token itself and is worthless
    # until the signature holds.
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    try:
        Ed25519PublicKey.from_public_bytes(key_bytes).verify(
            _b64url_decode(encoded_signature), signing_input
        )
    except InvalidSignature as exc:
        raise LicenceError("licence token signature does not verify") from exc
    except ValueError as exc:
        raise LicenceError("licence signing key is malformed") from exc

    try:
        claims = json.loads(_b64url_decode(encoded_payload))
    except json.JSONDecodeError as exc:
        raise LicenceError("licence token payload is not JSON") from exc
    if not isinstance(claims, dict):
        raise LicenceError("licence token payload is not an object")

    # A token signed by us but minted for a different service, or by a
    # different deployment, is not one we should honour.
    if claims.get("iss") != issuer:
        raise LicenceError(f"licence token issuer {claims.get('iss')!r} is not {issuer!r}")
    if claims.get("aud") != audience:
        raise LicenceError(f"licence token audience {claims.get('aud')!r} is not {audience!r}")

    try:
        return LicenceClaims(
            account_id=str(claims["sub"]),
            tier=str(claims.get("tier", "free")),
            issued_at=int(claims["iat"]),
            expires_at=int(claims["exp"]),
            grace_days=int(claims.get("grace_days", 0)),
            jti=str(claims.get("jti", "")),
            device_id=claims.get("device"),
            email=claims.get("email"),
            features=claims.get("features") or {},
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LicenceError("licence token is missing required claims") from exc
