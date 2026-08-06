#!/usr/bin/env python
"""Publishes the portable MMA Assist build to the marketing site.

The app ships portable: a zip the user extracts wherever they like, with the
app writing its data into a `data/` folder beside the exe. Nothing is
installed. The raw PyInstaller folder inside is an implementation detail.

Full release sequence (order matters - see desktop/README.md):

    cd backend
    pyinstaller pyinstaller/app.spec        # 1. Python bundle
    cd ../desktop && npm run dist           # 2. wraps (1) into the zip
    cd ../backend
    python scripts/build_release.py         # 3. publishes (2) to the site

Writes:
    frontend/public/downloads/MMA-Assist-<version>-portable-win64.zip
    frontend/public/version.json

The zip lands in the site's `public/` directory so `npm run dev` and
`npm run build` both serve it with no extra hosting. It is gitignored: a
~230MB build artifact, not source. For a public release, upload the same
file to a release host and re-run with --github-release OWNER/REPO.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
RELEASE_DIR = REPO_ROOT / "desktop" / "release"
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"
DOWNLOADS_DIR = PUBLIC_DIR / "downloads"


def find_artifact(version: str | None, platform: str = "win") -> tuple[Path, str]:
    """Locates the electron-builder artifact for a platform, and its version.

    Windows ships a portable zip the user extracts wherever they like, with
    the app writing its data into a `data/` folder beside the exe. macOS
    ships a .dmg and keeps data in ~/Library/Application Support - a signed
    .app bundle cannot host its own data folder (see macos/README.md).

    electron-builder names these with spaces - "MMA Assist-1.2.3-win.zip" -
    which is awkward in a URL, so the published copy gets renamed.
    """
    if not RELEASE_DIR.exists():
        sys.exit(
            f"No Electron build found at {RELEASE_DIR}.\n"
            "Run `npm run dist` in desktop/ first (and `pyinstaller pyinstaller/app.spec` "
            "in backend/ before that, so the package wraps a current backend)."
        )

    if platform == "mac":
        # .dmg first: it is what a Mac user expects to download. The .zip
        # electron-builder also emits exists for auto-update, not for humans.
        patterns = ("*.dmg", "*-mac.zip", "*-arm64.zip")
    else:
        patterns = ("*-win.zip", "*.zip")

    candidates: list[Path] = []
    for pattern in patterns:
        candidates = sorted(RELEASE_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if platform == "win":
            # Don't let a mac artifact satisfy a Windows publish when both
            # are sitting in release/ - that would put a .dmg behind the
            # "Download for Windows" button.
            candidates = [c for c in candidates if "mac" not in c.stem and "arm64" not in c.stem]
        if candidates:
            break

    if not candidates:
        sys.exit(
            f"No {platform} artifact in {RELEASE_DIR} (looked for {', '.join(patterns)}).\n"
            + ("Run ./macos/build.sh on a Mac." if platform == "mac" else "Did `npm run dist` finish?")
        )

    artifact = candidates[0]
    if version:
        return artifact, version

    match = re.search(r"(\d+\.\d+\.\d+)", artifact.stem)
    if not match:
        sys.exit(f"Could not read a version out of {artifact.name} - pass --version explicitly.")
    return artifact, match.group(1)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the Electron installer to the marketing site")
    parser.add_argument("--version", help="Override the version parsed from the installer filename")
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Keep previously published installers instead of clearing the downloads directory",
    )
    parser.add_argument(
        "--download-url",
        help="Point version.json at an external URL instead of the locally served copy",
    )
    parser.add_argument(
        "--github-release",
        metavar="OWNER/REPO",
        help=(
            "Shorthand for --download-url pointing at that repo's latest release asset, e.g. "
            "OppositeMusical/UFC-Website. You still have to create the release and upload the installer."
        ),
    )
    parser.add_argument(
        "--platform",
        choices=("win", "mac"),
        default="win",
        help=(
            "Which platform's artifact to publish (default: win). The two are built on "
            "different machines, so each run merges into version.json rather than "
            "replacing it - publishing mac must not wipe the Windows entry."
        ),
    )
    parser.add_argument(
        "--notes",
        action="append",
        default=[],
        metavar="LINE",
        help=(
            "A release-note bullet; repeat for several. Shown in the app's update prompt and on "
            "the Download page, so write them for a user deciding whether to bother updating."
        ),
    )
    args = parser.parse_args()

    if args.download_url and args.github_release:
        sys.exit("Use either --download-url or --github-release, not both.")

    artifact, version = find_artifact(args.version, args.platform)

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.keep_old:
        # Only this platform's stale artifacts. Clearing everything would
        # delete the other platform's published file, which is built on a
        # different machine and cannot be regenerated here.
        stale_glob = "*-mac*" if args.platform == "mac" else "*-win*"
        for stale in DOWNLOADS_DIR.glob(stale_glob):
            print(f"Removing old {stale.name}")
            stale.unlink()

    if args.platform == "mac":
        asset_name = f"MMA-Assist-{version}-macos{artifact.suffix}"
    else:
        asset_name = f"MMA-Assist-{version}-portable-win64.zip"
    dest = DOWNLOADS_DIR / asset_name
    print(f"Copying {artifact.name} -> {dest.relative_to(REPO_ROOT)}")
    shutil.copyfile(artifact, dest)

    size_bytes = dest.stat().st_size
    print(f"Hashing {size_bytes / (1024 * 1024):.1f} MB...")
    checksum = sha256_of(dest)

    if args.github_release:
        download_url = f"https://github.com/{args.github_release}/releases/latest/download/{asset_name}"
        note = (
            f"Points at the latest GitHub release of {args.github_release}. "
            f"Create that release and upload {asset_name} as an asset, or the link 404s."
        )
    elif args.download_url:
        download_url = args.download_url
        note = "Points at an externally hosted copy. Upload the built installer there."
    else:
        download_url = f"/downloads/{asset_name}"
        note = (
            "Served locally out of frontend/public/downloads by `npm run dev` / `npm run build`. "
            "For a public release, re-run with --github-release OWNER/REPO after uploading the installer."
        )

    entry = {
        "downloadUrl": download_url,
        "fileName": asset_name,
        "kind": "dmg" if args.platform == "mac" else "portable",
        "sizeBytes": size_bytes,
        "sha256": checksum,
    }

    version_path = PUBLIC_DIR / "version.json"
    existing = {}
    if version_path.exists():
        try:
            existing = json.loads(version_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    # Merge, don't replace. Windows and macOS artifacts are produced on
    # separate machines, so a mac publish must leave the Windows entry alone
    # - it cannot be regenerated from here.
    platforms = dict(existing.get("platforms") or {})
    # A platform entry from an older version is stale the moment the version
    # moves on: it would advertise a download that no longer matches.
    if existing.get("version") != version:
        platforms = {}
    platforms[args.platform] = entry

    version_info = {
        "version": version,
        "releasedAt": dt.date.today().isoformat(),
        # Reuse the previous notes only when this run supplied none AND the
        # version is unchanged - carrying them into a new version would lie
        # about what changed.
        "releaseNotes": list(args.notes)
            or (existing.get("releaseNotes", []) if existing.get("version") == version else []),
        "platforms": platforms,
        "notes": note,
    }

    # Windows also stays at the top level. Installed copies poll this same
    # file for updates and read downloadUrl/sha256 from the root, so moving
    # them under "platforms" would break every already-shipped client.
    version_info.update(platforms.get("win", {}))

    version_path.write_text(json.dumps(version_info, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {dest}  ({size_bytes / (1024 * 1024):.1f} MB)")
    print(f"Wrote {version_path}")
    print(f"sha256: {checksum}")
    print("\nServe it:  cd frontend && npm run dev   ->  open /download")


if __name__ == "__main__":
    main()
