"""Unit tests for the offline licence verifier.

These use locally generated keys, so they exercise the verifier's own edge
cases. ``test_licensing_contract.py`` is what proves it agrees with the Java
signer.
"""
from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.licensing.entitlement import FREE, Status, evaluate, status_message
from app.services.licensing.token import LicenceError, verify_token

ISSUER = "https://api.mmaassist.test"
AUDIENCE = "mma-assist-desktop"
KID = "unit-test"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.fixture
def signer():
    """Signs arbitrary header/claim pairs, so malformed tokens can be built."""
    private_key = Ed25519PrivateKey.generate()
    raw_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    def sign(claims: dict, header: dict | None = None) -> str:
        head = header if header is not None else {"alg": "EdDSA", "typ": "JWT", "kid": KID}
        encoded = f"{_b64url(json.dumps(head).encode())}.{_b64url(json.dumps(claims).encode())}"
        signature = private_key.sign(encoded.encode("ascii"))
        return f"{encoded}.{_b64url(signature)}"

    sign.public_keys = {KID: raw_public}  # type: ignore[attr-defined]
    return sign


def _claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "sub": "acct-1",
        "aud": AUDIENCE,
        "jti": "jti-1",
        "iat": now,
        "exp": now + 1209600,
        "tier": "pro",
        "features": {"cloud_providers": True},
        "grace_days": 7,
    }
    base.update(overrides)
    return base


def test_valid_token_verifies(signer):
    claims = verify_token(signer(_claims()), signer.public_keys,
                          issuer=ISSUER, audience=AUDIENCE)

    assert claims.is_pro
    assert claims.feature("cloud_providers") is True
    assert claims.feature("kalshi_market") is False


@pytest.mark.parametrize("algorithm", ["none", "HS256", "RS256", "ES256", ""])
def test_algorithm_is_pinned_to_eddsa(signer, algorithm):
    """The classic JWT hole: trusting the header's choice of algorithm.

    A token whose header says ``none`` must be refused even though the rest of
    it is perfectly well formed and correctly signed.
    """
    token = signer(_claims(), header={"alg": algorithm, "typ": "JWT", "kid": KID})

    with pytest.raises(LicenceError, match="algorithm"):
        verify_token(token, signer.public_keys, issuer=ISSUER, audience=AUDIENCE)


def test_unsigned_token_is_rejected(signer):
    """`alg: none` with the signature removed entirely - the textbook forgery."""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT", "kid": KID}).encode())
    payload = _b64url(json.dumps(_claims(tier="pro")).encode())

    with pytest.raises(LicenceError):
        verify_token(f"{header}.{payload}.", signer.public_keys,
                     issuer=ISSUER, audience=AUDIENCE)


@pytest.mark.parametrize("malformed", [
    "", "not-a-token", "only.two", "a.b.c.d", "...", "!!!.???.***",
])
def test_malformed_tokens_raise_licence_error(signer, malformed):
    """Never anything other than LicenceError: the caller only handles that."""
    with pytest.raises(LicenceError):
        verify_token(malformed, signer.public_keys, issuer=ISSUER, audience=AUDIENCE)


def test_missing_claims_are_rejected(signer):
    incomplete = {"iss": ISSUER, "aud": AUDIENCE, "sub": "acct-1"}  # no iat/exp

    with pytest.raises(LicenceError, match="required claims"):
        verify_token(signer(incomplete), signer.public_keys,
                     issuer=ISSUER, audience=AUDIENCE)


def test_expiry_is_not_enforced_by_the_verifier(signer):
    """Deliberate: grace handling lives in evaluate(), not here."""
    expired = signer(_claims(exp=int(time.time()) - 100))

    claims = verify_token(expired, signer.public_keys, issuer=ISSUER, audience=AUDIENCE)

    assert claims.expires_at < time.time()
    assert evaluate(claims, now=int(time.time())).status is Status.GRACE


class TestEntitlementEvaluation:
    def test_no_token_is_free_and_wants_a_refresh(self):
        entitlement = evaluate(None)

        assert entitlement is FREE
        assert not entitlement.is_pro
        assert entitlement.should_refresh

    def test_grace_boundary_is_exclusive(self, signer):
        expiry = int(time.time()) - 1000
        claims = verify_token(signer(_claims(exp=expiry, grace_days=7)),
                              signer.public_keys, issuer=ISSUER, audience=AUDIENCE)
        grace_end = expiry + 7 * 86400

        assert evaluate(claims, now=grace_end - 1).status is Status.GRACE
        assert evaluate(claims, now=grace_end).status is Status.EXPIRED

    def test_zero_grace_days_expires_immediately(self, signer):
        expiry = int(time.time()) - 1
        claims = verify_token(signer(_claims(exp=expiry, grace_days=0)),
                              signer.public_keys, issuer=ISSUER, audience=AUDIENCE)

        assert evaluate(claims, now=expiry).status is Status.EXPIRED

    def test_expired_entitlement_offers_no_features(self, signer):
        expiry = int(time.time()) - 10_000_000
        claims = verify_token(signer(_claims(exp=expiry)), signer.public_keys,
                              issuer=ISSUER, audience=AUDIENCE)

        entitlement = evaluate(claims)

        assert entitlement.allows("cloud_providers") is False

    def test_refresh_is_requested_near_expiry_but_not_early(self, signer):
        now = int(time.time())
        claims = verify_token(signer(_claims(exp=now + 14 * 86400)), signer.public_keys,
                              issuer=ISSUER, audience=AUDIENCE)

        assert evaluate(claims, now=now).should_refresh is False

        near = verify_token(signer(_claims(exp=now + 86400)), signer.public_keys,
                            issuer=ISSUER, audience=AUDIENCE)
        assert evaluate(near, now=now).should_refresh is True

    def test_status_message_only_speaks_when_it_matters(self, signer):
        now = int(time.time())
        healthy = verify_token(signer(_claims(exp=now + 14 * 86400)), signer.public_keys,
                               issuer=ISSUER, audience=AUDIENCE)

        assert status_message(evaluate(healthy, now=now)) is None
        assert "Pro stays on" in status_message(
            evaluate(verify_token(signer(_claims(exp=now - 86400)), signer.public_keys,
                                  issuer=ISSUER, audience=AUDIENCE), now=now))
