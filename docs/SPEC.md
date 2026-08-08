# MMA AI Predictor — Product & Technical Spec

Status: v1 spec, written before implementation per project requirement.

## 1. Overview & Goals

Two decoupled deliverables:

1. **Marketing/landing website** (`frontend/`) — a public, static, MMA-themed site whose only job is to explain the product and let visitors download the desktop app. No backend, no accounts, no user data.
2. **UFC Predictor desktop app** (`backend/` + `desktop/`) — a Python program distributed to end users as a Windows application. It runs a local web server; an Electron shell (`desktop/`) spawns that server and renders its UI in a native window, so users get a real desktop app rather than a browser tab. Running `backend/run.py` directly still opens the browser instead, which is the development path. It supports both a fully local AI mode (Ollama) and cloud AI providers (OpenAI, Google Gemini, Deepseek, Anthropic Claude) via user-supplied API keys. It offers three prediction pages modeled on prop-betting/prediction-market formats (PrizePicks, DraftKings, Kalshi), a persistent multi-turn chatbot, and a Retrieval-Augmented-Generation (RAG) layer backed by a local ChromaDB vector store of real UFC fighter statistics.

**Non-goals for v1**: user accounts/auth, cloud sync, mobile apps, real-money betting integration, macOS/Linux packaging (Windows-only for v1; the app runs fine on macOS/Linux from source since Flask/Python are cross-platform, but only Windows gets a packaged build).

**Disclaimer (shown in-app and on the landing site)**: predictions are for informational/entertainment purposes only. This is not financial or gambling advice, and the app does not place bets or wagers. Users are responsible for complying with the laws and platform terms that apply to them.

## 2. Architecture

```
┌──────────────────────────┐        ┌────────────────────────────────────────────────┐
│ frontend/ (React + Vite) │        │ Installed on the user's machine                │
│ Static marketing site    │        │                                                │
│  - Home                  │        │  ┌──────────────────────────────────────────┐  │
│  - Download              │        │  │ desktop/  Electron shell                 │  │
│  - About (placeholder)   │        │  │   main.js    window, menu, lifecycle     │  │
│                          │        │  │   backend.js spawn + /health + teardown  │  │
│  Serves:                 │download│  └───────────────┬──────────────────────────┘  │
│   version.json ──────────┼───────▶│      spawns      │      loads http://127.0.0.1 │
│   the portable zip       │        │                  ▼                             │
│                          │        │  ┌──────────────────────────────────────────┐  │
│                          │        │  │ backend/  waitress → Flask               │  │
│  version.json is ALSO    │        │  │   Jinja UI + JSON API (§5)               │  │
│  the update manifest ◀───┼────────┼──┤   polled ≤6h for a newer release         │  │
│  installed copies poll   │        │  └──────────────────────────────────────────┘  │
└──────────────────────────┘        │                                                │
                                    │  Data in <app folder>\data\ (portable, §13.1) │
                                    │   SQLite + ChromaDB (seeded on first launch)   │
                                    │                                                │
                                    │  ┌─────────────┐  ┌────────────────────────┐   │
                                    │  │ AI Provider │  │ RAG (ChromaDB)         │   │
                                    │  │ abstraction │◀─┤ fighter stat documents │   │
                                    │  │ Ollama/     │  └────────────────────────┘   │
                                    │  │ OpenAI/     │        ▲                      │
                                    │  │ Gemini/     │        │ ingested by          │
                                    │  │ Deepseek/   │  ┌─────┴──────────────────┐   │
                                    │  │ Claude      │  │ Scraper (ufc.com)      │   │
                                    │  └─────────────┘  │ sitemap → athlete pages│   │
                                    │                   └────────────────────────┘   │
                                    └────────────────────────────────────────────────┘
```

The marketing site and the app **share no code and no runtime API**. The one thing they share is `version.json`: the Download page reads it to render the download button, and installed copies poll the same file to detect updates (§13). The app serves its own UI (Jinja2 templates + vanilla JS) — there is no build step or SPA framework inside `backend/`.

### 2.1 Data source pivot (important, read before touching the scraper)

The original candidate scrape targets were UFCStats.com and ESPN. Both were verified live and rejected:

- **UFCStats.com** now serves a JavaScript proof-of-work "checking your browser" challenge on every page (confirmed by direct HTTP fetch — the response is a challenge script, not fighter data). Writing code to solve this challenge would mean deliberately defeating an anti-bot control the site operator put in place; that is out of scope for this project regardless of technical feasibility.
- **ESPN**'s `robots.txt` explicitly disallows `anthropic-ai` (and several other AI crawlers) for the entire site. This project is built by an Anthropic model, so that source is excluded on principle, independent of technical feasibility.

