# UFC Predictor - Electron shell

Wraps the existing Flask app in a real desktop window instead of opening a
browser tab. The backend is unchanged: Electron spawns it as a child
process, waits for `/health`, and points a `BrowserWindow` at it.

Nothing about the UI was rewritten - the Jinja templates, routes, RAG
pipeline and tests are the same code that runs standalone.

## Run it (development)

```powershell
cd desktop
npm install          # first time only
npm start
```

That spawns `backend/.venv/Scripts/python.exe run.py` with a free port and
`--no-browser`. The backend must have its virtualenv set up already
(`pip install -r requirements.txt` in `backend/`).

### If `npm start` fails with `Cannot read properties of undefined (reading 'requestSingleInstanceLock')`

Your shell has `ELECTRON_RUN_AS_NODE=1` set - **VS Code's integrated
terminal sets this**. It makes the Electron binary behave as plain Node, so
`require("electron")` returns a path string instead of the API and every
`app.*` call fails. Launch from a normal terminal, or clear it first:

```powershell
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm start
```

## Build an installer

> **Rebuild the PyInstaller bundle first, every time `backend/` changes.**
> electron-builder copies `backend/dist/UFCPredictor` in as-is; it has no
> idea the Python source moved on. Skipping this ships a stale backend and
> the failure is confusing rather than obvious - a backend built before
> `--port` existed ignores the flag, binds 8765 instead of the port
> Electron assigned, and the app dies on a health-check timeout while a
> perfectly healthy server sits on the wrong port.

The packaged app ships the PyInstaller build as an extra resource, so build
that first:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pyinstaller pyinstaller/app.spec        # -> backend/dist/UFCPredictor

cd ..\desktop
npm run dist                            # -> desktop/release/*.zip (portable)
npm run dist:dir                        # unpacked, faster, for testing
```

The zip is large (~230MB; ~630MB extracted: Electron runtime + the Python
bundle + the 28MB seeded fighter database). That is the cost of shipping a
Python app to machines with no Python. Note zip/deflate compresses this
worse than the NSIS installer's LZMA did - the tradeoff for extracting once
rather than unpacking to temp on every launch.

## Portable, not installed

The app ships as a **zip the user extracts wherever they like**. There is no
installer, nothing in Program Files, and nothing in AppData.

```
C:\wherever\they\extracted\
├── UFC Predictor.exe      ← run this
├── resources\             ← app + bundled Python backend
└── data\                  ← created on first launch
    ├── chroma_db\             25MB, seeded from the bundle
    └── ufc_predictor.db       fighters, chats, settings
