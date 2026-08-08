# accounts

Accounts, Stripe payments, and the licence tokens the desktop app verifies.
Java 21 / Spring Boot 3.5, one deployable, one PostgreSQL database.

Design rationale lives in [`../docs/ACCOUNTS_AND_PAYMENTS_SPEC.md`](../docs/ACCOUNTS_AND_PAYMENTS_SPEC.md).
This file is the operator's guide.

> **Status: not deployed, and not ready to take live payments.** Every plan row
> still carries a placeholder Stripe price id, and the phase-7 items in the spec
> (reconciliation alerting, a restore drill, live-mode keys) are not done. See
> [Before live mode](#before-live-mode).

## Layout

```
src/main/java/com/mmaassist/accounts/
  platform/     errors, auth filter, rate limiter, audit, config, spi/
  identity/     accounts, OAuth brokers, sessions, devices, refresh tokens
  billing/      plans, Stripe checkout, webhook pipeline, entitlements
  licensing/    Ed25519 signing, JWKS, licence issuance
src/main/resources/db/migration/   Flyway: V1 platform, V2 identity,
                                   V3 billing, V4 plan seed, V5 licensing
```

Dependencies point one way — `licensing → billing → identity → platform` — and
`ModuleBoundaryTest` fails the build if that changes. Where a lower module needs
something from a higher one, the interface lives in `platform/spi/`
(`EntitlementLookup`, `AccountClosureListener`).

## Running it

```bash
docker run -d --name mmaassist-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=mmaassist postgres:16-alpine

mvn spring-boot:run
```

Flyway migrates on boot. With no Stripe keys and no OAuth credentials the
service still starts: checkout returns `billing_unavailable`, sign-in returns
`provider_not_configured`, and a warning explains both at startup.

```bash
mvn test      # unit tests; the Testcontainers ones skip without Docker
mvn verify    # everything, which is what CI runs
```

### Webhooks locally

```bash
stripe listen --forward-to localhost:8080/webhooks/stripe
stripe trigger checkout.session.completed
```

The printed `whsec_…` goes in `STRIPE_WEBHOOK_SECRET`. There is no way to
develop this path without it: the service refuses every webhook when no secret
is configured, because accepting unverified ones would let anyone grant
themselves a licence with one `curl`.

### Generating a licence signing key

```bash
mvn -q compile
java -cp target/classes com.mmaassist.accounts.licensing.Ed25519Keys
```

Prints `LICENCE_SIGNING_KEY` (base64 of the 32-byte seed followed by the
32-byte public key) and the public half for the desktop app. Left unset, the
service generates an ephemeral key at startup and logs a warning — fine
locally, ruinous in production, where every restart would invalidate every
licence in the field.

## Configuration

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | Railway's `postgres://` form is translated to JDBC automatically |
| `SITE_ORIGIN` | yes | The single allowed CORS origin |
| `API_BASE_URL` | yes | This service's public URL; OAuth redirect URIs are built from it |
| `SESSION_COOKIE_DOMAIN` | prod | `.mmaassist.com`, so the cookie reaches the API subdomain |
| `SESSION_COOKIE_SECURE` | prod | `true` |
| `STRIPE_SECRET_KEY` | for billing | |
| `STRIPE_WEBHOOK_SECRET` | for billing | Per environment; each endpoint has its own |
| `GOOGLE_CLIENT_ID` / `_SECRET` | for sign-in | |
| `GITHUB_CLIENT_ID` / `_SECRET` | for sign-in | The OAuth app needs the `user:email` scope |
| `LICENCE_SIGNING_KEY` | for licences | See above |
| `LICENCE_SIGNING_KID` | for licences | Names the key in the JWKS document |

## Deployment

A Railway service with Root Directory `accounts/`, plus the Postgres plugin.
`railway.json` selects the Dockerfile and points the healthcheck at
`/actuator/health/readiness` — which probes the database and deliberately does
not probe Stripe, so a Stripe blip cannot restart the service.

**Single replica.** Three things are in-process: the rate limiter, the pending
OAuth state store, and the webhook poller. A second replica multiplies the rate
limit, breaks any sign-in whose callback lands on the other instance, and has
two pollers competing (that last one is already safe — the claim query uses
`for update skip locked`). Moving the first two to Redis is the prerequisite for
scaling out.

## Decisions that will look odd without the reason

**No Spring Security.** The authentication surface is "opaque token → database
row → account", and Spring Security's value here would be mostly its CSRF
machinery, which this design does not use: the session cookie is `SameSite=Lax`,
so a cross-site POST never carries it. What Spring Security would have supplied
for free is instead explicit — `SecurityHeadersFilter` sets the headers,
`AuthenticationFilter` resolves the caller, and endpoints declare their own
requirement by taking an `AuthPrincipal` parameter. The trade is a smaller,
more legible auth path against giving up a well-audited framework; if this
service grows roles, scopes, or a second token type, revisit it.

**JSON columns are `text`, not `jsonb`.** Nothing queries inside them —
`features`, the webhook payload and the audit detail are read whole and parsed
in Java. `text` avoids a Hibernate type mapping that could only be validated
against a live PostgreSQL, and promoting a column later is one `ALTER`.

**Webhook payloads are parsed with Jackson, not the Stripe SDK's models.**
Stripe pins an event's shape to the API version that produced it, so an SDK
upgrade can start failing to parse events already sitting in the table. Reading
the handful of fields we use keeps old events replayable indefinitely. The SDK
is still used for outbound calls and — importantly — for signature
verification, which is not hand-rolled.

**The licence token is assembled by hand.** It is a compact JWS built in
`LicenceTokenSigner` rather than through a JOSE library. That is defensible
only because this service exclusively *signs*: algorithm confusion is a
verifier bug, and the verifier is Python
(`backend/app/services/licensing/token.py`), which pins EdDSA and rejects
everything else. The two are held together by a shared fixture — see below.

## The cross-language contract

`backend/tests/fixtures/licence_contract.json` holds a token, the key that
verifies it, and the claims it should decode to.

- `LicenceContractTest` (Java) asserts the signer still reproduces that exact
  token. Ed25519 is deterministic, so with a fixed key and fixed claims the
  output is a fixed string.
- `backend/tests/test_licensing_contract.py` asserts the verifier still accepts
  it and reads every gated feature back correctly.

Change the claim set and one side fails. Without this, both suites would stay
green while every paying customer lost access — neither language can see the
other, and this is the seam where that matters most.

To regenerate deliberately: delete the fixture, run the Java test (it writes
the file and fails once), commit it, then run the Python contract test.

## Before live mode

1. **Get the Stripe account approved.** This product generates betting-prop
   predictions; Stripe's restricted-business list covers gambling. That is
   their call to make, and a rejection invalidates this whole billing design in
   favour of a merchant of record. Spec section 4.2.
2. Replace the placeholder `stripe_price_id` values in `billing.plans` for each
   environment. `PlanCatalogueValidator` logs an error at startup for any that
   are still placeholders.
3. Set a real `LICENCE_SIGNING_KEY`, and bake the matching public key into the
   desktop build.
4. Wire alerting to the reconciliation job's warnings and to unprocessed
   `stripe_events` older than five minutes — the job repairs drift *and* shouts,
   because a silent repair hides a webhook endpoint that has been failing for a
   week.
5. Verify a database restore actually works. This database holds the only
   record of which account paid; Stripe can rebuild the payments but not the
   links to accounts.
