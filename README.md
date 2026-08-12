# MMA Assist — Website

The public marketing/download site for **MMA Assist** (React + Vite, served by
a small hand-written static server). The application itself — Flask backend,
Electron desktop shell, build tooling — lives in the private
[UFC-Website-Backend](https://github.com/OppositeMusical/UFC-Website-Backend)
repo.

**Releases stay here.** Installed copies of the app poll this repo's public
GitHub release assets (`latest.yml` + installer) for updates, and the portable
build reads [`frontend/public/version.json`](frontend/public/version.json) on
`main`. Publishing a release means uploading the four artifacts to a release
**on this repo** and committing the regenerated `version.json` here — both are
produced by the app repo's `build_release.py`.

## Quick start

```powershell
cd frontend
npm install
npm run dev      # dev server
npm run build    # production build -> frontend/dist
npm test         # vitest (42 tests)
```

## Deploying to Railway

Config lives in [`frontend/railway.json`](frontend/railway.json); the site is
served by [`frontend/server.js`](frontend/server.js), a dependency-free static
server.

1. New Railway project → **Deploy from GitHub repo**.
2. In the service's **Settings → Root Directory**, set `frontend`. Railway then
   finds `package.json` and `railway.json`, and Railpack detects Node.
3. Deploy. It runs `npm ci && npm run build`, then `npm start`.

Railway injects `PORT`; the server binds it on `0.0.0.0` and answers
`/healthz` for the healthcheck.

## Publishing a release (from the app repo)

**`frontend/public/downloads/` is gitignored**, so the ~180MB installer is not
in the repo and will not exist on Railway. `version.json` must point at a
GitHub release on this repo:

1. Build and sign in **UFC-Website-Backend** (see its README, "Cutting a
   release"); its `build_release.py --github-release OppositeMusical/UFC-Website`
   step regenerates `version.json` with the release URL, size, SHA-256 and
   notes.
2. Create the GitHub release **on this repo** with all four artifacts — **as a
   draft first, upload, then un-draft**. An empty release sitting at
   `releases/latest` makes every installed copy's update check 404 for the
   length of the upload:
   - `MMA-Assist-<version>-setup-x64.exe` — primary, self-updating
   - `MMA-Assist-<version>-setup-x64.exe.blockmap` — differential updates
   - `MMA-Assist-<version>-portable-win64.zip`
   - `latest.yml` — what installed copies poll
3. Copy the regenerated `version.json` into this repo and commit it
   (`Publish v<version>`). That commit is what announces the release to
   portable/browser users.

**Asset names must match `latest.yml` exactly** — a mismatch means every
update check 404s silently, and the app just keeps reporting it's up to date.

The page fails safe either way: it HEAD-checks a relative `downloadUrl` before
rendering a live button, so a missing artifact shows "Build not available yet"
rather than a button that 404s.

## Why a hand-written server

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

## Update feeds

Two independent feeds, deliberately not mixed:

| Build | Reads | Used for |
|---|---|---|
| Installed (NSIS) | `latest.yml` on this repo's GitHub release | download + install in place |
| Portable / browser | `version.json` on `main` | "a newer version exists" notice |
