"""Licensing for the desktop app.

Verifies, offline, the signed statement the accounts service issues about what
this user has paid for. See ``entitlement.py`` for the rule that matters most:
a licence check never blocks anything.
"""
from .client import AccountsClient
from .entitlement import FREE, Entitlement, Status, evaluate, status_message
from .token import (
    LicenceClaims,
    LicenceError,
    UnknownSigningKey,
    verify_token,
)

__all__ = [
    "AccountsClient",
    "Entitlement",
    "FREE",
    "LicenceClaims",
    "LicenceError",
    "Status",
    "UnknownSigningKey",
    "evaluate",
    "status_message",
    "verify_token",
]
