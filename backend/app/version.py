"""Runtime version of the installed app, plus semantic-version comparison.

There is deliberately no version constant here. The shipped product is the
Electron desktop app, so `desktop/package.json` is the single source of
truth - electron-builder stamps the installer from it, and the Electron
main process passes `--app-version` down when it spawns this backend.
Duplicating the number in Python would just create something to forget to
bump.

Running the backend directly (no Electron) is a development path and
reports DEV_VERSION, which disables update checks rather than inventing a
version to compare against.
"""
from __future__ import annotations

import re

DEV_VERSION = "0.0.0-dev"

_current_version = DEV_VERSION

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+](.+))?$")


def set_current_version(version: str | None) -> None:
    global _current_version
    _current_version = version.strip() if version and version.strip() else DEV_VERSION


def get_current_version() -> str:
    return _current_version


def is_dev_build() -> bool:
    return _current_version == DEV_VERSION


def parse_version(version: str) -> tuple[int, int, int, int] | None:
    """Returns a sortable tuple, or None if the string isn't semver.

    The trailing element ranks a prerelease below its own release: 1.2.0-rc1
    must not read as newer than 1.2.0. Prerelease identifiers aren't ordered
    against each other beyond that - this app ships plain x.y.z releases and
    the extra precision would be untested code.
    """
    match = _SEMVER_RE.match(version.strip())
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    return (int(major), int(minor), int(patch), 0 if prerelease else 1)


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is a strictly newer release than `current`.

    Compared numerically, not lexically - "0.10.0" > "0.9.0" is the whole
    reason this exists. Unparseable input returns False: an update prompt
    driven by a malformed manifest is worse than no prompt.
    """
    parsed_candidate = parse_version(candidate)
    parsed_current = parse_version(current)
    if parsed_candidate is None or parsed_current is None:
        return False
    return parsed_candidate > parsed_current
