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
┌─────────────────────────┐        ┌──────────────────────────────────────────────┐
│  frontend/ (React+Vite)  │        │  backend/ (downloaded, runs on user machine)  │
│  Static marketing site   │        │                                                │
│  - Home                  │  link  │  run.py → waitress WSGI server (127.0.0.1)    │
│  - Download              │───────▶│    → Flask app (blueprints below)             │
│  (no API calls to        │        │    → opens default browser automatically       │
│   backend; fully static) │        │                                                │
└─────────────────────────┘        │  Local data (SQLite + ChromaDB) under          │
                                    │  %LOCALAPPDATA%\UFCPredictor\                 │
                                    │                                                │
                                    │  ┌─────────────┐  ┌────────────────────────┐  │
                                    │  │ AI Provider  │  │ RAG (ChromaDB)         │  │
                                    │  │ abstraction  │◀─┤ fighter stat documents │  │
                                    │  │ Ollama/OpenAI│  └────────────────────────┘  │
                                    │  │ Gemini/      │        ▲                     │
                                    │  │ Deepseek/    │        │ ingested by         │
                                    │  │ Claude       │  ┌─────┴──────────────────┐  │
                                    │  └─────────────┘  │ Scraper (ufc.com)      │  │
                                    │                     │ sitemap → athlete pages│  │
                                    │                     └────────────────────────┘  │
                                    └──────────────────────────────────────────────┘
```

The marketing site and the desktop app **share no code and no runtime API**. The desktop app is entirely self-contained and serves its own UI (Jinja2 templates + vanilla JS) — there is no build step or SPA framework inside `backend/`.

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

## 3. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Desktop app backend | Flask + waitress | Flask for routing/templating; waitress (not Flask's dev server) as a real WSGI server for the shipped app |
| Desktop app UI | Jinja2 templates + vanilla JS/CSS | No build step; simplest to package with PyInstaller |
| Desktop app DB | SQLite via SQLAlchemy 2.0 ORM | Zero-config, file-based, fits single-user desktop app; no Alembic — a `schema_version` row plus small hand-written additive upgrades instead |
| Vector store | ChromaDB `PersistentClient`, bundled default ONNX MiniLM embedding function | Fully local embeddings, no API key or GPU needed; avoids the multi-GB torch/sentence-transformers dependency that default embeddings via `sentence-transformers` would pull in |
| Secrets (API keys) | `keyring` (Windows Credential Manager backend, explicitly selected) with a Fernet-encrypted-file fallback | OS-native secret storage; explicit backend selection avoids `keyring`'s auto-detection being unreliable once frozen by PyInstaller |
| Packaging | PyInstaller, **onedir** mode | Onefile re-extracts 150–300MB to a temp directory on every launch (slow, triggers more antivirus false positives); onedir starts fast and is what gets zipped for distribution |
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
| GET | `/` | Dashboard: nav, last fighter-DB sync time, recent predictions/conversations |
| GET | `/betting/<platform>` | Renders the shared prediction form for `prizepicks`/`draftkings`/`kalshi`; 404 on unknown platform |
| POST | `/betting/<platform>/predict` | Body: `{fighter_a_id, fighter_b_id, stat_category, line_value}` → runs RAG+LLM, saves `Prediction` + seeds a `Conversation`, returns `{conversation_id, prediction: {direction, confidence_pct, reasoning}}` |
| GET | `/chat` | List conversations |
| POST | `/chat/new` | Create an empty conversation |
| GET | `/chat/<id>` | Conversation detail + messages |
| POST | `/chat/<id>/message` | Body: `{content}` → fuzzy-matches fighter names in the message, injects Chroma context if found, calls active provider, appends both messages, returns the assistant reply |
| GET | `/settings` | Current provider config (masked keys), Ollama status |
| POST | `/settings/provider` | Body: `{provider, api_key?}` → sets active provider, stores key via `secret_manager` |
| GET | `/settings/ollama/models` | Proxies `GET http://localhost:11434/api/tags` |
| POST | `/settings/test-connection` | Sends a minimal request to the configured provider, returns ok/error |
| POST | `/settings/sync-fighters` | Kicks off the scraper pipeline in a background thread, returns a job id |
| GET | `/settings/sync-fighters/status` | Poll: `{running, fighters_done, fighters_total, last_error}` |
| GET | `/api/fighters/autocomplete?q=` | Returns `[{id, name, weight_class}]` for the form autocomplete inputs |

## 6. Page-by-Page UI Spec

All pages share `base.html` (left nav: Dashboard, PrizePicks, DraftKings, Kalshi, Chat, Settings) and the dark MMA theme (`static/css/theme.css`: near-black background, crimson/red accent, white/light-gray text).

