# CI/CD

Two workflows. [`ci.yml`](../.github/workflows/ci.yml) tests and builds
everything on every push; [`release.yml`](../.github/workflows/release.yml)
guards version tags.

## What runs on every push and pull request

| Job | Covers | Roughly |
|---|---|---|
| **Java · accounts service** | `mvn -B verify` — 106 tests including the Testcontainers integration tests | ~1 min |
| **Python · desktop app backend** | `pytest tests` — 112 tests, including the licence verifier and the cross-language contract | ~1 min |
| **Node · marketing site** | `npm ci`, `npm run build` (which is `tsc -b && vite build`, so a type check too), `npm test` — 34 tests | ~1 min |
| **Node · Electron shell** | lockfile resolves, sources parse. No tests exist here | ~30s |
| **Docker · accounts image** | builds the production Dockerfile; publishes to GHCR only from `main` | ~1–2 min |
| **all green** | aggregates the five above into one status | instant |

They run in parallel, so wall clock is roughly the slowest job.

### Why there are no path filters

The previous workflow was filtered to `accounts/**`. Two consequences: most of
the repository had no CI at all, and a required status check would never arrive
on a pull request that did not touch the filtered paths — the check sits
"expected — waiting" and the PR cannot merge. Running everything on everything
costs a few minutes and removes both problems.

### Require **`all green`**, not the individual jobs

`gate` (displayed as *all green*) depends on every other job and fails if any of
them failed or was cancelled. Requiring that single check in branch protection
means adding a job later needs no change to the protection rule.

It is not currently enforced — branch protection is a repository setting, not
something a workflow can grant itself. To turn it on: **Settings → Branches →
Add rule** for `main`, tick *Require status checks to pass*, and select
**all green**.

### The cross-language contract

The Java job asserts the licence signer still reproduces
`backend/tests/fixtures/licence_contract.json` byte for byte; the Python job
asserts the verifier still accepts it. They are independent jobs — the fixture
is committed, so each side checks itself against it. Change the token format and
exactly one goes red, which tells you which side moved. Without this, both
suites would stay green while every paying customer lost access.

### Why the Docker image builds on every branch

The Dockerfile is what production runs. Building it only at deploy time means
discovering it is broken at the worst possible moment, so it builds everywhere
and is pushed only from `main`. Images land at
`ghcr.io/<owner>/ufc-website/accounts`, tagged with the commit SHA and `latest`.

## Deployment

The deploy jobs are **inert until secrets are configured**, and they have never
run. Treat the first execution as something to watch.

| Secret / variable | Purpose |
|---|---|
| `RAILWAY_TOKEN` | Enables the deploy jobs. Absent, they skip |

When set, `main` pushes deploy `accounts` and then `frontend` to Railway, one at
a time, and only after *all green* passes. The service names in the matrix must
match the Railway service names.

**If you enable this, turn off Railway's own GitHub auto-deploy for those
services.** Otherwise every push deploys twice — and Railway's integration does
not know about GitHub Actions, so it would deploy a red commit, which is the gap
this wiring exists to close. That matters more than usual here: Flyway migrates
on boot, so a deploy is also a schema migration.

The Railway CLI is installed unpinned because this path is unverified; pin it
the first time it succeeds.

## Releases

Tagging `v0.5.0` runs the consistency check. It compares the tag against
`desktop/package.json` (the single source of truth for the version) and against
`frontend/public/version.json` (the download pointer *and* the update manifest
installed copies poll), and sanity-checks the manifest's SHA-256, size and
filename.

Run it locally before tagging:

```bash
node .github/scripts/check-release.mjs 0.5.0
```

**CI does not build the Windows artifact**, and cannot. The packaged app bundles
a pre-scraped seed database (SPEC.md §10) that is gitignored, ~28MB, and
produced by a multi-hour crawl honouring ufc.com's 15-second crawl delay.
Building without it would ship an app whose first run has an empty fighter
database. Packaging stays manual, on a machine that holds the seed; the workflow
summary prints the remaining steps.

## Gaps worth knowing about

- **Deploys are unverified.** The wiring is right in shape; the Railway CLI
  invocation has never been executed.
- **No coverage thresholds, no linting.** Neither exists in the repo today;
  adding a linter would fail on pre-existing code and teach people to ignore red.
- **No dependency or secret scanning.** Dependabot and secret scanning are
  repository settings, worth enabling for a payments service.
- **`accounts` still has placeholder Stripe price ids**, so a deploy would come
  up unable to sell anything. See `accounts/README.md` before live mode.