**Replacement, verified live and approved by the user**: `www.ufc.com`, the UFC's own official site.
- `robots.txt` has no blanket disallow and states `crawl-delay: 15` — an explicit, honored crawling allowance.
- `sitemap.xml` (a sitemap index, `?page=1..N`) lists every `/athlete/<slug>` profile URL — confirmed live (~140 athlete URLs per sub-sitemap page across 20+ pages).
- Individual athlete pages (e.g. `ufc.com/athlete/jon-jones`) return full server-rendered HTML with no bot gate, containing exactly the stats needed. Verified live markup:
  - Bio fields: `<div class="c-bio__label">Height</div>` paired with a sibling `<div class="c-bio__text">76.00</div>` (same pattern for Status, Place of Birth, Trains at, Age, Weight, Octagon Debut, Reach, Leg reach).
  - Career stats: `<div class="c-stat-compare__number">4.38</div>` paired with `<div class="c-stat-compare__label">Sig. Str. Landed</div>` and an optional `<div class="c-stat-compare__label-suffix">Per Min</div>` (same pattern for Sig. Str. Absorbed, Takedown avg, Submission avg, Sig. Str. Defense, Takedown Defense, Knockdown Avg, Average fight time).

This is a better data source than either original option: it's the official record-keeper, richer in per-fighter detail, and fully compliant with the site's stated crawling policy.

### 2.2 How `desktop/` and `backend/` interact

`backend/` is the whole application; `desktop/` is a shell that owns a window and a child process. They are two separate programs communicating over **localhost HTTP** — Electron is simply acting as the browser.

Launch sequence (`desktop/main.js` → `desktop/backend.js`):

1. **Pick a free port** — bind `:0`, read the assigned port, release it. Not a fixed 8765, which collides with a second copy, an unrelated dev server, or a crash leftover; the symptom would be a window that never loads.
2. **Resolve the command** — packaged: `resources/backend/UFCPredictor.exe` (users have no Python). Dev: `backend/.venv/Scripts/python.exe run.py`. Same arguments either way, so the two paths can't diverge behaviourally.
3. **Spawn** with `--port N --no-browser [--app-version X]`.
4. **Race** a `/health` poll (90s cap) against the child's `exit`/`error` events, so a crash surfaces immediately rather than after the full timeout.
5. **Show the window** on `ready-to-show`, closing the splash.

What crosses the boundary is deliberately narrow:

