"""The Python half of the licence-token contract.

Java signs licence tokens; this module verifies them. Neither language's test
suite can see the other, so a change to the claim set, the JWS header, or the
base64 variant would leave both suites green while every paying customer lost
access to the app they bought.

``backend/tests/fixtures/licence_contract.json`` is the shared artefact that
closes that gap. ``accounts/.../LicenceContractTest.java`` asserts the signer
still reproduces the token in it; this file asserts the verifier still accepts
it. Breaking the format fails one side or the other.

The signing key in the fixture exists only for this fixture.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.services.licensing.entitlement import Status, evaluate
from app.services.licensing.token import LicenceError, UnknownSigningKey, verify_token

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "licence_contract.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    if not FIXTURE_PATH.exists():
        pytest.fail(
            f"Missing {FIXTURE_PATH}. Regenerate it by running the Java test "
            "LicenceContractTest (it writes the fixture and fails once)."
        )
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def public_keys(contract: dict) -> dict[str, bytes]:
    encoded = contract["publicKeyBase64Url"]
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    return {contract["kid"]: raw}


def test_java_signed_token_verifies(contract, public_keys):
    """The headline assertion: a real Java-produced token verifies here."""
    claims = verify_token(
        contract["token"],
        public_keys,
        issuer=contract["issuer"],
        audience=contract["audience"],
    )

    expected = contract["expectedClaims"]
    assert claims.account_id == expected["sub"]
    assert claims.device_id == expected["device"]
    assert claims.jti == expected["jti"]
    assert claims.tier == expected["tier"]
    assert claims.email == expected["email"]
    assert claims.issued_at == expected["iat"]
    assert claims.expires_at == expected["exp"]
    assert claims.grace_days == expected["grace_days"]
    assert claims.features == expected["features"]
    assert claims.is_pro


def test_every_gated_feature_survives_the_round_trip(contract, public_keys):
    """The feature map is what the UI gates on, so it is checked field by field."""
    claims = verify_token(
        contract["token"], public_keys,
        issuer=contract["issuer"], audience=contract["audience"],
    )

    for feature in ("cloud_providers", "all_platforms", "kalshi_market", "unlimited_history"):
        assert claims.feature(feature) is True, f"{feature} did not survive"


def test_tampered_payload_is_rejected(contract, public_keys):
    """Editing the claims to grant yourself Pro must break the signature."""
    header, payload, signature = contract["token"].split(".")
    decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
    forged = decoded.replace('"tier":"pro"', '"tier":"enterprise"')
    assert forged != decoded, "the fixture no longer contains the claim being tampered with"

    repacked = base64.urlsafe_b64encode(forged.encode()).decode().rstrip("=")

    with pytest.raises(LicenceError):
        verify_token(
            f"{header}.{repacked}.{signature}", public_keys,
            issuer=contract["issuer"], audience=contract["audience"],
        )


def test_token_from_a_different_key_is_rejected(contract):
    """A validly-structured token signed by somebody else is not ours."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    impostor = Ed25519PrivateKey.generate()
    raw_public = impostor.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    with pytest.raises(LicenceError):
        verify_token(
            contract["token"], {contract["kid"]: raw_public},
            issuer=contract["issuer"], audience=contract["audience"],
        )


def test_unknown_key_id_is_distinguishable(contract):
    """A rotated key must be recoverable, not fatal - hence its own exception."""
    with pytest.raises(UnknownSigningKey) as caught:
        verify_token(
            contract["token"], {"some-other-kid": b"\x00" * 32},
            issuer=contract["issuer"], audience=contract["audience"],
        )
    assert caught.value.kid == contract["kid"]


def test_wrong_issuer_and_audience_are_rejected(contract, public_keys):
    with pytest.raises(LicenceError, match="issuer"):
        verify_token(
            contract["token"], public_keys,
            issuer="https://evil.example", audience=contract["audience"],
        )

    with pytest.raises(LicenceError, match="audience"):
        verify_token(
            contract["token"], public_keys,
            issuer=contract["issuer"], audience="some-other-app",
        )


def test_entitlement_evaluation_across_the_window(contract, public_keys):
    """The same real token, read at four points in its life."""
    claims = verify_token(
        contract["token"], public_keys,
        issuer=contract["issuer"], audience=contract["audience"],
    )
    day = 86_400

    inside = evaluate(claims, now=claims.expires_at - day)
    assert inside.status is Status.VALID and inside.is_pro

    in_grace = evaluate(claims, now=claims.expires_at + day)
    assert in_grace.status is Status.GRACE
    assert in_grace.is_pro, "an offline laptop must not lose the tier it paid for"

    lapsed = evaluate(claims, now=claims.expires_at + (claims.grace_days + 1) * day)
    assert lapsed.status is Status.EXPIRED
    assert not lapsed.is_pro
    assert lapsed.features == {}
