# UFC Predictor

An MMA-themed product with two parts:

1. **`frontend/`** - a static marketing site (React + Vite) that explains the product and links to the Windows download.
2. **`backend/`** - the actual downloadable app: a Python/Flask local web app with local (Ollama) and cloud (OpenAI, Gemini, Deepseek, Claude) AI support, PrizePicks/DraftKings/Kalshi prediction pages backed by a ChromaDB RAG layer over real UFC fighter stats, and a persistent chatbot.

**Full technical spec (architecture, data models, API contracts, page-by-page UI spec, scraper design/ethics, setup & packaging instructions): [`docs/SPEC.md`](docs/SPEC.md).**

## Quick start (backend/desktop app)

```
cd backend
pip install -r requirements.txt
python run.py
```

Opens `http://127.0.0.1:8765/` automatically. Fighter predictions need real stats first:

```
python scripts/scrape.py --limit 50
```

Run the test suite:

```
pip install -r requirements-dev.txt
pytest tests/
```

Package for distribution (Windows, onedir - see `docs/SPEC.md` section 12 for the mandatory pre-build step):

```
pyinstaller pyinstaller/app.spec
```

## Quick start (marketing site)

```
cd frontend
npm install
npm run dev      # local dev server
npm run build    # production build -> frontend/dist
npm run test     # vitest
```

## Data source note

The fighter-stats scraper targets `ufc.com` (the UFC's own official site), **not** UFCStats.com or ESPN - see
`docs/SPEC.md` section 2.1 for why those were ruled out and why ufc.com is both compliant and higher quality.