```

`backend.js::resolveDataDir()` decides where `data/` goes, in this order:

1. **`UFC_PREDICTOR_DATA_DIR` if already set** — how tests and dev runs point
   somewhere specific. Overriding it silently would make them unreproducible.
2. **Packaged: `<folder containing the exe>/data`** — resolved from
   `process.execPath` at every launch, not stored anywhere, so moving the
   whole folder to another drive or a USB stick just works.
3. **Otherwise `%LOCALAPPDATA%`** — the fallback when that folder isn't
   writable (extracted into Program Files, a read-only share, a mounted
   image). It degrades rather than failing: the data re-seeds from the
   bundle, so nothing is lost.

Electron passes the result down as `UFC_PREDICTOR_DATA_DIR`, so the Python
side stays generic and has no knowledge of Electron's layout.

### Only one copy runs at a time

Electron's single-instance lock is **app-wide**, not per-data-directory, so
two portable folders can't run side by side even though they have separate
databases. That's stricter than necessary; scoping it per data directory
would need a lock file rather than Electron's built-in lock.

## Code signing (self-signed, for testing)

Builds are signed with a locally generated certificate: SHA256 digest,
SHA256 RFC3161 timestamp from DigiCert.

```powershell
.\scripts\new-signing-cert.ps1 -Password "<pick one>"   # once per machine
.\scripts\sign-backend.ps1     -Password "<same>"       # BEFORE npm run dist
$env:CSC_KEY_PASSWORD = "<same>"
npm run dist                                            # signs app + installer
.\scripts\trust-cert.ps1                                # trust it on this machine
```

`sign-backend.ps1` must run **before** `npm run dist`. electron-builder signs
the Electron app, the uninstaller and the installer, but only *copies*
`backend/dist/UFCPredictor/UFCPredictor.exe` in as a resource — signing that
afterwards leaves the copy inside the installer unsigned.

### What this actually achieves

On machines where you install the `.cer` into Trusted Root, the UAC prompt
shows **the publisher name instead of "Unknown Publisher"**, and
`signtool verify /pa` passes.

**It does not clear SmartScreen for the public.** SmartScreen reputation is
keyed to a publicly-trusted certificate that has accumulated download
history; a self-signed cert has neither, and no amount of local trust changes
what Microsoft's reputation service thinks. Anyone downloading the installer
from the internet still gets "Windows protected your PC". Only a purchased
certificate — ideally EV, which starts with reputation — removes that, which
is why §14 of the spec still lists signing as an open item.

### Handle the .pfx like a password

`desktop/certs/` is gitignored. The `.pfx` holds the private key: anyone with
it can sign anything as this publisher, and on a machine that trusts the root
that software runs without a warning. Never commit it, and only install the
root cert on machines you control (`trust-cert.ps1 -Remove` undoes it).

### Signing changes the file, so re-publish after signing

Signing rewrites the binary, so its SHA-256 and size change. If a release is
already published, upload the signed installer to replace the asset and then
re-run `build_release.py` — otherwise the checksum on the Download page
describes a file nobody has.

## Versioning and updates

`desktop/package.json`'s `version` is the **single source of truth**.
electron-builder stamps the installer from it, `main.js` passes it to the
backend as `--app-version`, and `build_release.py` reads it back off the
installer filename. The Python side declares no version of its own, so the
two cannot drift and report different numbers.

Cutting a release:

```powershell
python backend\scripts\set_version.py 0.2.0   # bumps package.json
cd backend   ; pyinstaller pyinstaller/app.spec
cd ..\desktop ; npm run dist
cd ..\backend ; python scripts\build_release.py --notes "What changed" --notes "And this"
```

Installed copies check `Config.UPDATE_MANIFEST_URL` (the same
`version.json` the Download page reads) at most every 6 hours, and show a
banner on the dashboard plus a section in Settings when something newer
exists. Publishing the manifest is the only step needed to announce a
release - there is no separate update feed.

**The app never self-updates.** It links the user to the download page so
they run the installer themselves. Auto-replacing an executable on someone's
machine is a much bigger trust ask than this app needs to make, and the
download page is where the SmartScreen warning and checksum live.

Point the check somewhere else for testing:

```powershell
$env:UFC_PREDICTOR_UPDATE_URL = "http://localhost:5174/version.json"
$env:UFC_PREDICTOR_DOWNLOAD_PAGE_URL = "http://localhost:5174/download"
```

A dev run (no `--app-version`) reports `0.0.0-dev` and skips the check
entirely rather than comparing against a made-up version.

## How it fits together

| File | Role |
| --- | --- |
| `main.js` | Window lifecycle, menu, single-instance lock, external-link handling |
| `backend.js` | Picks a free port, spawns the backend, polls `/health`, kills the process tree on quit |
| `preload.js` | Exposes only `window.ufcPredictor.isDesktop` - the UI needs nothing else |
| `splash.html` | Shown while the backend boots (first launch loads the ONNX embedder + Chroma index) |

### Decisions worth knowing

- **A free port is chosen per launch**, not the fixed 8765. A hard-coded
  port collides with a second copy, an unrelated dev server, or a leftover
  process from a crash - and the symptom is a window that never loads.
- **The child is killed with `taskkill /T`** on Windows. The PyInstaller exe
  is a process tree (bootloader -> real app) and `child.kill()` only signals
  the parent, leaving an orphaned server holding the SQLite file and a port.
- **Startup failures show the backend's own output** in the error dialog. A
  Python traceback is almost always the real answer and is otherwise
  invisible in a packaged app with no console.
- **Off-site links open in the real browser** via `setWindowOpenHandler` and
  `will-navigate`. A chrome-less Electron window is a bad place to land on
  an external site, and worse for anything asking for credentials.
- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`.

## Standalone mode still works

`python run.py` behaves exactly as before - binds the default port and opens
your browser. Electron only changes things by passing `--port N
--no-browser`.
