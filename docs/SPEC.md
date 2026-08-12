# MMA AI Predictor — Product & Technical Spec

Status: living document. Written before implementation per project
requirement, and kept current with the shipped code since — **last reconciled
against the tree at v0.6.0**. Where a decision was later reversed, the
original reasoning is kept alongside the reversal rather than deleted (see
§15), because knowing why something *used* to be true is usually what stops
it being re-litigated.

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
│  - About the developer   │        │  │   main.js    window, menu, lifecycle     │  │
│                          │        │  │   backend.js spawn + /health + teardown  │  │
│  Serves:                 │download│  └───────────────┬──────────────────────────┘  │
│   version.json ──────────┼───────▶│      spawns      │      loads http://127.0.0.1 │
│   installer + zip        │        │                  ▼                             │
│                          │        │  ┌──────────────────────────────────────────┐  │
│                          │        │  │ backend/  waitress → Flask               │  │
│  version.json is ALSO    │        │  │   Jinja UI + JSON API (§5)               │  │
│  the update manifest ◀───┼────────┼──┤   update check (§13.2)                   │  │
│  installed copies poll   │        │  └──────────────────────────────────────────┘  │
└──────────────────────────┘        │                                                │
                                    │  Data: user profile, or data\ beside exe       │
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
  key          TEXT UNIQUE NOT NULL   -- active_provider | active_ollama_model | schema_version
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

market_predictions                       -- priced fight markets (§5.2)
  id                       INTEGER PK
  conversation_id          INTEGER FK -> conversations.id
  platform                 TEXT
  fighter_a_id             INTEGER FK -> fighters.id   -- the fighter the bet names
  fighter_b_id             INTEGER FK -> fighters.id
  market_type              TEXT   -- method | method_in_round | round_reached
  victory_method           TEXT   -- null for round_reached
  round_number             INTEGER -- null for a plain method bet
  question                 TEXT   -- the exact wording put to the model
  moneyline                INTEGER -- American odds, as entered
  model_probability_pct    INTEGER
  implied_probability_pct  REAL   -- from the price, margin included
  edge_pct                 REAL   -- percentage points, model minus implied
  verdict                  TEXT   -- value | fair | overpriced | implausible
  reasoning                TEXT
  created_at               DATETIME

  -- Separate from `predictions` rather than nullable columns bolted onto it.
  -- A stat prop has a line and an over/under call; a market has a price and a
  -- probability. `predictions.stat_category`, `line_value` and
  -- `direction_predicted` are all NOT NULL, and SQLite cannot relax a NOT NULL
  -- without rebuilding the table - so sharing it would have meant a risky
  -- migration on every install, or storing a moneyline in a column called
  -- `line_value`. A new table needs no migration: create_all() makes it.

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
| POST | `/betting/<platform>/market` | **DraftKings only** (400 elsewhere). Body: `{fighter_a_id, fighter_b_id, market_type, method?, round_number?, moneyline}` → estimates the outcome's probability from stats, then compares it to the price. Saves a `MarketPrediction` + `Conversation`. Returns `{conversation_id, question, modelProbabilityPct, impliedProbabilityPct, edgePct, verdict, verdictLabel, profitPer100, expectedValuePer100, moneyline_display, reasoning}` — see §5.2 |
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

### 5.2 Priced fight markets (v0.6.0+)

DraftKings lists three markets that take a **moneyline** rather than an
over/under line, defined in `betting/markets.py`:

| `market_type` | Fields | Question put to the model |
|---|---|---|
| `method` | `method` ∈ KO/TKO, Submission, Decision, Draw | "Will A beat B by KO/TKO?" (a draw is phrased as the bout ending in one — naming a winner would be wrong) |
| `method_in_round` | `method` + `round_number` 1–5 | "Will A beat B by Submission in round 2?" |
| `round_reached` | `round_number` 2–5 | "Will A vs B reach round 3?" |

They overlap on purpose — a KO in round 2 is also a KO, and also a fight
reaching round 2 — because a sportsbook prices them separately and the
interesting question is often whether those prices agree.

Two combinations are refused rather than offered, because they cannot occur:

