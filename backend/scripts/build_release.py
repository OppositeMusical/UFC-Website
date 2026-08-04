#!/usr/bin/env python
"""Publishes the Electron desktop installer to the marketing site.

The site hands users the Electron build - a normal Windows installer that
puts "UFC Predictor" in the Start menu and opens in its own window. The raw
PyInstaller folder is an implementation detail bundled inside it, not
something a user should be downloading and unzipping.

Full release sequence (order matters - see desktop/README.md):

    cd backend
    pyinstaller pyinstaller/app.spec        # 1. Python bundle
    cd ../desktop && npm run dist           # 2. wraps (1) into the installer
    cd ../backend
    python scripts/build_release.py         # 3. publishes (2) to the site

Writes:
    frontend/public/downloads/UFC-Predictor-Setup-<version>.exe
    frontend/public/version.json

The installer lands in the site's `public/` directory so `npm run dev` and
`npm run build` both serve it with no extra hosting. It is gitignored: a
~190MB build artifact, not source. For a public release, upload the same
file somewhere and re-run with --github-release OWNER/REPO.
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


def find_installer(version: str | None) -> tuple[Path, str]:
    """Locates the electron-builder NSIS output and the version it encodes.

    electron-builder names it "UFC Predictor Setup 1.2.3.exe" - spaces and
    all - which is awkward in a URL, so the published copy gets renamed.
    """
    if not RELEASE_DIR.exists():
        sys.exit(
            f"No Electron build found at {RELEASE_DIR}.\n"
            "Run `npm run dist` in desktop/ first (and `pyinstaller pyinstaller/app.spec` "
            "in backend/ before that, so the installer wraps a current backend)."
        )

    candidates = sorted(
        (p for p in RELEASE_DIR.glob("*Setup*.exe") if not p.name.endswith(".__uninstaller.exe")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        sys.exit(f"No installer (*Setup*.exe) in {RELEASE_DIR}. Did `npm run dist` finish?")

    installer = candidates[0]
    if version:
        return installer, version

    match = re.search(r"(\d+\.\d+\.\d+)", installer.stem)
    if not match:
        sys.exit(f"Could not read a version out of {installer.name} - pass --version explicitly.")
    return installer, match.group(1)


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
    args = parser.parse_args()

    if args.download_url and args.github_release:
        sys.exit("Use either --download-url or --github-release, not both.")

    installer, version = find_installer(args.version)

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.keep_old:
        # Otherwise every version ever published keeps getting copied into
        # frontend/dist by `npm run build`.
        for stale in list(DOWNLOADS_DIR.glob("*.exe")) + list(DOWNLOADS_DIR.glob("*.zip")):
            print(f"Removing old {stale.name}")
            stale.unlink()

    asset_name = f"UFC-Predictor-Setup-{version}.exe"
    dest = DOWNLOADS_DIR / asset_name
    print(f"Copying {installer.name} -> {dest.relative_to(REPO_ROOT)}")
    shutil.copyfile(installer, dest)

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

    version_info = {
        "version": version,
        "downloadUrl": download_url,
        "fileName": asset_name,
        "kind": "installer",
        "sizeBytes": size_bytes,
        "sha256": checksum,
        "releasedAt": dt.date.today().isoformat(),
        "notes": note,
    }
    version_path = PUBLIC_DIR / "version.json"
    version_path.write_text(json.dumps(version_info, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {dest}  ({size_bytes / (1024 * 1024):.1f} MB)")
    print(f"Wrote {version_path}")
    print(f"sha256: {checksum}")
    print("\nServe it:  cd frontend && npm run dev   ->  open /download")


if __name__ == "__main__":
    main()
