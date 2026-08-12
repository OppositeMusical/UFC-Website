#!/usr/bin/env python
"""Bumps the app version.

`desktop/package.json` is the single source of truth: electron-builder
stamps the installer from it, the Electron main process passes it to the
backend at spawn time, and build_release.py reads it back off the installer
filename. So a release is exactly one number in one file - this script
edits it and prints the rest of the release sequence.

    python scripts/set_version.py 0.2.0
    python scripts/set_version.py --show
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DESKTOP_PACKAGE_JSON = REPO_ROOT / "desktop" / "package.json"
# npm keeps the version in the lockfile too, in two places: the root object
# and the "" entry under packages. `npm version` updates both, so this script
# has to as well or the two drift apart depending on which was used to bump.
DESKTOP_PACKAGE_LOCK = REPO_ROOT / "desktop" / "package-lock.json"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_version() -> str:
    data = json.loads(DESKTOP_PACKAGE_JSON.read_text(encoding="utf-8"))
    return data["version"]


def write_version(version: str) -> None:
    # Edited as text, not re-serialised from the parsed dict: json.dump
    # would reformat the whole file and bury a one-line version bump in a
    # diff nobody wants to review.
    raw = DESKTOP_PACKAGE_JSON.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{version}\g<2>", raw, count=1
    )
    if count != 1:
        sys.exit(f"Could not find a version field to replace in {DESKTOP_PACKAGE_JSON}")
    DESKTOP_PACKAGE_JSON.write_text(updated, encoding="utf-8")

    if not DESKTOP_PACKAGE_LOCK.exists():
        return
    # Only the first two occurrences: the root object and the "" package
    # entry, both of which sit above the dependency tree. A blanket replace
    # would rewrite the version of every dependency that happens to share the
    # old number.
    raw_lock = DESKTOP_PACKAGE_LOCK.read_text(encoding="utf-8")
    updated_lock, lock_count = re.subn(
        r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{version}\g<2>", raw_lock, count=2
    )
    if lock_count:
        DESKTOP_PACKAGE_LOCK.write_text(updated_lock, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the desktop app version")
    parser.add_argument("version", nargs="?", help="New version, e.g. 0.2.0")
    parser.add_argument("--show", action="store_true", help="Print the current version and exit")
    args = parser.parse_args()

    if args.show or not args.version:
        print(read_version())
        return

    if not SEMVER_RE.match(args.version):
        sys.exit(f"'{args.version}' is not a plain x.y.z version.")

    old = read_version()
    if args.version == old:
        print(f"Already at {old}.")
        return

    write_version(args.version)
    print(f"{old} -> {args.version}  ({DESKTOP_PACKAGE_JSON.relative_to(REPO_ROOT)})")
    print(
        "\nNow rebuild and publish (see README 'Cutting a release' for the\n"
        "PowerShell that recovers the signing password):\n"
        "  cd backend   && pyinstaller pyinstaller/app.spec\n"
        "  cd ../desktop && .\\scripts\\sign-backend.ps1 -Password <pfx>\n"
        "                   $env:CSC_KEY_PASSWORD = <pfx>; npm run dist\n"
        '  cd ../backend && python scripts/build_release.py --notes "What changed"\n'
        "\nsign-backend.ps1 must run BEFORE npm run dist - electron-builder only\n"
        "copies UFCPredictor.exe in as a resource, so signing it afterwards\n"
        "leaves the copy inside the installer unsigned.\n"
    )


if __name__ == "__main__":
    main()