- **Draw in a round.** A draw is scored after the final round, so it can never
  land in one. `method_in_round` therefore omits Draw.
- **Reaching round 1.** Every fight does. `round_reached` starts at 2.

**The model is never shown the moneyline.** This is the rule the whole feature
rests on. The output is the *gap* between the model's probability and the
price's; a model told "the book says 27%" drifts toward 27%, and the gap stops
measuring anything except how obediently it repeats its input. The route
estimates first (`build_fight_market_prompt`, which has no odds parameter to
pass) and compares afterwards (`services/odds.py::assess`). A test asserts the
prompt never contains the price.

**Both verdict bands fail toward silence.** Under 5 points is reported as a
fair price, because that is inside the error bar of an LLM estimate. **Over 20
points is reported as "Gap too large to trust"** and the expected-value figure
is suppressed entirely. A liquid market is not wrong by twenty points; a
language model asked for a probability routinely is. This was not theoretical —
during development a local model priced *KO/TKO in round 2* **above** *KO/TKO
in any round*, which is impossible since one is a subset of the other, and
without the upper band it would have rendered as a 54-point edge worth chasing.

The implied probability is the raw conversion of the price and therefore
**includes the sportsbook's margin**. De-vigging needs the opposite side of
the market, which a single-market form does not have, so the UI says so rather
than letting a 3-point edge read as free money.

## 6. Page-by-Page UI Spec

All pages share `base.html` (left nav: Dashboard, PrizePicks, DraftKings, Kalshi, Chat, Settings) and the dark MMA theme (`static/css/theme.css`: near-black background, crimson accent). The nav collapses to a 64px icon rail via a toggle; the state persists in `localStorage` and is applied by an inline `<head>` script **before first paint**, or the sidebar visibly flashes open on every navigation.

- **Dashboard (`/`)**: stat tiles that count up (fighters with stats / fighters known / predictions made), two **measured** status chips (§6.1), a dismissible update banner when a newer release exists (§13), and recent predictions with a "Continue in Chat" link.
- **PrizePicks / DraftKings / Kalshi (`/betting/<platform>`)**: the matchup is picked **once** at the top of the page — Fighter A and Fighter B (autocomplete, arrow-key navigable) in their own card, shared by every form below it. It used to live inside the stat-prop form, which was fine while that was the only form; with four on the DraftKings page it would have meant picking the same two fighters four times. Then a Stat Prop card: Stat Category (platform-specific subset), Line Value, Submit → shimmer skeletons while waiting, then a result card with an SVG confidence ring that draws while the number counts up in step, the OVER/UNDER call, reasoning, and "Continue in Chat". Platform pages differ only in accent colour, stat categories, and which extra cards they enable (`betting/platforms.py::PLATFORM_CONFIG`). **DraftKings additionally** renders the three priced markets of §5.2, each its own card: a model / edge / price triptych, a verdict pill, an expected-value line, and a standing note that the implied percentage carries the book's margin. The edge is always signed, and coloured by verdict rather than by sign — green for value, amber for a gap too large to trust, so a miscalibrated estimate never renders as a jackpot. **Kalshi additionally** has a free-text market-question card (§5.1): a textarea, a probability ring, and a Leans Yes / Leans No / Toss-up verdict — 45–55% reads as a toss-up, since anything finer is inside the noise of an LLM estimate. It states plainly whether the answer is stat-grounded, because a confident-looking ring on a question naming no known fighter would otherwise read as far more authoritative than it is.
- **Chat (`/chat/`)**: full-screen — no page padding, no reading-measure cap, and the transcript is the only thing that scrolls. Two states share **one** composer: an empty conversation centres it under "Where should we begin?" with suggestion rows; sending settles it to the bottom under the thread. Sharing the element means starting a conversation doesn't move focus or discard typed text. Replies reveal progressively (rAF against a token budget, so pacing holds regardless of length), auto-scroll only sticks while already near the bottom, and every assistant message has a hover Copy. The conversation rail has its own independent collapse toggle.
- **Settings (`/settings/`)**: Provider selector (Ollama / OpenAI / Gemini / Deepseek / Claude) — Ollama shows locally installed models, cloud providers a masked key input; both offer Test Connection. "Fighter Database" panel: Sync Now with a real progress bar (it reads "Discovering the roster…" during the phase where no total exists yet, rather than a misleading 0%). "App Version" panel: installed version, Check for Updates, and release notes.