- **Dashboard (`/`)**: welcome panel, "AI provider: <current>" status chip, "Fighter database last synced: <time>" (or "Not synced yet — go to Settings"), list of recent predictions with a "Continue in Chat" link.
- **PrizePicks / DraftKings / Kalshi (`/betting/<platform>`)**: one shared form — Fighter A (autocomplete input), Fighter B (autocomplete input), Stat Category (dropdown, platform-specific subset), Line Value (number input, e.g. `2.5`), Submit → renders a result card: Over/Under call, confidence %, bullet-point reasoning, a small stat comparison table for both fighters, and a "Continue in Chat" button. Platform pages differ only in accent color/logo text and which stat categories are offered (`betting/platforms.py::PLATFORM_CONFIG`). Footer disclaimer per §1.
- **Chat (`/chat`)**: sidebar of past conversations (titled by platform/fighters if seeded from a prediction, else "New Chat"), main panel is a standard message thread with a text input; conversations seeded from a prediction start with that prediction as the first assistant message.
- **Settings (`/settings`)**: Provider selector (Ollama / OpenAI / Gemini / Deepseek / Claude). If Ollama: dropdown of locally installed models (from `/settings/ollama/models`) + "Test Connection." If cloud: masked API key input + Save + Test Connection. Separate "Fighter Database" panel: last synced time, "Sync Now" button, progress bar driven by polling `/settings/sync-fighters/status`.

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

- **Betting pages**: fighters are already resolved to a specific `fighter_id` via the autocomplete endpoint, so context lookup is deterministic — `collection.get(ids=[fighter_a.ufc_slug, fighter_b.ufc_slug])`. No ambiguity, no wrong-fighter risk.
- **Chatbot**: free-text input. Before each turn, fuzzy-match fighter names mentioned in the message against the SQLite `fighters.name` column (e.g. `difflib`/`rapidfuzz`), and inject any matched fighters' Chroma documents into the prompt as context. This deterministic pre-processing step is used instead of model-driven tool-calling because tool-calling support is inconsistent across local Ollama models, and full-local (Ollama) operation is a core feature — context injection must work the same way regardless of provider.

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

- API keys are never stored in plaintext files. `keyring` with the Windows Credential Manager backend explicitly selected is the primary store; a Fernet-encrypted file (key derived from a per-install random value with restricted ACLs) is the fallback if `keyring` raises. The fallback protects against casual disk inspection, not a determined local attacker with full OS access to the same user account — acceptable for a single-user local desktop tool.
- No telemetry, no external data collection beyond the user's own configured AI provider calls and the user-initiated `ufc.com` scrape.
- All app data (SQLite DB, Chroma persistent directory, Fernet fallback key file) lives under `%LOCALAPPDATA%\UFCPredictor\`, never inside the installed program directory (which may be read-only).

## 12. Folder Structure

See the repository root; mirrors the structure agreed in the implementation plan (`docs/` for this spec, `backend/app/{models,blueprints,services,templates,static,seed_data}`, `backend/tests`, `frontend/src/{pages,components}`).

## 13. Setup / Build / Run

**Dev run:**
```
cd backend
pip install -r requirements.txt
python run.py
```
Opens `http://127.0.0.1:<port>/` in the default browser automatically.

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
5. `cd desktop && npm run dist` → copies step 4's folder in as `resources/backend` and emits `desktop/release/UFC Predictor Setup <version>.exe` (NSIS installer, ~180MB).
6. `python backend/scripts/build_release.py` → copies step 5's installer into `frontend/public/downloads/` and regenerates `version.json` (URL, size, SHA-256) — this is what the landing page's Download button serves.

> **Rebuild step 4 whenever `backend/` changes.** electron-builder copies
> `backend/dist/UFCPredictor` in verbatim; it cannot tell the Python source
> moved on. A stale bundle fails confusingly rather than loudly — one built
> before `run.py` grew `--port` ignored the flag, bound its default 8765
> instead of the port Electron assigned, and the app died on a health-check
> timeout while a perfectly healthy server sat on the wrong port.

**Not done yet**: the installer is unsigned, so Windows SmartScreen shows
"Windows protected your PC" on first run. Code signing needs a purchased
certificate; the Download page tells users what to expect and publishes the
SHA-256 so they can verify the file themselves.

**Marketing site:**
```
cd frontend
npm install
npm run build
```

## 14. Explicitly Out of Scope for the Initial Build Session

- Running a real signed `.exe` end-to-end interactively the way a user's own machine would (the sandbox this was written in has since actually built and launched the real `.exe` and confirmed it serves — see the build log — but a user's own install is still the authoritative test).
- Making real calls to any paid cloud LLM provider (no live API keys are configured in the dev environment) — provider code is validated with mocked HTTP/SDK layers. Ollama, if the user has it installed, is exercised for real.
- A full multi-thousand-fighter live scrape was in fact run against ufc.com (see §10) to bake the bundled seed data — this is no longer out of scope, it's how the shipped database was produced.

## 15. Open Questions / v2 Ideas

- Embedded webview (pywebview) instead of opening the system browser, for a more "native app" feel.
- Auto-update mechanism for the packaged app.
- Optional model-driven tool-calling for chat on providers that support it well (OpenAI/Anthropic/Gemini), as a layered enhancement on top of the deterministic fuzzy-match context injection (not a replacement, since Ollama must keep working the same way).
- macOS/Linux packaging.