| Direction | Payload |
|---|---|
| Electron → backend | `--port`, `--no-browser`, `--app-version`; `PYTHONUNBUFFERED=1` so stdout arrives line-by-line rather than in one block at exit |
| backend → Electron | stdout/stderr lines (startup log + the error dialog's contents), the `UFC_PREDICTOR_READY <url>` line, and HTTP responses |

There is **no IPC bridge**. `preload.js` exposes only `window.ufcPredictor.isDesktop`; the renderer is the Flask UI, which needs nothing from Node. Electron never touches SQLite, ChromaDB, or any AI provider.

**Teardown** matters as much as startup: `before-quit` → `taskkill /pid N /T /F`. The `/T` is load-bearing — the PyInstaller exe is a process tree (bootloader → real app), so `child.kill()` signals only the parent and orphans a server holding the SQLite file and a port. A single-instance lock prevents a second launch spawning a second backend against the same database.

**The one tight coupling is at build time**: electron-builder copies `backend/dist/UFCPredictor` in verbatim as `resources/backend` and cannot tell the Python source moved on (§13).

## 3. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Desktop app backend | Flask + waitress | Flask for routing/templating; waitress (not Flask's dev server) as a real WSGI server for the shipped app |
| Desktop app UI | Jinja2 templates + vanilla JS/CSS | No build step; simplest to package with PyInstaller |
| Desktop app DB | SQLite via SQLAlchemy 2.0 ORM | Zero-config, file-based, fits single-user desktop app; no Alembic — a `schema_version` row plus small hand-written additive upgrades instead |
| Vector store | ChromaDB `PersistentClient`, bundled default ONNX MiniLM embedding function | Fully local embeddings, no API key or GPU needed; avoids the multi-GB torch/sentence-transformers dependency that default embeddings via `sentence-transformers` would pull in |
| Secrets (API keys) | `keyring` (Credential Manager / Keychain, backend named explicitly per platform) with a Fernet-encrypted-file fallback | OS-native secret storage; naming the backend avoids `keyring`'s auto-detection, which is unreliable once frozen. See §11 for a verified limitation in packaged Windows builds |
| Desktop shell | Electron + electron-builder (portable zip) | Gives the local Flask app a real window without rewriting the UI. Ships portable rather than installed so the app and its data live in one user-chosen folder (§13.1). Kept on a supported Electron major — the version electron-builder pulls in by default carried 17 CVEs, and unlike build tooling the runtime ships to users |
| Backend bundling | PyInstaller, **onedir** mode | Onefile re-extracts 150–300MB to a temp directory on every launch (slow, triggers more antivirus false positives); onedir starts fast, and Electron copies the folder in as `resources/backend` |
| Marketing site | React + Vite | Componentized landing page, matches prior project scaffolding intent |
| Scraper | `requests` + `BeautifulSoup4` against `ufc.com`, sitemap-driven discovery | See §2.1 |

## 4. Data Models

### 4.1 SQLite (SQLAlchemy models, `backend/app/models/`)

```
fighters
  id                    INTEGER PK
  ufc_slug              TEXT UNIQUE NOT NULL      -- e.g. "jon-jones"
  name                  TEXT NOT NULL
  nickname              TEXT
  weight_class          TEXT
  stance                TEXT
  height_in             REAL
  reach_in              REAL
  leg_reach_in          REAL
  dob                   DATE
  wins, losses, draws, no_contests   INTEGER
  status                TEXT                       -- Active/Not Fighting/Retired
  place_of_birth        TEXT
  trains_at             TEXT
  octagon_debut         TEXT
  slpm                  REAL   -- sig. strikes landed per min
  sapm                  REAL   -- sig. strikes absorbed per min
  sig_str_defense_pct   REAL
  td_avg                REAL   -- takedown avg per 15 min
  td_defense_pct        REAL
  sub_avg               REAL   -- submission avg per 15 min
  knockdown_avg         REAL
  avg_fight_time        TEXT
  source_url            TEXT
  roster_synced_at      DATETIME
  stats_scraped_at      DATETIME  -- NULL until detail page has been scraped

app_settings
  id           INTEGER PK
  key          TEXT UNIQUE NOT NULL   -- active_provider | active_ollama_model | schema_version | last_fighter_sync_at
  value        TEXT
  updated_at   DATETIME

conversations
  id             INTEGER PK
  title          TEXT
  platform       TEXT NULL   -- prizepicks | draftkings | kalshi | NULL (pure chat)
  fighter_a_id   INTEGER NULL FK -> fighters.id
  fighter_b_id   INTEGER NULL FK -> fighters.id
  created_at, updated_at   DATETIME

messages
  id               INTEGER PK
  conversation_id  INTEGER FK -> conversations.id
  role             TEXT   -- user | assistant | system
  content          TEXT
  created_at       DATETIME

predictions
  id                    INTEGER PK
  conversation_id       INTEGER FK -> conversations.id
  platform              TEXT
  fighter_a_id          INTEGER FK -> fighters.id
  fighter_b_id          INTEGER FK -> fighters.id
  stat_category         TEXT
  line_value            REAL
  direction_predicted   TEXT   -- over | under
  confidence_pct        INTEGER
  reasoning             TEXT
  created_at            DATETIME

scrape_checkpoints
  id             INTEGER PK
  fighter_slug   TEXT UNIQUE
  status         TEXT   -- pending | done | error
  last_attempt_at DATETIME
```

### 4.2 ChromaDB

Collection `fighters`:
- `id` = `ufc_slug`
- `document` = natural-language summary, e.g. *"Jon Jones (Light Heavyweight) — record 27-1-0. Significant strikes landed: 4.38/min, absorbed: 2.24/min, defense 64%. Takedowns: 1.89 avg per 15 min, defense 95%. Submissions: 0.46 avg per 15 min. Knockdown avg: 0.25."*
- `metadata` = `{name, weight_class, stance, wins, losses, draws, slpm, sapm, td_avg, sub_avg, sig_str_defense_pct, td_defense_pct}` for filtering/debugging.

## 5. API Contracts (Flask routes)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard: measured status chips (§6), stat tiles, recent predictions |
| GET | `/health` | Liveness probe. Electron polls this to decide when to show the window |
| GET | `/api/status/provider` | Live check of the configured AI provider — Ollama reachable and has the selected model, or a key is stored for a hosted provider. Fetched by JS after paint so a hung Ollama can't stall the dashboard |
| GET | `/api/updates/check[?force=1]` | Compares the installed version against the published manifest. `{status: available\|current\|unknown\|dev\|disabled, currentVersion, latestVersion?, releaseNotes?, downloadPageUrl?}`. Cached 6h; `force=1` bypasses it |
| GET | `/betting/<platform>` | Renders the shared prediction form for `prizepicks`/`draftkings`/`kalshi`; 404 on unknown platform |
| POST | `/betting/<platform>/predict` | Body: `{fighter_a_id, fighter_b_id, stat_category, line_value}` → runs RAG+LLM, saves `Prediction` + seeds a `Conversation`, returns `{conversation_id, prediction: {direction, confidence_pct, reasoning}}` |
| POST | `/betting/<platform>/market-probability` | **Kalshi only** (400 elsewhere). Body: `{question}` (≤500 chars) → fuzzy-matches any fighters named, injects their stats, returns `{conversation_id, probability_pct, reasoning, matched_fighters}`. Writes a `Conversation` but **no `Prediction`** — see §5.1 |
| GET | `/chat/` | Full-screen chat. Empty state is a centred composer; no conversation is created until the first message |
| POST | `/chat/new` | Create an empty conversation |
| GET | `/chat/<id>` | Conversation detail + messages |
| POST | `/chat/<id>/message` | Body: `{content}` → fuzzy-matches fighter names in the message, injects Chroma context if found, calls active provider, appends both messages, returns the assistant reply |
| GET | `/settings/` | Provider config, fighter-DB panel, installed version |
| POST | `/settings/provider` | Body: `{provider, api_key?}` → sets active provider, stores key via `secret_manager` |
| GET | `/settings/ollama/models` | Proxies `GET http://localhost:11434/api/tags` |
| POST | `/settings/test-connection` | Sends a minimal request to the configured provider, returns ok/error |
| POST | `/settings/sync-fighters` | Kicks off the scraper pipeline in a background thread |
| GET | `/settings/sync-fighters/status` | Poll: `{running, done, total, last_error}` |
| GET | `/api/fighters/autocomplete?q=` | Returns `[{id, name, weight_class}]` for the form autocomplete inputs |

### 5.1 Why the Kalshi market endpoint writes no `Prediction`

`predictions` requires two fighter IDs, a stat category and a numeric line. A
free-text market ("will this fight end inside the distance?") need not have any
of them, and forcing a row in would mean inventing values. The endpoint writes a
`Conversation` plus its opening assistant message instead, so the estimate
persists and "Continue in Chat" works exactly as it does for a stat prop. The
tradeoff: market questions don't appear in the dashboard's Recent Predictions.

## 6. Page-by-Page UI Spec

All pages share `base.html` (left nav: Dashboard, PrizePicks, DraftKings, Kalshi, Chat, Settings) and the dark MMA theme (`static/css/theme.css`: near-black background, crimson accent). The nav collapses to a 64px icon rail via a toggle; the state persists in `localStorage` and is applied by an inline `<head>` script **before first paint**, or the sidebar visibly flashes open on every navigation.

- **Dashboard (`/`)**: stat tiles that count up (fighters with stats / fighters known / predictions made), two **measured** status chips (§6.1), a dismissible update banner when a newer release exists (§13), and recent predictions with a "Continue in Chat" link.
- **PrizePicks / DraftKings / Kalshi (`/betting/<platform>`)**: one shared form — Fighter A and Fighter B (autocomplete, arrow-key navigable), Stat Category (platform-specific subset), Line Value, Submit → shimmer skeletons while waiting, then a result card: an SVG confidence ring that draws while the number counts up in step, the OVER/UNDER call, reasoning, and "Continue in Chat". Platform pages differ only in accent colour and stat categories (`betting/platforms.py::PLATFORM_CONFIG`). **Kalshi additionally** has a free-text market-question card (§5.1): a textarea, a probability ring, and a Leans Yes / Leans No / Toss-up verdict — 45–55% reads as a toss-up, since anything finer is inside the noise of an LLM estimate. It states plainly whether the answer is stat-grounded, because a confident-looking ring on a question naming no known fighter would otherwise read as far more authoritative than it is.
- **Chat (`/chat/`)**: full-screen — no page padding, no reading-measure cap, and the transcript is the only thing that scrolls. Two states share **one** composer: an empty conversation centres it under "Where should we begin?" with suggestion rows; sending settles it to the bottom under the thread. Sharing the element means starting a conversation doesn't move focus or discard typed text. Replies reveal progressively (rAF against a token budget, so pacing holds regardless of length), auto-scroll only sticks while already near the bottom, and every assistant message has a hover Copy. The conversation rail has its own independent collapse toggle.
- **Settings (`/settings/`)**: Provider selector (Ollama / OpenAI / Gemini / Deepseek / Claude) — Ollama shows locally installed models, cloud providers a masked key input; both offer Test Connection. "Fighter Database" panel: Sync Now with a real progress bar (it reads "Discovering the roster…" during the phase where no total exists yet, rather than a misleading 0%). "App Version" panel: installed version, Check for Updates, and release notes.

### 6.1 Status chips report measured state, not configuration

Both dashboard chips derive from reality (`app/services/status.py`), which is a
deliberate correction of an earlier design where they were decorative:

- **Fighter database** — counts and freshness straight from the `fighters`
  table, keyed on `max(stats_scraped_at)`. It must **not** key on the
  `last_fighter_sync_at` setting: a seeded install has real per-fighter scrape
  timestamps but no sync setting, so that version told every new user their
  database was empty while they sat on a full roster, and pushed them toward a
  ~28h scrape they didn't need. Green when stats exist, amber past 30 days
  (matching the point a sync would actually re-fetch), red when nothing usable.
- **AI provider** — a live check: is the Ollama daemon answering and does it
  have the selected model pulled, or is a key actually in the keyring? Neither
  spends tokens; Test Connection is the deliberate, user-initiated version.
  Fetched asynchronously after paint so a hung Ollama can't stall the page.

Each chip carries a state dot (pulsing while checking) so meaning never rests on
colour alone.

### 6.2 Motion

One shared vocabulary of easing curves and durations lives in the theme's custom
properties, so unrelated components move like one product. Everything is
disabled under `prefers-reduced-motion` — including the marketing site's
scroll-reveals, which are forced visible so scroll-triggered content can never
be trapped at `opacity: 0`.

## 7. AI Provider Abstraction

`backend/app/services/ai/base.py` defines:
```python
class AIProvider(ABC):
    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str: ...
    def list_models(self) -> list[str]: ...
```
- `OllamaProvider` — `http://localhost:11434/api/chat` and `/api/tags`; no key required; raises a clear "Ollama not running" error if connection is refused.
- `OpenAICompatibleProvider` — shared base for `OpenAIProvider` (`base_url=https://api.openai.com/v1`) and `DeepseekProvider` (`base_url=https://api.deepseek.com`), since Deepseek's API is OpenAI-compatible.
- `GeminiProvider` — Google's Generative AI SDK.
- `AnthropicProvider` — the `anthropic` SDK.
- `factory.get_active_provider()` reads `app_settings.active_provider`, resolves the relevant key through `secret_manager`, and constructs the provider instance.

## 8. Chat Retrieval Design

- **Free text (chat, and the Kalshi market question)**: `app/services/fighter_mentions.py` matches names against the SQLite `fighters.name` column and injects the matched fighters' Chroma documents as context. This deterministic pre-processing is used instead of model-driven tool-calling because tool-calling support is inconsistent across local Ollama models, and full-local operation is a core feature — context injection must behave identically regardless of provider.

  Matching is **recall first, precision second**, and both halves were forced by real failures:
  - `rapidfuzz.partial_ratio` with `processor=str.lower` generates candidates. The original `WRatio` default scored a short name against a whole sentence poorly *and* was case-sensitive, so `"how good is jon jons at wrestling"` matched nobody at all.
  - A confirmation pass then requires **every part of a name** to appear (per-token fuzzy, so a typo still resolves). Without it, `"Will Jon Jones win by KO?"` also returned Antonio Jones and Carlton Jones — their stats went into the prompt as though they were participants, and the model duly explained that Jon's *"opponent Carlton Jones"* is a grappling specialist. Entirely fabricated, and it read as authoritative.

- **Betting pages**: fighters are already resolved to a specific `fighter_id` via autocomplete, so lookup is deterministic — no matching involved and no wrong-fighter risk.

## 9. Scraper Design & Ethics/Rate-Limit Policy

- Target: `www.ufc.com` only (see §2.1 for why, not ufcstats.com/espn.com).
- `ufc_client.py`: a single `requests.Session`, a descriptive `User-Agent`, and `time.sleep(15)` between every request to `ufc.com` — matching the site's own stated `crawl-delay: 15` in `robots.txt`. No concurrency. Retry with backoff on 5xx; abort-and-stop on repeated 403/429 rather than retrying aggressively.
- `sitemap.py`: fetches `https://www.ufc.com/sitemap.xml` (sitemap index), follows each `?page=N` sub-sitemap, extracts `/athlete/<slug>` URLs.
- `parser.py`: all CSS selectors centralized as named constants (`c-bio__label`/`c-bio__text`, `c-stat-compare__label`/`c-stat-compare__label-suffix`/`c-stat-compare__number`), verified against a real saved fixture page. A markup change on the live site will show up as a parser test failing against the saved fixture, not as silent bad data being ingested.
- `pipeline.py`: `sync_roster()` upserts slug/name stubs from the sitemap; `scrape_details(limit, resume)` processes fighters one at a time, committing to SQLite and upserting to ChromaDB after each fighter — an interrupted run resumes via `WHERE stats_scraped_at IS NULL` and loses at most one fighter's progress.
- A full roster sync (thousands of fighters × 15s delay) can take many hours by design — this is intentional and matches the site's stated crawl-delay. It runs as a background job the user starts from Settings (or via `scripts/scrape.py`), never automatically and never inside test/CI runs.

## 10. Bundled Seed Database (Pre-Filled Fighter Data)

A fresh install should not start with an empty database — a first-time user
would otherwise have to run (or wait out) a many-hours-long full scrape
before predictions have any real stats to work with. Instead, the packaged
app ships with a pre-scraped snapshot bundled directly into the executable:

- **`backend/app/seed_data/`** holds `ufc_predictor.seed.db` (a full SQLite
  snapshot) and `chroma_db/` (the matching ChromaDB persistent directory),
  baked by `scripts/build_seed_data.py` from a completed
  `scripts/scrape.py` run and bundled via PyInstaller's `datas` (see
  `pyinstaller/app.spec`).