### 6.1 Status chips report measured state, not configuration

Both dashboard chips derive from reality (`app/services/status.py`), which is a
deliberate correction of an earlier design where they were decorative:

- **Fighter database** — counts and freshness straight from the `fighters`
  table, keyed on `max(stats_scraped_at)`. It must **not** key on a
  `last_fighter_sync_at` setting, which only a manual sync ever wrote: a seeded
  install has real per-fighter scrape timestamps but no such setting, so that
  version told every new user their database was empty while they sat on a full
  roster, and pushed them toward a ~28h scrape they didn't need. Green when
  stats exist, amber past 30 days (matching the point a sync would actually
  re-fetch), red when nothing usable.

  The **Settings → Fighter Database** card was left on the setting when the
  chips were fixed, so until **v0.5.4** the two surfaces contradicted each
  other over the same table — the wrong one sitting directly above the button
  that starts the scrape. Both now share `fighter_db_status()`, and the card
  additionally reports what a sync would actually fetch (how many fighters are
  known by name and record but carry no stats yet). The setting itself was
  deleted in **v0.5.5**, once nothing read it; rows left in existing databases
  are simply never consulted.
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
  (whichever of the three in §11 applies) has no database yet, it copies the
  bundled seed in; if a database already exists (any prior run, including
  one the user has since synced further), it is **never** overwritten.
  Skipped entirely under `TestConfig` so unit tests stay fast/isolated.
