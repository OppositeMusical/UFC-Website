"""What the app actually unlocks, given a licence token and the clock.

The rule this module exists to enforce: **a licence check never blocks
anything.** Not startup, not a prediction, not a page render. An outage at the
accounts service, an expired cached token, a machine that has been offline for
a fortnight — all of these degrade to "keep working" or "quietly drop to free",
never to a spinner.

That is not a nicety. SPEC.md section 6.1 records the same mistake being made
once already with the AI-provider status chip, where a hung Ollama stalled the
dashboard; the fix was to move the check off the render path. A licence check is
the same shape of problem with worse consequences, because the thing it would
stall is something the user has paid for.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .token import LicenceClaims

SECONDS_PER_DAY = 86_400


class Status(str, Enum):
    """Why the current entitlement is what it is."""

    VALID = "valid"
    """Inside the token's lifetime."""

    GRACE = "grace"
    """Past expiry but inside the grace window: still Pro, and worth saying so."""

    EXPIRED = "expired"
    """Past expiry and grace. Dropped to free."""

    NONE = "none"
    """No usable token at all — never signed in, or the cache was unreadable."""


@dataclass(frozen=True)
class Entitlement:
    status: Status
    tier: str
    features: Mapping[str, Any]
    expires_at: int | None = None
    grace_expires_at: int | None = None

    @property
    def is_pro(self) -> bool:
        return self.tier == "pro"

    def allows(self, feature: str) -> bool:
        return bool(self.features.get(feature, False))

    @property
    def should_refresh(self) -> bool:
        """Whether it is worth trying the server on this pass.

        True inside the last three days of the window, and always once expired.
        Refreshing earlier wastes a request; refreshing later risks the user
        being offline for the only window that mattered.
        """
        if self.status in (Status.NONE, Status.EXPIRED, Status.GRACE):
            return True
        if self.expires_at is None:
            return True
        return self.expires_at - int(time.time()) < 3 * SECONDS_PER_DAY


FREE = Entitlement(status=Status.NONE, tier="free", features={})


def evaluate(claims: LicenceClaims | None, now: int | None = None) -> Entitlement:
    """Turn verified claims into what the UI should offer."""
    if claims is None:
        return FREE

    moment = int(time.time()) if now is None else now
    grace_expires_at = claims.expires_at + claims.grace_days * SECONDS_PER_DAY

    if moment < claims.expires_at:
        return Entitlement(
            status=Status.VALID,
            tier=claims.tier,
            features=claims.features,
            expires_at=claims.expires_at,
            grace_expires_at=grace_expires_at,
        )

    if moment < grace_expires_at:
        # Deliberately keeps the paid tier. The overwhelmingly likely cause of a
        # token going stale is a laptop that has been offline, not a lapsed
        # subscription - and the server has already had its say by refusing to
        # issue a longer one.
        return Entitlement(
            status=Status.GRACE,
            tier=claims.tier,
            features=claims.features,
            expires_at=claims.expires_at,
            grace_expires_at=grace_expires_at,
        )

    return Entitlement(
        status=Status.EXPIRED,
        tier="free",
        features={},
        expires_at=claims.expires_at,
        grace_expires_at=grace_expires_at,
    )


def status_message(entitlement: Entitlement) -> str | None:
    """A short line for the Settings panel, or None when nothing needs saying."""
    if entitlement.status is Status.GRACE:
        remaining = max(
            0,
            (entitlement.grace_expires_at or 0) - int(time.time()),
        ) // SECONDS_PER_DAY
        return (
            "Couldn't reach the licence server. Pro stays on for "
            f"{remaining} more day{'s' if remaining != 1 else ''}."
        )
    if entitlement.status is Status.EXPIRED:
        return "Your Pro licence could not be renewed. Sign in again to restore it."
    return None
