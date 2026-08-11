#!/usr/bin/env python
"""Publishes the MMA Assist Windows builds to the marketing site.

Windows ships two artifacts from one build:

  * an NSIS installer (primary) - the self-updating channel. electron-updater
    only supports NSIS on Windows, so this is the one that can replace itself
    in place when the user clicks Update. Data lives in the user profile.
  * a portable zip - extract anywhere, data in a `data/` folder beside the
    exe, nothing installed. No in-app updates; download and replace manually.

macOS ships a .dmg and keeps data in ~/Library/Application Support - a signed
.app bundle cannot host its own data folder (see macos/README.md).

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


# Which electron-builder outputs to publish, per platform, in the order the
# entries should be written. The first is primary: it is what the Download
# page offers and what version.json advertises at the top level.
#
# Windows publishes two. The NSIS installer is primary because it is the
# only Windows target electron-updater can update in place (`zip` and
# `portable` are not auto-updatable), so it is the channel that gets
# self-updates. The portable zip stays for people who want no installer at
# all - they keep the manual download-and-replace flow.
ARTIFACT_KINDS: dict[str, tuple[tuple[str, str, str], ...]] = {
    # (glob, kind, published-name template)
    "win": (
        # The installer's published name MUST match the filename inside
        # latest.yml. electron-builder writes "MMA Assist-<v>-setup-x64.exe"
        # to disk but URL-encodes the space to a hyphen in latest.yml, and
        # electron-updater resolves the asset by that encoded name - so
        # renaming to anything else (an earlier draft used "win64") 404s the
        # download and updates silently never install. check_update_manifest
        # below enforces the match rather than trusting this string.
        ("*-setup-*.exe", "nsis", "MMA-Assist-{version}-setup-x64.exe"),
        ("*-win.zip", "portable", "MMA-Assist-{version}-portable-win64.zip"),
    ),
    # The .zip electron-builder also emits for mac exists for auto-update,
    # not for humans, so it is not published to the site.
    "mac": (("*.dmg", "dmg", "MMA-Assist-{version}-macos.dmg"),),
}

# electron-updater reads these from the *release host*, not the website.
# They are copied alongside the installers only so the upload step is one
# folder. Resolved by exact name against the release being published - see
# the blockmap handling in main().


def find_artifacts(version: str | None, platform: str = "win") -> tuple[list[tuple[Path, str, str]], str]:
    """Locates every publishable electron-builder artifact for a platform.

    Returns [(path, kind, published_name)] plus the resolved version.
    electron-builder names these with spaces - "MMA Assist-1.2.3-win.zip" -
    which is awkward in a URL, so published copies get renamed.
    """
    if not RELEASE_DIR.exists():
        sys.exit(
            f"No Electron build found at {RELEASE_DIR}.\n"
            "Run `npm run dist` in desktop/ first (and `pyinstaller pyinstaller/app.spec` "
            "in backend/ before that, so the package wraps a current backend)."
        )

    found: list[tuple[Path, str, str]] = []
    resolved_version = version

    for pattern, kind, name_template in ARTIFACT_KINDS[platform]:
        candidates = sorted(RELEASE_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if platform == "win":
            # Don't let a mac artifact satisfy a Windows publish when both
            # are sitting in release/ - that would put a .dmg behind the
            # "Download for Windows" button.
            candidates = [c for c in candidates if "mac" not in c.stem and "arm64" not in c.stem]
        if not candidates:
            continue

        artifact = candidates[0]
        if resolved_version is None:
            match = re.search(r"(\d+\.\d+\.\d+)", artifact.stem)
            if match:
                resolved_version = match.group(1)
        found.append((artifact, kind, name_template))

    if not found:
        globs = ", ".join(g for g, _k, _n in ARTIFACT_KINDS[platform])
        sys.exit(
            f"No {platform} artifact in {RELEASE_DIR} (looked for {globs}).\n"
            + ("Run ./macos/build.sh on a Mac." if platform == "mac" else "Did `npm run dist` finish?")
        )

    if resolved_version is None:
        sys.exit("Could not read a version out of the artifact names - pass --version explicitly.")

    return [(p, k, n.format(version=resolved_version)) for p, k, n in found], resolved_version


def check_update_manifest(nsis_asset_name: str, version: str) -> None:
    """Fails the publish if latest.yml disagrees with what we are shipping.

    electron-updater downloads whatever filename latest.yml names. If the
    asset uploaded to the release is called something else, or is from a
    different build, the update 404s or fails its sha512 check - and does so
    *silently*, because a failed check just leaves the app reporting that it
    is current. There is no error a user would ever report.

    Cheap to verify here, so verify it here.
    """
    manifest = RELEASE_DIR / "latest.yml"
    if not manifest.exists():
        sys.exit(
            "No latest.yml in desktop/release/.\n"
            "electron-updater polls that file; without it, in-app updates never fire.\n"
            "It is produced by the nsis target - did `npm run dist` build one?"
        )

    text = manifest.read_text(encoding="utf-8")
    named = re.search(r"^path:\s*(.+?)\s*$", text, re.MULTILINE)
    declared_version = re.search(r"^version:\s*(.+?)\s*$", text, re.MULTILINE)

    if not named:
        sys.exit(f"Could not read a 'path:' out of {manifest} - refusing to publish blind.")
    if named.group(1) != nsis_asset_name:
        sys.exit(
            f"latest.yml names '{named.group(1)}' but this run publishes "
            f"'{nsis_asset_name}'.\nelectron-updater fetches the name in latest.yml, so the "
            "update would 404. Fix ARTIFACT_KINDS or nsis.artifactName so the two agree."
        )
    if declared_version and declared_version.group(1) != version:
        sys.exit(
            f"latest.yml is for version {declared_version.group(1)} but the artifacts are "
            f"{version}. Stale build output - re-run `npm run dist`."
        )
    print(f"latest.yml agrees: {named.group(1)} @ {version}")


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

    artifacts, version = find_artifacts(args.version, args.platform)

    print("Publishing:")
    for artifact, kind, asset_name in artifacts:
        # Print the SOURCE filename too. desktop/release/ accumulates old
        # builds, and the globs match by pattern - seeing "0.4.0-win.zip"
        # about to be published as "0.5.0-portable" is the only warning you
        # would get before shipping a mislabelled artifact.
        print(f"  {kind:9} {artifact.name}  ->  {asset_name}")

    if args.platform == "win":
        nsis = next((name for _p, kind, name in artifacts if kind == "nsis"), None)
        if nsis is None:
            sys.exit(
                "No NSIS installer in desktop/release/. That is the only Windows target "
                "electron-updater can update in place - publishing without it means no "
                "in-app updates for this release."
            )
        check_update_manifest(nsis, version)

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.keep_old:
        # Only this platform's stale artifacts. Clearing everything would
        # delete the other platform's published file, which is built on a
        # different machine and cannot be regenerated here.
        #
        # Derived from the published-name templates rather than hand-written,
        # because a hand-written "*-win*" silently missed every NSIS artifact:
        # the installer is published as MMA-Assist-<v>-setup-x64.exe, which
        # has no "-win" in it. Old installers and their blockmaps therefore
        # accumulated here across releases and turned up in the upload list
        # below, inviting a previous version's blockmap to be attached to
        # this version's release. The trailing * catches .blockmap.
        for _, _, template in ARTIFACT_KINDS[args.platform]:
            for stale in DOWNLOADS_DIR.glob(template.format(version="*") + "*"):
                print(f"Removing old {stale.name}")
                stale.unlink()

    def url_for(asset_name: str) -> tuple[str, str]:
        if args.github_release:
            return (
                f"https://github.com/{args.github_release}/releases/latest/download/{asset_name}",
                f"Points at the latest GitHub release of {args.github_release}. "
                f"Create that release and upload the assets, or the links 404.",
            )
        if args.download_url:
            return args.download_url, "Points at an externally hosted copy."
        return (
            f"/downloads/{asset_name}",
            "Served locally out of frontend/public/downloads by `npm run dev` / `npm run build`. "
            "For a public release, re-run with --github-release OWNER/REPO after uploading.",
        )

    entries: list[tuple[str, dict]] = []
    note = ""
    for artifact, kind, asset_name in artifacts:
        dest = DOWNLOADS_DIR / asset_name
        print(f"Copying {artifact.name} -> {dest.relative_to(REPO_ROOT)}")
        shutil.copyfile(artifact, dest)

        size_bytes = dest.stat().st_size
        print(f"Hashing {size_bytes / (1024 * 1024):.1f} MB...")
        checksum = sha256_of(dest)

        download_url, note = url_for(asset_name)
        entries.append(
            (
                kind,
                {
                    "downloadUrl": download_url,
                    "fileName": asset_name,
                    "kind": kind,
                    "sizeBytes": size_bytes,
                    "sha256": checksum,
                },
            )
        )

    # latest.yml is what electron-updater actually polls, and .blockmap is
    # what makes the download differential instead of a fresh 240MB every
    # release. Neither is served from the website - they belong to the
    # release host - but they are copied here so the upload is one folder,
    # and because forgetting latest.yml is a silent failure: the app simply
    # never notices the release exists.
    update_metadata: list[str] = []
    if args.platform == "win":
        # Blockmaps are taken from THIS release's installer by name, not by a
        # "*.blockmap" glob. desktop/release/ is never cleaned between builds,
        # so a glob accumulated one blockmap per version ever built and the
        # upload list below grew every release - inviting a stale version's
        # blockmap onto the new release, where it means nothing and hides the
        # one that matters.
        wanted: list[tuple[Path, str]] = [(RELEASE_DIR / "latest.yml", "latest.yml")]
        for source, kind, published_name in artifacts:
            if kind == "nsis":
                wanted.append(
                    (
                        source.with_name(source.name + ".blockmap"),
                        # Spaces -> hyphens, for the same reason the installer
                        # is renamed: electron-updater fetches the blockmap by
                        # appending ".blockmap" to the installer's URL, so
                        # "MMA Assist-...exe.blockmap" is a 404 against a
                        # hyphenated installer name. That one degrades quietly
                        # - the update still works, it just downloads all
                        # 178MB instead of the changed blocks, silently
                        # discarding the reason NSIS was chosen over the zip.
                        published_name + ".blockmap",
                    )
                )

        for meta, published in wanted:
            if not meta.exists():
                continue
            shutil.copyfile(meta, DOWNLOADS_DIR / published)
            update_metadata.append(published)

    # The primary artifact (first in ARTIFACT_KINDS) is what the platform
    # entry and the legacy top-level fields describe.
    entry = entries[0][1]
    secondary = {kind: data for kind, data in entries[1:]}

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
    # Windows publishes a second, non-updating artifact. Keyed separately
    # rather than nested inside the win entry so a client can feature-detect
    # it with one lookup and ignore it entirely if it does not care.
    if args.platform == "win" and "portable" in secondary:
        platforms["winPortable"] = secondary["portable"]

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

    print()
    for kind, data in entries:
        print(f"  {kind:9} {data['fileName']}  ({data['sizeBytes'] / (1024 * 1024):.1f} MB)")
        print(f"            sha256 {data['sha256']}")
    print(f"\nWrote {version_path}")

    if args.platform == "win":
        if update_metadata:
            print("\nUpload these to the GitHub release as well:")
            for name in sorted(update_metadata):
                print(f"  {name}")
            print(
                "\n  latest.yml is what the installed app polls for updates. Without it, "
                "in-app\n  updates silently never fire - the app just keeps reporting that "
                "it is current."
            )
        else:
            print(
                "\nWARNING: no latest.yml in desktop/release/. In-app updates will not work "
                "for this\n  release. It is generated by the nsis target - check that "
                "`npm run dist` built one."
            )

    print("\nServe it:  cd frontend && npm run dev   ->  open /download")


if __name__ == "__main__":
    main()
