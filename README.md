# UFC Predictor

An MMA-themed product in three parts:

| Directory | What it is |
|---|---|
| **`backend/`** | The application: Python/Flask, serving its own UI (Jinja + vanilla JS). Local (Ollama) or cloud AI (OpenAI, Gemini, Deepseek, Claude), PrizePicks/DraftKings/Kalshi prediction pages, a chatbot, and a ChromaDB RAG layer over real UFC fighter stats. |
| **`desktop/`** | The Electron shell that ships it as a Windows desktop app. Spawns the backend as a child process and renders its UI in a native window. **This is the shipped product.** |
| **`frontend/`** | A static marketing site (React + Vite) that explains the product and serves the installer. |

**Full technical spec** — architecture, data models, API contracts, scraper ethics, packaging, versioning: [`docs/SPEC.md`](docs/SPEC.md).
**Electron shell design notes**: [`desktop/README.md`](desktop/README.md).

## Quick start

### The desktop app (what users get)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\desktop
npm install
npm start
```

Electron picks a free port, starts the backend on it, and opens a window once
`/health` answers.

> If `npm start` dies with `Cannot read properties of undefined (reading
> 'requestSingleInstanceLock')`, your shell has `ELECTRON_RUN_AS_NODE=1` set —
> **VS Code's integrated terminal does this**. See [`desktop/README.md`](desktop/README.md).

**No scraping needed before your first prediction.** The app ships with a
pre-scraped database of 6,746 fighters (3,484 carrying full stats), copied into
your data directory on first launch. Refresh it whenever from Settings → Sync
Now. See §10 of the spec.

Predictions do need an AI provider: install [Ollama](https://ollama.com) and
`ollama pull llama3.1` to stay fully offline, or paste a cloud API key into
Settings.

### Backend on its own (development)

```powershell
cd backend
.venv\Scripts\Activate.ps1
python run.py
```

Serves the identical UI at `http://127.0.0.1:8765/` in your browser. This is a
development convenience — the shipped product is the Electron build.

### Marketing site

```powershell
cd frontend
npm install
npm run dev      # dev server
npm run build    # production build -> frontend/dist
npm test         # vitest
```

## Tests

```powershell
cd backend  ; .venv\Scripts\Activate.ps1 ; pip install -r requirements-dev.txt ; pytest tests
cd frontend ; npm test
```

```powershell
cd desktop   ; npm test          # packaging whitelist + updater error mapping
```

**186 tests** — 113 backend, 42 frontend, 31 desktop. No network calls: the
scraper, AI providers and update checks are all exercised against mocked HTTP.

The desktop suite is small but load-bearing. It asserts that every root `.js`
is matched by `build.files` and that every relative `require` resolves to a
packaged file — a regression test for the release that shipped without
`datamigrate.js` and crashed on launch, which passed every other suite because
nothing else launches the *packaged* app.

## Cutting a release

Each step's output feeds the next, and **nothing detects a stale input** —
skipping one ships a mismatched build rather than failing loudly.

```powershell
# 0. Recover the signing password (DPAPI-encrypted, bound to this machine+account)
cd desktop
$sec   = (Get-Content .\certs\pfx-password.dpapi | Select-Object -First 1) | ConvertTo-SecureString
$bstr  = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

python ..\backend\scripts\set_version.py 0.5.7      # 1. bump desktop/package.json
cd ..\backend ; pyinstaller pyinstaller/app.spec    # 2. Python bundle
cd ..\desktop ; .\scripts\sign-backend.ps1 -Password $plain   # 3. sign the backend exe
$env:CSC_KEY_PASSWORD = $plain ; npm run dist       # 4. wrap (2) -> signed installer + zip
cd ..\backend ; python scripts\build_release.py `
    --github-release OppositeMusical/UFC-Website --notes "What changed"   # 5. publish