- Because the seed file is a real, fully-initialized app database, every
  fighter row carries the `stats_scraped_at` it was scraped with. The
  Dashboard chip and the Settings card both read `max(stats_scraped_at)`, so a
  fresh install correctly reports *when the bundled snapshot was captured*
  rather than a fake "just synced" timestamp — which is what tells a user it's
  time for an occasional refresh. (Freshness deliberately comes from the data,
  not from a setting; see §6.1 for the bug that taught us this.)
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
- All app data (SQLite DB, Chroma persistent directory, Fernet fallback key file) lives in a per-user directory, **never** inside the installed program directory — which may be read-only, and which the NSIS updater replaces wholesale on every update. Which directory depends on how the app was started, and Electron passes the answer down as `UFC_PREDICTOR_DATA_DIR` (§13.1):
  - **Installed build** → the Electron user-data directory (`%APPDATA%\MMA Assist\` on Windows). Survives updates *and* uninstalls, since `deleteAppDataOnUninstall` is false.
  - **Portable build** → `data\` beside the exe, so the whole folder stays movable.
  - **Backend run standalone** (dev, no Electron) → `%LOCALAPPDATA%\UFCPredictor\`, from `platformdirs`. This is the only case the bare `Config.data_dir()` default applies to.

### 11.1 Loopback server hardening (`app/security.py`)

Binding `127.0.0.1` keeps the port off the network but is **not** an access
control: the user's browser can reach it, and so can any page the user
visits. Three guards run as `before_request`/`after_request` hooks, verified
by `backend/tests/test_security.py` (each test fails if the hooks are
removed).

| Guard | Attack it closes |
|---|---|
| **Host allowlist** — only `127.0.0.1`, `localhost`, `::1` | **DNS rebinding.** An attacker points `evil.com` at `127.0.0.1` after first load; the browser then treats our responses as `evil.com`'s origin, so the same-origin policy is *satisfied* and CORS never applies. Chat history, saved predictions, and provider settings were all readable. A rebound request cannot claim a loopback Host without giving up the origin it wants to read from. |
| **Origin / `Sec-Fetch-Site` check** on unsafe methods | **CSRF.** A cross-origin form POST is a "simple request": no preflight, no CORS opt-in needed to *send* it. JSON endpoints shrugged these off only incidentally (`get_json()` insists on `application/json`, which does force a preflight), but `POST /chat/new` and `POST /settings/sync-fighters` take no body at all and were fully exposed — the latter starts a multi-hour scrape of ufc.com **from the user's own IP**. |
| **Response headers** — CSP, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` | Defence in depth for the chat page, which renders LLM output. |

The Host and origin checks reinforce each other and neither is redundant: a
rebound request looks same-origin to the browser, so only the Host check
stops it passing the origin test as well.

`UFC_PREDICTOR_ALLOWED_HOSTS` (comma-separated) extends the allowlist for a
deliberate `--host 0.0.0.0` run. Off by default — exposing this app to a
network should have to be typed out.

**CSP shape:** `script-src` is strict (`'self'` plus a per-response nonce for
the one pre-paint inline block in `base.html`). `style-src` keeps
`'unsafe-inline'` because several templates carry `style=""` attributes and
CSP has no nonce mechanism for those; that is the deliberately weaker half,
since style injection cannot execute code.

### 11.2 Untrusted input boundaries

- **The update manifest is remote data, not configuration.** Its
  `downloadUrl`/`downloadPageUrl` reach an `href`, where a `javascript:`
  value would execute in the app's own origin with access to every
  same-origin endpoint. Filtered to http(s) in **both** `services/updates.py`
  (`_safe_http_url`) and `static/js/common.js` (`safeExternalUrl`).
- **`shell.openExternal` is a launch primitive**, not a link opener — it
  delegates to the OS protocol handler, which acts on `file:`, `smb:` and the
  `ms-*:` family. Since the renderer displays model-generated text, `desktop/main.js`
  funnels every call through `openExternalSafely`, which allows only
  http/https/mailto.
- **LIKE wildcards in fighter autocomplete are escaped.** Unescaped, `%`
  matched all ~6,700 rows on both indexed columns on every keystroke.
- Templates rely on Jinja2 autoescaping (no `|safe`, no `Markup`), and the
  static JS writes message content with `textContent`, never `innerHTML`.

## 12. Folder Structure

```
backend/        Flask app + scraper + RAG. The application itself.
  app/
    blueprints/   main, betting (platforms + markets), chat, fighters, settings
    models/       SQLAlchemy: Fighter, Conversation, Message, Prediction,
                  MarketPrediction, AppSetting, ScrapeCheckpoint
    services/     ai/ (providers, prompts), rag/ (chroma, ingest, retrieve),
                  scraper/ (sitemap, client, parser, pipeline), secrets/,
                  db/, status.py, updates.py, odds.py, fighter_mentions.py
    templates/    Jinja: base, index, chat, settings, betting/form
    static/       css/ (theme, chat, betting), js/ (common, chat, betting,
                  settings, status)
    seed_data/    Bundled pre-scraped DB (gitignored except its README; §10)
    version.py    Semver comparison + whatever Electron passed as --app-version.
                  No release number of its own (only a "0.0.0-dev" sentinel).
  pyinstaller/  app.spec
  scripts/      scrape.py, build_seed_data.py, build_release.py, set_version.py
  tests/        169 tests, no network

desktop/        Electron shell. The shipped product (§2.2).
  main.js       window, menu, lifecycle, update IPC
  backend.js    spawn + /health + data-dir resolution + teardown
  updater.js    electron-updater wrapper (§13.2)
  datamigrate.js  one-time portable -> installed data import (§13.1)
  preload.js    argument-free update bridge (§13.2)
  splash.html, package.json (version source)
  build/        icon.ico
  certs/        code-signing.pfx + DPAPI-encrypted password (gitignored)
  scripts/      sign-backend, new-signing-cert, trust-cert, make-icon
  tests/        31 tests (packaging whitelist, updater error mapping)

frontend/       React + Vite marketing site.
  src/{pages,components,hooks,styles}
  src/lib/      versionJson.ts — shared manifest types + fetch hook
  public/       version.json (download + update manifest), downloads/ (gitignored)
  tests/        42 tests

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
4. `python backend/scripts/set_version.py <x.y.z>` → bumps `desktop/package.json`, the single source of truth for the version (§4 of `desktop/README.md`).
5. `pyinstaller backend/pyinstaller/app.spec` → `backend/dist/UFCPredictor/` (onedir, contains `UFCPredictor.exe`).
6. **`desktop/scripts/sign-backend.ps1 -Password <pfx>`** → signs step 5's `UFCPredictor.exe`. Must run **before** step 7: electron-builder copies that binary in as a resource, so signing it afterwards leaves the copy inside the installer unsigned. The script has its own freshness guard against a stale bundle.
7. `$env:CSC_KEY_PASSWORD = <pfx>` then `cd desktop && npm run dist` → copies step 5's folder in as `resources/backend` and emits **both** Windows artifacts (§13.1): `MMA Assist-<version>-setup-x64.exe` (NSIS, signed) and `MMA Assist-<version>-win.zip` (portable, ~230MB; ~630MB extracted), plus `latest.yml` and a `.blockmap`.
8. `python backend/scripts/build_release.py --github-release OWNER/REPO --notes "..."` → renames step 7's artifacts to their published names, copies them plus `latest.yml` and the matching blockmap into `frontend/public/downloads/`, and regenerates `version.json` (URL, size, SHA-256, notes).
9. Create the GitHub release and upload all four files. **Publish it as a draft first, upload, then un-draft** — an empty release at `releases/latest` makes every installed copy's update check 404 for the duration of the upload.

> **Forgetting `CSC_KEY_PASSWORD` does not fail early.** The build runs for
> several minutes and then dies on `SignTool Error: The specified PFX password
> is not correct`, which reads like a corrupt certificate rather than an unset
> variable. The password is stored DPAPI-encrypted at
> `desktop/certs/pfx-password.dpapi`; `desktop/README.md` has the recovery
> snippet for both steps.

> **Rebuild step 4 whenever `backend/` changes.** electron-builder copies
> `backend/dist/UFCPredictor` in verbatim; it cannot tell the Python source
> moved on. A stale bundle fails confusingly rather than loudly — one built
> before `run.py` grew `--port` ignored the flag, bound its default 8765
> instead of the port Electron assigned, and the app died on a health-check
> timeout while a perfectly healthy server sat on the wrong port.

### 13.1 Two Windows artifacts: installer and portable

From **v0.5.0** Windows ships both, from one `npm run dist`:

| Artifact | Data location | In-app update |
|---|---|---|
| `MMA-Assist-<v>-setup-x64.exe` (NSIS, **primary**) | user profile | **Yes** — see 13.2 |
| `MMA-Assist-<v>-portable-win64.zip` | `data/` beside the exe | No — download and replace |

The installer is primary because **electron-updater only supports NSIS on
Windows**; `zip` and `portable` are not auto-updatable targets. Keeping the
zip costs one line of build config and preserves the no-install path for
anyone who wants it.

`desktop/backend.js::resolveDataDir()` resolves the location per launch, in
this order:

1. An existing `UFC_PREDICTOR_DATA_DIR` (tests/dev).
2. macOS packaged → `~/Library/Application Support`.
3. **An existing `data/` folder beside the exe → use it.** Checked *before*
   the installed-build test, deliberately. This is the compatibility
   guarantee for everyone already on the portable build: no future change to
   how "installed" is detected can quietly point them at an empty directory,
   which would re-seed and look exactly like data loss.
4. An installed build (uninstaller present beside the exe) → user profile.
   Nothing may live in the install directory, because the updater replaces
   it wholesale.
5. Otherwise → create `data/` beside the exe; `%LOCALAPPDATA%` if unwritable.

There is no flag from electron-builder distinguishing the two targets — both
package the identical `win-unpacked` tree — hence the uninstaller check.

Because the portable path is derived from `process.execPath` every time and
never persisted, moving that folder to another drive or a USB stick keeps
working. Electron passes the result down as an env var, so the Python side
stays generic.

**Switching portable → installed** would otherwise strand the user's data in
the old folder. `desktop/datamigrate.js` runs on the first launch of an
installed build that finds an empty data directory and *offers* a one-time
import (they pick the old folder; it copies the database, Chroma directory
and secret files). Never silent, never guessed.

On the Download page the installer is a plain link; the portable zip sits
behind a disclosure and keeps the `showDirectoryPicker()` flow where
available (Chromium only, secure context only) to stream straight into a
chosen folder. Firefox and Safari fall back to an ordinary download link,
and any failure — CORS on a cross-origin release asset being the likely one
— falls back too. `DownloadButton.tsx` renders both the 0.5.0 manifest shape
(installer at the root, zip under `platforms.winPortable`) and the older one
(zip at the root), because a cached deploy can serve either.

Electron's single-instance lock is app-wide rather than per-data-directory,
so two portable copies cannot run simultaneously even though their databases
are separate.

**Not done yet**: builds are signed with a *self-signed* certificate, which
only suppresses "Unknown Publisher" on machines that trust it. SmartScreen
reputation is keyed to a publicly-trusted certificate with download history,
so public downloads still show "Windows protected your PC". The Download page
says so and publishes the SHA-256 to verify against.

**Versioning.** `desktop/package.json`'s `version`
is the single source of truth — electron-builder stamps the installer from
it, `desktop/main.js` passes it to the backend as `--app-version`, and
`build_release.py` reads it back off the installer filename. The Python
side deliberately declares no version constant (`app/version.py` holds only
comparison logic and the value Electron supplied), so the two cannot drift.
`scripts/set_version.py` bumps it.

### 13.2 In-app updates (v0.5.0+)

The installed build updates itself: **Settings → Check for Updates →
Download → Restart & Install**. `desktop/updater.js` wraps
`electron-updater`; `desktop/main.js` exposes it over IPC.

**Two feeds, deliberately not merged.**

| Feed | Read by | Purpose |
|---|---|---|
| `latest.yml` on the GitHub release | the installed app, via electron-updater | what actually drives the update |
| `version.json` on the website | the Download page, browsers, the portable build | announcement + manual download |

Inside the desktop app the updater is authoritative, because it is the thing
that will perform the install. Driving the dashboard banner off the website
manifest *as well* would let the two disagree — a release exists but
`version.json` has not caught up — and show a prompt the Settings page then
contradicts. Both `status.js` and `settings.js` feature-detect
`window.mmaAssist.updates` and fall back to the Flask endpoint in a plain
browser or a portable build.

**Forgetting to upload `latest.yml` is a silent failure**: the app simply
keeps reporting it is current. `build_release.py` copies it next to the
installers and prints a reminder, and warns loudly if the nsis target did
not produce one.

**Differential downloads.** The `.blockmap` (`nsis.differentialPackage`)
means an update transfers only changed blocks. This matters more than it
sounds: of ~630MB uncompressed, `resources/backend` is 294MB and the
Electron runtime is ~300MB, while a typical release changes ~100KB of JS and
Python. Without blockmaps every patch release is a quarter-gigabyte download.

**The updater is a remote-code-execution channel by design.** Four controls:

| Vector | Control |
|---|---|
| Renderer compromise (the chat page renders LLM output) | Every IPC method is **argument-free**. The renderer may say "go", never "go *here*". |
| Tampered manifest redirecting the binary | Feed pinned at build time in `publish`, baked into `app-update.yml`. Never manifest-supplied. |
| Compromised release asset | `win.verifyUpdateCodeSignature` checks Authenticode against `publish[].publisherName` (`OppositeMusical`). |
| MITM | HTTPS + sha512 from `latest.yml`. |

⚠️ **Signature verification fails for users who never imported the
self-signed certificate.** That is correct and must stay — but the raw error
reads like a corrupt download, which invites exactly the wrong response.
`updater.js::describeError()` rewrites it to name the certificate and say
*do not install* if unexpected. A publicly-trusted OV certificate would
remove both this cliff and the SmartScreen friction; it is the single
highest-value purchase for this project.

**Install ordering.** Windows will not overwrite a running executable, and
`resources/backend` is exactly that. `install()` awaits
`stopBackendAndWait()` before `quitAndInstall()`; the wait resolves rather
than rejects on timeout, because blocking the update forever beats letting
the installer report a locked file.

**Kill switch.** `minSupportedVersion` in `version.json` escalates status
from `available` to `required`, and a required update's banner is not
dismissable. Absent or malformed values fall back to the ordinary optional
path — a manifest typo must not force-update everyone.

Comparison is numeric, not lexical (`0.10.0` > `0.9.0`), a prerelease sorts
below its own release, and an unparseable or older published version never
prompts — a bad manifest must not push users into a "downgrade update".

**Rollback** is manual: keep older releases downloadable. Retaining a
~600MB previous copy on disk is not worth it for a single-user tool.

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

## 14. What Has and Hasn't Been Verified

**Verified end to end** (as of v0.5.7):

- **A real signed build.** Every shipped artifact since v0.5.0 is Authenticode-signed with SHA-256 and an RFC3161 timestamp, and `signtool verify /pa` passes.
- **A real in-app update.** Driven for real from 0.5.0 → 0.5.1 and re-checked each release since: the app downloads, verifies the signature, quits, installs silently and relaunches with the user's database, chats and predictions intact.
- **The packaged app against a live AI provider.** Predictions, Kalshi market questions, chat continuation, fighter autocomplete and the update check are all exercised against a running Ollama on the packaged build before each release — not just against mocks.
- **A full multi-thousand-fighter live scrape** against ufc.com (§10); it is how the shipped database was produced.

**Still unverified — do not claim otherwise:**

- **A machine that has never had Python, Node, or this repo on it.** Everything is bundled and the packaged path is exercised against an empty data directory, but a genuinely clean machine remains the authoritative test.
- **Signature verification where the certificate is *not* trusted.** The cert is self-signed and imported into Trusted Root on the dev machine. On any other machine `win.verifyUpdateCodeSignature` should *correctly refuse* the update — that refusal path has never been observed on real hardware, and `updater.js::describeError()` exists to explain it if it happens.
- **Differential updates.** `differentialPackage` is on and blockmaps are published, but every observed update has transferred the full installer.
- **Paid cloud LLM providers.** No live keys are configured; OpenAI/Gemini/Deepseek/Claude are validated against mocked HTTP/SDK layers only.

## 15. Open Questions / v2 Ideas

**Done since first draft** — kept here so the history is legible:
- ~~Embedded webview instead of the system browser~~ → done, as an Electron shell rather than pywebview (§2.2).
- ~~Auto-update mechanism~~ → **reversed and shipped in v0.5.0.** This spec previously argued against it: *"silently replacing an executable is a bigger trust ask than this app needs to make."* The reasoning was sound about *silence*, not about updating — so what shipped keeps the consent and drops the manual download. Nothing is fetched until the user presses Download, nothing installs until they press Restart & Install, and the downloaded installer's signature is verified against the expected publisher before it runs (§13.2).
- ~~An app icon~~ → done in v0.5.2; generated by `desktop/scripts/make-icon.ps1` into `build/icon.ico`, used for the window, taskbar and installer.
- ~~Code signing~~ → done in v0.5.0, with the caveat below.

**Still open:**
- **A certificate a stranger's machine trusts.** Builds are signed, but with a *self-signed* certificate, so SmartScreen still warns on public downloads and the in-app updater will refuse to install on any machine that hasn't imported the cert. Needs a purchased CA certificate; until then the Download page publishes a SHA-256 and explains the warning.
- **macOS/Linux packaging.** The Download page already lists macOS as coming soon. `desktop/backend.js` resolves a POSIX venv path and treats darwin as non-portable (§13.1), but PyInstaller must be run on each target OS and none of it is tested there.
- **Stat-less fighters in autocomplete.** 3,262 of 6,746 roster entries are historical or never-competed profiles ufc.com lists without stats. They're currently selectable, so a user can pick someone the AI has nothing to reason about. Keep them in the database, exclude them from autocomplete.
- **Retry the 5 checkpointed scrape errors** from the full run (§10); they're marked `error`, so a resync picks up only those.
- Optional model-driven tool-calling for chat on providers that support it well (OpenAI/Anthropic/Gemini), layered on top of the deterministic fuzzy-match injection rather than replacing it — Ollama must keep working the same way.
- Dictation in the chat composer via the Web Speech API.
