# macOS support

Build tooling for the macOS version. **Not** a separate copy of the app —
`desktop/` (Electron) and `backend/` (Flask) are already cross-platform, and
forking them would double the maintenance for something electron-builder
handles with config. What lives here is the mac-only build script,
entitlements, and the notes below.

## You cannot build this from Windows

PyInstaller does not cross-compile. It freezes *the interpreter and native
extensions of the machine it runs on*, and this app depends on platform-
specific binaries — `onnxruntime`, `tokenizers`, and SQLite all ship compiled
`.dylib`/`.so` files. There is no flag that makes a Windows machine emit a Mac
binary.

So the macOS build must happen on:

- a Mac (Apple Silicon or Intel), or
- a macOS GitHub Actions runner (`runs-on: macos-14`), or
- a Mac in a CI service

Everything in this repo is ready for that. **None of it has been executed** —
it was written on Windows, so treat the first run as a debugging session
rather than a release.

## Build

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt

./macos/build.sh
```

Produces `desktop/release/`:
- `MMA Assist-<version>-arm64.dmg` / `-x64.dmg` — the normal way to ship a Mac app
- matching `.zip` files — needed if you ever add auto-update

## Gatekeeper: worse than SmartScreen, and not optional

On Windows an unsigned app shows a warning the user can click past. **macOS
does not offer that path for downloaded apps.** Anything with the
quarantine attribute that isn't signed *and notarized* is refused outright,
usually with *"MMA Assist is damaged and can't be opened. You should move it
to the Bin."* — which reads as corruption, not as a security prompt. Most
users will delete it and assume the download is broken.

Clearing that needs all three:

1. **An Apple Developer account** — $99/year, no free tier for this
2. **A Developer ID Application certificate** — signs the `.app`
3. **Notarization** — upload to Apple, they scan it, then staple the ticket

With `hardenedRuntime: true` already set in `desktop/package.json`, once you
have an identity:

```bash
export APPLE_TEAM_ID=XXXXXXXXXX
export APPLE_ID=you@example.com
export APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
./macos/build.sh
```

electron-builder signs and notarizes automatically when those are present.

**Without a developer account**, your realistic options are:
- Tell users to run `xattr -dr com.apple.quarantine "/Applications/MMA Assist.app"` —
  works, but asking people to strip a security attribute from an unsigned
  binary is a bad thing to normalise
- Right-click → Open, which still works for locally-built apps but is
  increasingly restricted for downloaded ones
- Don't ship a Mac build until you have one

## What differs from Windows at runtime

| | Windows | macOS |
|---|---|---|
| Distribution | portable zip, extract anywhere | `.dmg`, drag to Applications |
| Data location | `data/` beside the exe | `~/Library/Application Support/MMA Assist` |
| Backend binary | `UFCPredictor.exe` | `UFCPredictor` |
| Keyring | Credential Manager | Keychain |
| Closing the window | quits the app | app stays in the Dock |
| Process teardown | `taskkill /T` | `SIGTERM`, then `SIGKILL` |

**The data location is the one that matters.** macOS is deliberately *not*
portable. A packaged `.app` is a signed bundle and `process.execPath` points
inside it, so writing a `data/` folder beside the binary would place user data
within the bundle — breaking the code signature, getting wiped by any update
that replaces the `.app`, and failing outright in `/Applications` for a
non-admin user. `desktop/backend.js::resolveDataDir()` branches on
`process.platform` for exactly this reason.

## Universal vs per-architecture

The config builds `arm64` and `x64` separately rather than a universal
binary. A universal build would need PyInstaller run twice and the results
`lipo`-merged, and would roughly double an already-230MB download. Two
separate artifacts means the Download page has to pick the right one — Apple
Silicon users running the x64 build would get it working under Rosetta, but
slowly.

## Not done

- Nothing here has been run. No Mac was available.
- No Apple Developer identity, so signing and notarization are untested.
- The Download page does not yet detect Apple Silicon vs Intel.
- No icon (`.icns`); the app will use Electron's default.
