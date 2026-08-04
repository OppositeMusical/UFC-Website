#!/usr/bin/env python
"""Packages the PyInstaller build into a downloadable zip and points the
marketing site's version.json at it.

Usage (from backend/, after `pyinstaller pyinstaller/app.spec`):
    python scripts/build_release.py
    python scripts/build_release.py --version 0.2.0

Writes:
    frontend/public/downloads/UFCPredictor-<version>-windows.zip
    frontend/public/version.json

The zip lands in the site's `public/` directory so `npm run dev` and
`npm run build` both serve it with no extra hosting - which is what makes
the Download page work end to end on a local machine. It is gitignored:
this is a ~100MB build artifact regenerated from `dist/`, not source. For a
real public release, upload the same zip to a release host and point
version.json's downloadUrl at that instead.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DIST_DIR = BACKEND_DIR / "dist" / "UFCPredictor"
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"
DOWNLOADS_DIR = PUBLIC_DIR / "downloads"

DEFAULT_VERSION = "0.1.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the built app for download from the site")
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"Release version (default: {DEFAULT_VERSION})")
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Keep previously built zips instead of clearing the downloads directory",
    )
    args = parser.parse_args()

    if not DIST_DIR.exists():
        sys.exit(
            f"No PyInstaller build found at {DIST_DIR}.\n"
            "Run `pyinstaller pyinstaller/app.spec` from backend/ first."
        )

    exe = DIST_DIR / "UFCPredictor.exe"
    if not exe.exists():
        sys.exit(f"{DIST_DIR} exists but has no UFCPredictor.exe - the build looks incomplete.")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.keep_old:
        # Otherwise every version ever built keeps being copied into
        # frontend/dist by `npm run build`.
        for stale in DOWNLOADS_DIR.glob("UFCPredictor-*.zip"):
            print(f"Removing old {stale.name}")
            stale.unlink()

    zip_name = f"UFCPredictor-{args.version}-windows.zip"
    zip_path = DOWNLOADS_DIR / zip_name

    files = [p for p in DIST_DIR.rglob("*") if p.is_file()]
    print(f"Zipping {len(files)} files from {DIST_DIR} -> {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for i, path in enumerate(files, 1):
            # Nest under a top-level folder so unzipping doesn't scatter
            # ~600 files into whatever directory the user extracted into.
            archive.write(path, Path("UFCPredictor") / path.relative_to(DIST_DIR))
            if i % 100 == 0 or i == len(files):
                print(f"  {i}/{len(files)}", end="\r", flush=True)
    print()

    size_bytes = zip_path.stat().st_size
    print(f"Hashing {size_bytes / (1024 * 1024):.1f} MB...")
    digest = hashlib.sha256()
    with zip_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)

    version_info = {
        "version": args.version,
        "downloadUrl": f"/downloads/{zip_name}",
        "sizeBytes": size_bytes,
        "sha256": digest.hexdigest(),
        "releasedAt": dt.date.today().isoformat(),
        "notes": "Built locally by scripts/build_release.py. For a public release, upload this zip to a release host and change downloadUrl to that URL.",
    }
    version_path = PUBLIC_DIR / "version.json"
    version_path.write_text(json.dumps(version_info, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {zip_path}  ({size_bytes / (1024 * 1024):.1f} MB)")
    print(f"Wrote {version_path}")
    print(f"sha256: {version_info['sha256']}")
    print("\nServe it:  cd frontend && npm run dev   ->  open /download")


if __name__ == "__main__":
    main()