```

**Step 3 must run before step 4.** electron-builder signs the Electron app, the
uninstaller and the installer, but only *copies* `UFCPredictor.exe` in as a
resource — signing it afterwards leaves the copy inside the installer unsigned.

**Step 4 fails late without `CSC_KEY_PASSWORD`**: several minutes in, with
`SignTool Error: The specified PFX password is not correct`, which reads like a
bad certificate rather than an unset variable.

Step 5 renames the artifacts to their published names, copies them plus
`latest.yml` and the matching `.blockmap` into `frontend/public/downloads/`, and
regenerates `version.json` (URL, size, SHA-256, release notes).

Then create the GitHub release with all four files — **as a draft first, upload,
then un-draft**. An empty release sitting at `releases/latest` makes every
installed copy's update check 404 for the length of the upload.

`desktop/package.json`'s `version` is the single source of truth throughout; the
Python side never declares one, so the two can't drift.

## Deploying the site to Railway

Config lives in [`frontend/railway.json`](frontend/railway.json); the site is
served by [`frontend/server.js`](frontend/server.js), a dependency-free static
server.

1. New Railway project → **Deploy from GitHub repo**.
2. In the service's **Settings → Root Directory**, set `frontend`. Railway then
   finds `package.json` and `railway.json`, and Nixpacks detects Node.
3. Deploy. It runs `npm ci && npm run build`, then `npm start`.

Railway injects `PORT`; the server binds it on `0.0.0.0` and answers
`/healthz` for the healthcheck.

### Point the download at GitHub first

**`frontend/public/downloads/` is gitignored**, so the ~180MB installer is not
in the repo and will not exist on Railway. If `version.json` still points at
`/downloads/...`, there is nothing behind it.

Publish the installer as a GitHub release, then regenerate the manifest to
point there and commit it:

```powershell
# after `npm run dist` in desktop/
cd backend
python scripts\build_release.py --github-release OppositeMusical/UFC-Website
# then upload these four from frontend/public/downloads/ to the GitHub release:
#   MMA-Assist-<version>-setup-x64.exe            <- primary, self-updating
#   MMA-Assist-<version>-setup-x64.exe.blockmap   <- differential updates
#   MMA-Assist-<version>-portable-win64.zip
#   latest.yml                                    <- what installed copies poll
git add ..\frontend\public\version.json && git commit -m "Publish v<version>"
```

**Asset names must match `latest.yml` exactly.** `build_release.py` refuses to
publish if they disagree — a mismatch there means every update check 404s
silently, and the app just keeps reporting it's up to date.

The page fails safe either way: it HEAD-checks a relative `downloadUrl` before
rendering a live button, so a missing artifact shows "Build not available yet"
rather than a button that 404s.

That same `version.json` is what installed copies poll for updates, so
committing it is also what announces the release to existing users.

### Why a hand-written server

Three cache policies and an SPA fallback, all of which matter:

- **`/version.json` is `no-store`.** It's the release pointer *and* the update
  manifest; a cached copy strands users on a stale version. This already caused
  a real bug.
- **`/assets/*` is `immutable`** — Vite fingerprints those filenames.
- **`index.html` is `no-cache`**, or visitors stay pinned to an old asset graph
  after a deploy.
- **Unknown extensionless paths serve `index.html`** so `/about` and `/download`
  survive a refresh — but anything *with* an extension 404s, since handing a
  broken `.js` a 200 masks the failure.

## Data source note

The fighter-stats scraper targets `ufc.com` — the UFC's own official site — and
honours its stated `crawl-delay: 15`. UFCStats.com and ESPN were both evaluated
and deliberately ruled out; see §2.1 of the spec for why.

## Updating

The installer is the self-updating channel. **Settings → Check for Updates**
downloads the new installer, verifies its Authenticode signature against the
expected publisher, stops the Python backend, installs silently and relaunches —
your database, chats and saved predictions are in the user profile, not the
install directory, so they survive both updates and uninstalls.

Nothing happens without two explicit clicks: one to download, one to install.
The portable zip cannot self-update (electron-updater only supports NSIS on
Windows) and falls back to a link to the download page.

Two independent feeds, deliberately not mixed:

| Build | Reads | Used for |
|---|---|---|
| Installed (NSIS) | `latest.yml` on the GitHub release | download + install in place |
| Portable / browser | `version.json` on `main` | "a newer version exists" notice |

## Known gaps

- The build is signed with a **self-signed** certificate, which suppresses the
  "Unknown Publisher" prompt only on machines that trust it. Public downloads
  still trip SmartScreen; the Download page explains this and publishes a
  SHA-256 to verify against. **It also gates updates**: on a machine that never
  imported the certificate, the updater will correctly refuse to install.
  That refusal path has never been observed on real hardware — see §14 of the
  spec for the full verified/unverified list.
- **Windows only.** The Download page lists macOS as coming soon; `macos/`
  holds the build tooling, not a second app.
- **Differential updates are unconfirmed.** Blockmaps are published and
  `differentialPackage` is on, but every observed update has transferred the
  full installer.
- **3,262 of 6,746 fighters have no stats** — historical or never-competed
  profiles ufc.com lists without them. They are still selectable in
  autocomplete, so a prediction can be requested about someone the AI has no
  data for. Settings now says how many are missing.
