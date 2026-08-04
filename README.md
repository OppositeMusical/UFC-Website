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

84 backend tests, 13 frontend tests. No network calls — the scraper, AI
providers, and update checks are all exercised against mocked HTTP.

## Cutting a release

Each step's output feeds the next, and **nothing detects a stale input** —
skipping one ships a mismatched build rather than failing loudly.

```powershell
python backend\scripts\set_version.py 0.2.0        # 1. bump desktop/package.json
cd backend    ; pyinstaller pyinstaller/app.spec   # 2. Python bundle
cd ..\desktop ; npm run dist                       # 3. wrap (2) -> NSIS installer
cd ..\backend ; python scripts\build_release.py --notes "What changed"   # 4. publish (3)
```

Step 4 copies the installer into `frontend/public/downloads/` and regenerates
`version.json` (URL, size, SHA-256, release notes). That manifest is what the
Download page serves **and** what installed copies poll for updates — publishing
it is the only step that announces a release.

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
# 1. upload desktop/release/*.exe to a GitHub release, named
#    UFC-Predictor-Setup-<version>.exe
# 2. repoint the manifest
cd backend
python scripts\build_release.py --github-release OppositeMusical/UFC-Website
git add ..\frontend\public\version.json && git commit -m "release 0.1.0"
```

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

## Known gaps

- The installer is **unsigned**, so Windows SmartScreen warns on first run. The
  Download page explains this and publishes a SHA-256 to verify against.
- **Windows only.** The Download page lists macOS as coming soon.
- The app uses Electron's default icon.
- Update checks resolve against `raw.githubusercontent.com/OppositeMusical/UFC-Website`,
  so they only start working once `frontend/public/version.json` is pushed to `main`.