- **`app/utils/seed.py::maybe_seed_data_dir()`** runs once at app startup,
  *before* `init_engine()`/`init_db()` ever touch the sqlite file (ordering
  matters — see the module docstring). If the user's real data directory
  (`%LOCALAPPDATA%\UFCPredictor\`) has no database yet, it copies the
  bundled seed in; if a database already exists (any prior run, including
  one the user has since synced further), it is **never** overwritten.
  Skipped entirely under `TestConfig` so unit tests stay fast/isolated.
- Because the seed file is a real, fully-initialized app database, the
  `last_fighter_sync_at` setting baked into it carries forward automatically
  once copied — the Dashboard/Settings pages correctly show *when the
  bundled snapshot was captured*, not a fake "just synced" timestamp. This
  is what tells a user it's time for an occasional refresh.
- Users can still pull current data anytime via Settings → Sync Now (or
  `scripts/scrape.py`) — bundling a seed only removes the *first-run* wait,
  it doesn't replace the normal sync mechanism or make the data "final."
- **Staleness-based refresh.** Shipping a seed means every fighter arrives
  with `stats_scraped_at` already set, so a resume-mode sync cannot use
  "never scraped" as its work filter — that would make Sync Now a no-op for
  the entire bundled roster and freeze stats at bake time forever. Instead
  `pipeline.scrape_details()` re-fetches a fighter when it has never been
  scraped *or* its stats are older than `max_age_days`
  (`DEFAULT_MAX_AGE_DAYS = 30`), oldest-first so an interrupted or
  `--limit`ed run spends its requests on the most out-of-date fighters.
  `--max-age-days 0` restores never-refresh behaviour (new fighters only);
  `--no-resume` forces a full re-scrape of everyone.
- Neither the baked `.db` nor `chroma_db/` is tracked in git — they are
  ~28MB of generated output, regenerated by the commands below. Only
  `app/seed_data/README.md` is committed, because `app.spec`'s `datas`
  entry requires the directory to exist at build time.

**Re-baking the seed data for a new release:**
```
python scripts/scrape.py                              # full run, into UFC_PREDICTOR_DATA_DIR
python scripts/build_seed_data.py --source-data-dir <that dir>
pyinstaller pyinstaller/app.spec                       # re-bundle with the fresh seed
```

Bake close to release: the seed's age is exactly how much catch-up work a
new user's first sync has to do.

**Snapshot currently bundled:** full ufc.com roster scraped 2026-08-01 →
2026-08-03 — 6,746 fighters (6,741 successfully scraped, 5 errors left
checkpointed for retry), of which 3,484 carry full striking/grappling
stats; the remainder are historical or never-competed profiles that
ufc.com lists without stats. 2.4MB SQLite + 24.7MB ChromaDB (6,741
vectors).

## 11. Security Notes

- API keys are never stored in plaintext files. `keyring` (Credential Manager on Windows, Keychain on macOS) is the *intended* primary store, with a Fernet-encrypted file — key derived from a per-install random value with restricted ACLs — as the fallback if `keyring` raises. The fallback protects against casual disk inspection, not a determined local attacker with full OS access to the same user account; acceptable for a single-user local desktop tool.

  **Known limitation, verified in the packaged Windows build (v0.4.0):** the
  frozen app does *not* reach the Credential Manager and always uses the
  encrypted-file fallback. `keyring` selects `WinVaultKeyring` successfully,
  but the write fails inside `win32ctypes`, whose cffi backend cannot build
  its FFI under PyInstaller. `cffi` is bundled because chromadb depends on
  it, so `win32ctypes` picks cffi over its freeze-friendly ctypes backend and
  there is no supported way to override that choice. Every Windows release to
  date has behaved this way — keys are encrypted at rest either way, so the
  practical impact is losing OS-level protection, not exposing plaintext.
  `keyring_store` now logs the reason rather than swallowing it, which is how
  this was finally found: running from the virtualenv works, so the bug is
  only visible by probing the frozen exe.
- No telemetry, no external data collection beyond the user's own configured AI provider calls and the user-initiated `ufc.com` scrape.
- All app data (SQLite DB, Chroma persistent directory, Fernet fallback key file) lives under `%LOCALAPPDATA%\UFCPredictor\`, never inside the installed program directory (which may be read-only).

## 12. Folder Structure

```
backend/        Flask app + scraper + RAG. The application itself.
  app/
    blueprints/   main, betting, chat, fighters, settings
    models/       SQLAlchemy: Fighter, Conversation, Message, Prediction,
                  AppSetting, ScrapeCheckpoint
    services/     ai/ (providers, prompts), rag/ (chroma, ingest, retrieve),
                  scraper/ (sitemap, client, parser, pipeline), secrets/,
                  db/, status.py, updates.py, fighter_mentions.py
    templates/    Jinja: base, index, chat, settings, betting/form
    static/       css/ (theme, chat, betting), js/ (common, chat, betting,
                  settings, status)
    seed_data/    Bundled pre-scraped DB (gitignored except its README; §10)
    version.py    Semver comparison + whatever Electron passed as --app-version.
                  No release number of its own (only a "0.0.0-dev" sentinel).
  pyinstaller/  app.spec
  scripts/      scrape.py, build_seed_data.py, build_release.py, set_version.py
  tests/        84 tests, no network

desktop/        Electron shell. The shipped product (§2.2).
  main.js, backend.js, preload.js, splash.html, package.json (version source)

frontend/       React + Vite marketing site.
  src/{pages,components,hooks,styles}
  public/       version.json (download + update manifest), downloads/ (gitignored)
  tests/        13 tests

docs/SPEC.md    This file.
```

## 13. Setup / Build / Run

**Dev run — the desktop app** (what users get):
```
cd backend  && pip install -r requirements.txt
cd ../desktop && npm install && npm start
```
Electron picks a free port, spawns the backend on it, and opens a window once
`/health` answers. If this fails with `requestSingleInstanceLock` undefined, the
shell has `ELECTRON_RUN_AS_NODE=1` set (VS Code's terminal does) — see
`desktop/README.md`.

**Dev run — backend alone**, serving the same UI in a browser:
```
cd backend
python run.py
```
A development convenience only; the shipped product is the Electron build.

**Sync the fighter database (only needed for a from-source dev run without a baked seed — a packaged install already ships with one, see §10):**
```
python scripts/scrape.py --limit 50   # small batch to start
python scripts/scrape.py              # full roster sync (long-running, resumable)
```

**Run tests:**
```
pytest backend/tests
```

**Package (Windows):**

The shipped artifact is an **Electron desktop app** (`desktop/`) that wraps
the Flask server: Electron spawns the packaged backend as a child process,
waits for `/health`, and points a `BrowserWindow` at it. The UI is unchanged —
still the same Jinja templates the standalone server renders. See
`desktop/README.md` for the design notes.

Each step's output is the next step's input, and **nothing detects a stale
input** — skipping a step ships a mismatched build rather than failing:

1. Ensure `requirements.txt` is installed in the build environment.
2. **Mandatory pre-bundle step**: run the app once with network access so ChromaDB's default embedding function downloads its ONNX model cache; then include that cache directory in the PyInstaller `datas` so a packaged, possibly-offline install doesn't silently fail to embed on first use.
3. **Bake the seed database** per §10 (`build_seed_data.py`) so `app/seed_data/` has real content before the next step — PyInstaller's `datas` entry for it must point at an existing directory.
4. `pyinstaller backend/pyinstaller/app.spec` → `backend/dist/UFCPredictor/` (onedir, contains `UFCPredictor.exe`).
5. `cd desktop && npm run dist` → copies step 4's folder in as `resources/backend` and emits `desktop/release/UFC Predictor-<version>-win.zip` (portable, ~230MB; ~630MB extracted).
6. `python backend/scripts/build_release.py` → copies step 5's zip into `frontend/public/downloads/` and regenerates `version.json` (URL, size, SHA-256) — this is what the landing page's Download button serves.

> **Rebuild step 4 whenever `backend/` changes.** electron-builder copies
> `backend/dist/UFCPredictor` in verbatim; it cannot tell the Python source
> moved on. A stale bundle fails confusingly rather than loudly — one built
> before `run.py` grew `--port` ignored the flag, bound its default 8765
> instead of the port Electron assigned, and the app died on a health-check
> timeout while a perfectly healthy server sat on the wrong port.

### 13.1 Portable, not installed

The app ships as a zip the user extracts wherever they like — nothing in
Program Files, nothing in AppData. `desktop/backend.js::resolveDataDir()`
resolves the data location per launch: an existing `UFC_PREDICTOR_DATA_DIR`
wins (tests/dev), else `<folder containing the exe>/data` when packaged,
else `%LOCALAPPDATA%` when that folder isn't writable. Because it is derived
from `process.execPath` every time and never persisted, moving the folder to
another drive or a USB stick keeps working. Electron passes the result down
as an env var, so the Python side stays generic.

The Download page uses `showDirectoryPicker()` where available (Chromium
only, secure context only) to stream the zip straight into a chosen folder;
Firefox and Safari fall back to an ordinary download link, and any failure —
CORS on a cross-origin release asset being the likely one — falls back too.

Electron's single-instance lock is app-wide rather than per-data-directory,
so two portable copies cannot run simultaneously even though their databases
are separate.

**Not done yet**: builds are signed with a *self-signed* certificate, which
only suppresses "Unknown Publisher" on machines that trust it. SmartScreen
reputation is keyed to a publicly-trusted certificate with download history,
so public downloads still show "Windows protected your PC". The Download page
says so and publishes the SHA-256 to verify against.

**Versioning and in-app update checks.** `desktop/package.json`'s `version`
is the single source of truth — electron-builder stamps the installer from
it, `desktop/main.js` passes it to the backend as `--app-version`, and
`build_release.py` reads it back off the installer filename. The Python
side deliberately declares no version constant (`app/version.py` holds only
comparison logic and the value Electron supplied), so the two cannot drift.
`scripts/set_version.py` bumps it.

Installed copies poll `Config.UPDATE_MANIFEST_URL` — the same `version.json`
the Download page reads — at most every 6 hours, cached in-process, and
surface a dismissible dashboard banner plus a Settings panel when a newer
release exists. Publishing the manifest is the only step that announces a
release; there is no separate update feed to maintain.

The app **never self-updates**: it links to the download page and the user
runs the installer. Silently replacing an executable is a larger trust ask
than this app needs to make, and the download page is where the SmartScreen
warning and checksum live. Comparison is numeric, not lexical (`0.10.0` >
`0.9.0`), a prerelease sorts below its own release, and an unparseable or
older published version never prompts — a bad manifest must not be able to
push users into a "downgrade update".

**Marketing site:**
```
cd frontend
npm install
npm run build     # -> frontend/dist
npm start         # serve dist/ the way production does (server.js)
```

**Hosting (Railway).** `frontend/railway.json` sets Nixpacks to
`npm ci && npm run build` then `npm start`, with `/healthz` as the healthcheck;
set the service's Root Directory to `frontend`. `frontend/server.js` is a
dependency-free static server rather than `serve`/express because the only
things needed beyond sending a file are an SPA fallback and three cache
policies — `no-store` on `version.json` (it is both the release pointer and the
update manifest), `immutable` on Vite's fingerprinted `/assets/*`, and
`no-cache` on `index.html` so a deploy isn't pinned to an old asset graph.
Extensionless paths fall back to `index.html` so client routes survive a
refresh; anything with an extension 404s, because handing a broken `.js` a 200
masks the failure.

**`frontend/public/downloads/` is gitignored**, so a host that builds from the
repo has `version.json` but no installer behind it. Publish the installer to a
release host and repoint the manifest
(`build_release.py --github-release OWNER/REPO`) before deploying. The Download
page fails safe regardless: it HEAD-checks a relative `downloadUrl` and shows
"Build not available yet" instead of a button that 404s.

## 14. Explicitly Out of Scope for the Initial Build Session

- Running a real **signed** installer end-to-end. The unsigned NSIS installer and the packaged Electron app have both been built and launched, and confirmed to spawn the bundled backend, seed a fresh data directory, serve every page and shut down without orphaning the Python process — but signing (and therefore a SmartScreen-free first run) is untested.
- Installing on a machine that has never had Python, Node, or this repo on it. Everything is bundled and the packaged path was exercised against an empty data directory, but a genuinely clean machine remains the authoritative test.
- Making real calls to any paid cloud LLM provider (no live API keys are configured in the dev environment) — provider code is validated with mocked HTTP/SDK layers. Ollama, if the user has it installed, is exercised for real.
- A full multi-thousand-fighter live scrape was in fact run against ufc.com (see §10) to bake the bundled seed data — this is no longer out of scope, it's how the shipped database was produced.

## 15. Open Questions / v2 Ideas

**Done since first draft** — kept here so the history is legible:
- ~~Embedded webview instead of the system browser~~ → done, as an Electron shell rather than pywebview (§2.2).
- ~~Auto-update mechanism~~ → deliberately **not** auto-update. Installed copies check the published manifest and link the user to the download page (§13); silently replacing an executable is a bigger trust ask than this app needs to make.

**Still open:**
- **Code signing.** The single highest-value remaining item: unsigned installers trip SmartScreen, and most users will read that as malware. Needs a purchased certificate.
- **An app icon.** Currently Electron's default, in the window, taskbar and installer.
- **macOS/Linux packaging.** The Download page already lists macOS as coming soon. `desktop/backend.js` resolves a POSIX venv path, but PyInstaller must be run on each target OS and none of it is tested there.
- **Stat-less fighters in autocomplete.** 3,262 of 6,746 roster entries are historical or never-competed profiles ufc.com lists without stats. They're currently selectable, so a user can pick someone the AI has nothing to reason about. Keep them in the database, exclude them from autocomplete.
- **Retry the 5 checkpointed scrape errors** from the full run (§10); they're marked `error`, so a resync picks up only those.
- Optional model-driven tool-calling for chat on providers that support it well (OpenAI/Anthropic/Gemini), layered on top of the deterministic fuzzy-match injection rather than replacing it — Ollama must keep working the same way.
- Dictation in the chat composer via the Web Speech API.
