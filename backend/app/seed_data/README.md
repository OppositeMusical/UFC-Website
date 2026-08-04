# Bundled seed data

This directory ships inside the packaged app (see `pyinstaller/app.spec`) so a
fresh install already has real UFC fighter stats instead of an empty database
the user would otherwise have to wait hours to populate via a live scrape.

Populated by `scripts/build_seed_data.py`, which copies a fully-scraped
`ufc_predictor.db` + `chroma_db/` from a source data directory into:

- `ufc_predictor.seed.db`
- `chroma_db/`

`app/utils/seed.py::maybe_seed_data_dir()` copies these into the user's real
app data directory on first launch only - it never overwrites an install that
already has data. Users can always get current data afterwards via
Settings -> Sync Now; this only removes the *initial* wait.

Because every seeded fighter arrives with `stats_scraped_at` already set, a
resume-mode sync keys off staleness rather than "has this ever been scraped"
(`pipeline.DEFAULT_MAX_AGE_DAYS`, 30 days) - otherwise Sync Now would only
ever pick up debutants and seeded stats would stay frozen at bake time.
Practical consequence: the fresher the seed is at release, the less work a
user's first sync does, so re-bake close to shipping.

Neither the seed `.db` nor `chroma_db/` is tracked in git (see `.gitignore`) -
they are ~28MB of generated build output. Only this README is committed, since
`pyinstaller/app.spec` requires the directory to exist at build time.

Re-bake before cutting a release:

```
python scripts/build_seed_data.py --source-data-dir <dir with a fresh full scrape>
```

See docs/SPEC.md section 11 for the full packaging process.
