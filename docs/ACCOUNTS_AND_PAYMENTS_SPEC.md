# Accounts & Payments — Design Spec

Status: **partly built.** Phases 1–6 are implemented on the
`claude/accounts-payments-impl-test` branch; see [§17](#17-implementation-status)
for exactly what exists, what the code does differently from this design, and
what is still missing.
Scope: a **Java/Spring Boot service** that owns user accounts, Stripe payments, and
the licence tokens the desktop app checks.

Read [`SPEC.md`](SPEC.md) first — this document assumes its architecture and
changes two of its stated non-goals.

> **Where the schema is defined.** The DDL quoted in §6.1 and §7.2 is the
> design sketch. The authoritative schema is
> `accounts/src/main/resources/db/migration/`; §17.2 lists every place the two
> deliberately differ.

---

## 1. What this changes about the product

`SPEC.md` §1 says of the marketing site: *"No backend, no accounts, no user data"*,
and §11 says *"No telemetry, no external data collection beyond the user's own
configured AI provider calls."* **Both statements stop being true.** That is the
real cost of this feature, and it should be a deliberate decision rather than a
side effect:

| Today | After |
|---|---|
| Static site, no database, no PII | A service holding email addresses, payment records, and IP/user-agent per session |
| App never contacts our infrastructure except a 6-hourly `version.json` fetch | App calls the licence endpoint on activation and roughly weekly to refresh its token |
| Nothing to breach | GDPR/CCPA obligations, a privacy policy, terms of service, a refund policy, and a real security surface |
| Delete the folder and it's gone (Download page copy) | Still true locally, but an account persists server-side until deleted |

Docs that must be updated as part of this work, not after: `SPEC.md` §1 non-goals
and §11 security notes, `README.md`, and the Download page's privacy copy
(`frontend/src/pages/Download.tsx`).

### 1.1 Enforcement is a speed bump, not DRM — say so up front

The desktop app runs entirely on the user's machine, using the user's own Ollama
install or their own API keys. **There is no server-side value to withhold.** A
determined user can patch the licence check out of a portable, unsigned Python
bundle in an afternoon, and no amount of obfuscation changes that.

The design therefore optimises for *honest users having a frictionless experience*
— fast activation, generous offline grace, no phone-home stalls — and explicitly
does **not** invest in anti-tamper, code virtualisation, or hardware binding.
Budget for that engineering elsewhere.

### 1.2 Why Java, alongside a Python backend

The user asked for Java, and the boundary happens to be a clean one: this service
shares no code, no database, and no deployment with `backend/`. They talk over
HTTPS with a signed token, and nothing else. The cost is a second toolchain in CI
(Maven + JDK 21 alongside pip and npm) and a second deployment target — real, but
bounded. Nothing in the design depends on the language choice.

---

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Language / framework | Java 21, Spring Boot 3.5, Maven | Java 21 is installed and LTS; Boot gives Actuator and Flyway wiring out of the box. Spring Security is deliberately *not* used — see §17.2 |
| Deployable count | **One** service, three internal modules | §5.1 |
| Database | PostgreSQL 16, managed (Railway) | Money needs transactions, constraints, and `numeric`/`timestamptz`. SQLite is right for the desktop app and wrong here |
| Schema migrations | Flyway | Versioned, checked into git, runs on boot. Unlike the desktop app (which uses hand-written additive upgrades) this DB has real referential integrity to protect |
| Payment provider | Stripe (Checkout + Billing Portal + webhooks) | Card data never touches our servers → PCI **SAQ A**. Portal removes an entire UI surface (cancel, update card, invoice history) |
| Sign-in | Google (OIDC) + GitHub (OAuth2). No passwords | Nothing to hash, leak, or reset. §6 covers the GitHub email-verification trap |
| Browser session | Opaque session cookie, HttpOnly/Secure/SameSite=Lax | No JWT-in-localStorage. Revocable server-side, immune to XSS token theft |
| Desktop auth | OAuth 2.0 authorisation code + PKCE, loopback redirect (RFC 8252) | The app already runs a local HTTP server on a random port — the redirect target exists for free |
| Entitlement transport | Ed25519-signed JWT, verified offline by the app | The app must work on a plane. §8 |
| Billing model | Lifetime one-time **and** monthly/annual subscription | Per the product decision. Both resolve to one `entitlements` row (§7.4) so the app never learns the difference |

---

## 3. Architecture

```
┌───────────────────────────┐        ┌──────────────────────────────────────────┐
│ frontend/ (React + Vite)  │        │ accounts/ (Spring Boot, Java 21)         │
│ mmaassist.com             │        │ api.mmaassist.com                        │
│                           │  fetch │                                          │
│  /pricing   plans + CTA   ├───────▶│  ┌────────────┐ ┌─────────┐ ┌──────────┐ │
│  /login     → IdP         │ cookie │  │ identity   │ │ billing │ │licensing │ │
│  /account   plan, invoices│        │  │ OAuth,     │ │ Stripe, │ │ Ed25519  │ │
│  /checkout/{ok,cancel}    │        │  │ sessions,  │ │ webhooks│ │ tokens,  │ │
└───────────────────────────┘        │  │ devices    │ │ ledger  │ │ devices  │ │
                                     │  └─────┬──────┘ └────┬────┘ └────┬─────┘ │
                                     │        └─────────────┼───────────┘       │
                                     └──────────────────────┼──────────────────┘
                                                            │
                    ┌───────────────────────┐   ┌────────────┴───────────┐
                    │ Stripe                │◀─▶│ PostgreSQL 16          │
                    │ Checkout, Portal,     │   │ schemas: identity,     │
                    │ webhooks → /webhooks/ │   │          billing       │
                    └───────────────────────┘   └────────────────────────┘
                                                            ▲
┌─────────────────────────────────────────────────┐         │ POST /v1/licence
│ Installed desktop app (backend/ + desktop/)     │         │ GET  /.well-known/jwks.json
│  Electron ─▶ Flask on 127.0.0.1:<random port>   ├─────────┘
│  app/services/licensing/  verifies the token    │  (activation, then ~weekly refresh)
│  offline against a baked-in public key          │
└─────────────────────────────────────────────────┘
```

The marketing site and the desktop app still share no code. They now share two
things instead of one: `version.json` (unchanged) and this API.

---

## 4. Commercial model

Three purchasable plans, all resolving to the same `pro` tier:

| Plan id | Stripe mode | Price (proposed) | Notes |
|---|---|---|---|
| `pro_monthly` | `subscription` | $4.99 / month | Cancel anytime via Portal |
| `pro_annual` | `subscription` | $39 / year | ~35% discount, the default CTA |
| `lifetime` | `payment` | $79 one-time | Perpetual, all future versions |

**Lifetime means perpetual, including updates.** The alternative ("updates for 12
months, then the app freezes") is common in desktop software and universally
resented; with a ~$79 price point and no per-user marginal cost, it buys goodwill
worth more than the upgrade revenue.

### 4.1 What free gets vs. Pro — proposal, needs a product decision

The app has **no marginal cost per prediction** (the user brings Ollama or their
own API key), so a usage cap would be arbitrary rather than cost-driven. Gate on
depth and convenience instead:

| | Free | Pro |
|---|---|---|
| Local AI (Ollama) | ✅ unlimited | ✅ unlimited |
| Cloud providers (OpenAI/Gemini/Deepseek/Claude) | 1 configured provider | All four, switchable |
| Betting pages | PrizePicks only | PrizePicks + DraftKings + Kalshi |
| Kalshi free-text market questions | — | ✅ |
| Chat | ✅ | ✅ |
| Prediction history | Last 20 | Unlimited + CSV export |
| Fighter DB sync | ✅ | ✅ |

Rationale: fully-local operation stays free, which keeps the privacy story and
the "no account needed to try it" onramp intact. **Flagging this as the weakest
part of the plan** — it is a pricing decision, not an engineering one, and the
whole feature's revenue depends on it more than on anything else in this document.

### 4.2 Blocker before any code: Stripe account approval

Stripe's restricted-business list covers gambling and, in places,
gambling-adjacent services. This product generates betting-prop predictions —
it does not accept wagers or handle stakes, and the in-app disclaimer says so,
but that is a judgement call Stripe makes, not us. **Open a Stripe account and
get the business description approved before Phase 1**, because a rejection
invalidates §7 entirely and pushes the design toward a merchant-of-record
(Paddle / Lemon Squeezy) instead. Cost of checking first: one afternoon. Cost of
checking last: the whole billing module.

---

## 5. Service design

```
accounts/
  pom.xml                        Java 21, Spring Boot 3.5, one module (see §5.1)
  Dockerfile                     eclipse-temurin:21-jre, non-root, layered jar
  src/main/java/com/mmaassist/accounts/
    AccountsApplication.java
    identity/                    accounts, OAuth login, sessions, devices
      web/          AuthController, AccountController, DeviceController
      domain/       Account, Identity, Device, Session
      service/      OAuthLoginService, SessionService, AccountLinkingService
    billing/                     Stripe: checkout, webhooks, ledger
      web/          CheckoutController, PortalController, StripeWebhookController
      domain/       Customer, Plan, Subscription, Purchase, Payment, StripeEvent
      service/      CheckoutService, WebhookIngestService, WebhookProcessor,
                    EntitlementCalculator, ReconciliationJob
    licensing/                   the token the desktop app verifies
      web/          LicenceController, JwksController
      service/      LicenceTokenSigner, KeyRotationService
    platform/                    shared: config, error handling, rate limits, audit
  src/main/resources/
    db/migration/                V1__identity.sql, V2__billing.sql, ...
    application.yml
  src/test/                      unit + Testcontainers integration + contract tests
```

### 5.1 One deployable, three modules — and why not three services

Three separate microservices would need distributed transactions across
"payment succeeded" → "entitlement granted" → "token issued", which is the exact
consistency problem that a single Postgres transaction solves for free. For a
system with one team, one database, and single-digit requests per second, the
network boundary buys nothing and costs correctness.

What the module split *does* buy is a seam that stays honest, enforced in CI:

- Packages talk through service interfaces, never each other's repositories.
- `billing` may read `identity.accounts` by id; `identity` may not import `billing`.
- ArchUnit tests fail the build on a violation.

If any module ever needs to scale or deploy independently, it lifts out along an
already-tested boundary. Splitting later is cheap; unwinding a distributed
transaction is not.

---

## 6. Identity: accounts, and where they live

### 6.1 Storage — PostgreSQL, schema `identity`

```sql
-- V1__identity.sql
create extension if not exists citext;
create extension if not exists pgcrypto;
create schema identity;

create table identity.accounts (
  id             uuid primary key default gen_random_uuid(),
  email          citext      not null unique,   -- always a VERIFIED address (§6.3)
  display_name   text,
  avatar_url     text,
  status         text        not null default 'active'
                 check (status in ('active','suspended','deleted')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  deleted_at     timestamptz
);

-- One row per linked identity provider. An account may have both.
create table identity.identities (
  id                uuid primary key default gen_random_uuid(),
  account_id        uuid        not null references identity.accounts(id) on delete cascade,
  provider          text        not null check (provider in ('google','github')),
  provider_user_id  text        not null,      -- Google `sub` / GitHub numeric id.
                                               -- NEVER the email: emails change hands.
  email_at_link     citext,
  created_at        timestamptz not null default now(),
  last_login_at     timestamptz,
  unique (provider, provider_user_id)
);

-- Browser sessions. Opaque id in a cookie; only its hash is stored, so a
-- database leak does not hand out live sessions.
create table identity.sessions (
  id           uuid primary key default gen_random_uuid(),
  account_id   uuid        not null references identity.accounts(id) on delete cascade,
  token_hash   bytea       not null unique,     -- sha256(random 256-bit token)
  user_agent   text,
  ip           inet,
  created_at   timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at   timestamptz not null,            -- 30 days, sliding
  revoked_at   timestamptz
);

-- Desktop installs. See §6.5 on why this is per-install, not per-machine.
create table identity.devices (
  id            uuid primary key default gen_random_uuid(),
  account_id    uuid        not null references identity.accounts(id) on delete cascade,
  install_id    text        not null,           -- random uuid generated by the app
  name          text,                           -- "DESKTOP-4F2K · Windows 11"
  app_version   text,
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz not null default now(),
  revoked_at    timestamptz,
  unique (account_id, install_id)
);

-- Rotating refresh tokens for desktop clients (browsers use sessions above).
create table identity.refresh_tokens (
  id          uuid primary key default gen_random_uuid(),
  account_id  uuid        not null references identity.accounts(id) on delete cascade,
  device_id   uuid        references identity.devices(id) on delete cascade,
  token_hash  bytea       not null unique,
  family_id   uuid        not null,             -- rotation family, for reuse detection
  issued_at   timestamptz not null default now(),
  expires_at  timestamptz not null,
  revoked_at  timestamptz,
  replaced_by uuid        references identity.refresh_tokens(id)
);
```

**Where accounts live, stated plainly**: one managed PostgreSQL instance, in the
`identity` schema, co-located with billing data in the same database and the same
transaction boundary. Not in Stripe (Stripe's customer object is a mirror, not the
record of truth), not in the desktop app's SQLite (that file is portable, per-install
and user-editable), and not in a third-party auth provider (Auth0/Clerk/Firebase —
they solve a password problem we don't have, since the IdPs handle credentials).

### 6.2 Web login flow

```
1. Site → GET  api/v1/auth/{google|github}/start?redirect=/account
              → 302 to the IdP, with state + PKCE stored server-side (5 min TTL)
2. IdP  → GET  api/v1/auth/{provider}/callback?code&state
              → validate state, exchange code, fetch profile
              → resolve account (§6.3), create session row
              → Set-Cookie: mma_session=<opaque>; HttpOnly; Secure;
                            SameSite=Lax; Domain=.mmaassist.com; Max-Age=30d
              → 302 back to the site path from step 1
3. Site → GET  api/v1/me  (credentials: 'include') → account + entitlement
```

`SameSite=Lax` works because `api.mmaassist.com` and `mmaassist.com` share a
registrable domain — they are same-site. **This constrains deployment**: if the API
ends up on a Railway-generated hostname on a different domain, the cookie must
become `SameSite=None` (still `Secure`, still HttpOnly), which is functional but
gives up the CSRF defence. Buy the domain and put the API on a subdomain of it.

CORS: exactly one allowed origin (the site), `allowCredentials=true`, no wildcard.

### 6.3 Resolving an identity to an account — the linking rule

```
lookup identities by (provider, provider_user_id)
  found     → that account. Update last_login_at. Done.
  not found → look up accounts by the provider's VERIFIED email
      found     → link: insert an identities row against the existing account
      not found → create account + identity
```

**GitHub is the trap.** It is OAuth2, not OIDC: there is no `email` claim. You must
request the `user:email` scope and call `GET /user/emails`, then take the entry with
`primary: true` **and** `verified: true`. If no verified primary email exists, refuse
the login with a clear message rather than falling back to the public profile email.

Linking on an unverified email is account takeover: anyone who can set an
unverified address to `victim@example.com` inherits their Pro licence and payment
history. Google's `email_verified` claim must be checked for the same reason —
it is `false` for some Workspace configurations.

### 6.4 Desktop login flow (RFC 8252 loopback + PKCE)

The Flask app already binds a random localhost port (`SPEC.md` §2.2), so it can
receive the redirect directly — no polling, no copy-pasted codes.

```
1. App   generates code_verifier + install_id, starts a one-shot handler at
         http://127.0.0.1:<port>/account/callback
2. App   opens the SYSTEM browser (not an embedded webview — embedded views are
         blocked by Google for OAuth and are indistinguishable from phishing):
         https://api.mmaassist.com/v1/auth/desktop/start
           ?code_challenge=…&code_challenge_method=S256
           &redirect_uri=http://127.0.0.1:<port>/account/callback&state=…
3. User  signs in with Google/GitHub in a browser they already trust
4. API   302 → the loopback URI with ?code=…&state=…
5. App   POST /v1/auth/desktop/token {code, code_verifier, install_id, app_version}
         → { access_token (opaque, 15 min), refresh_token (opaque, 90 d),
             account_id, device_id }
6. App   POST /v1/licence with that access token → the licence token (§8)
7. App   stores refresh + licence token in the data dir; shows the account panel
```

`redirect_uri` is validated against `^http://127\.0\.0\.1:\d{1,5}/account/callback$`
— loopback only, no wildcards, and never `localhost` (which can resolve to a
non-loopback interface on misconfigured machines).

### 6.5 Device identity is per-install, not per-machine

`install_id` is a random UUID the app generates once and stores in its data
directory — deliberately **not** a hardware fingerprint. The app is portable
(`SPEC.md` §13.1): the same install runs from a USB stick on three different
machines, and a hardware id would burn a fresh activation on each. Copying the
data folder clones the id, which is fine — the activation limit is a courtesy
cap, not a security control (§1.1).

Cap: **5 active devices** per account, with self-service revocation on `/account`.
Exceeding it returns a `device_limit_exceeded` error naming the devices, not a
silent failure.

---

## 7. Payments

### 7.1 What we never store

Card numbers, CVCs, expiry dates, and raw bank details never reach this service.
Stripe Checkout is a redirect to Stripe's own domain; our servers see only object
ids and the display fields Stripe returns. That keeps the integration at **PCI
SAQ A**, the lightest self-assessment tier, and it is the single most valuable
property of this design — protect it. Do not "simplify" later by adding Stripe
Elements to our own page, which moves us to SAQ A-EP and puts our JavaScript in
scope.

Safe to store, and useful for support: `card_brand`, `card_last4`, `receipt_url`,
Stripe object ids, amounts, currency, status.

### 7.2 Storage — schema `billing`

```sql
-- V2__billing.sql
create schema billing;

-- Plan catalogue. The site reads this, so prices are never hardcoded in React
-- and a price change is one row, not a redeploy.
create table billing.plans (
  id              text primary key,             -- 'pro_monthly' | 'pro_annual' | 'lifetime'
  stripe_price_id text        not null unique,
  kind            text        not null check (kind in ('subscription','one_time')),
  interval        text        check (interval in ('month','year')),
  amount_minor    integer     not null,         -- cents. NEVER a float.
  currency        text        not null default 'usd',
  features        jsonb       not null default '{}',
  display_name    text        not null,
  sort_order      integer     not null default 0,
  active          boolean     not null default true,
  check ((kind = 'subscription') = (interval is not null))
);

create table billing.customers (
  account_id         uuid primary key references identity.accounts(id) on delete restrict,
  stripe_customer_id text not null unique,
  created_at         timestamptz not null default now()
);
-- on delete RESTRICT, not cascade: financial records must outlive an account
-- deletion request. §10.3 covers how erasure works without dropping them.

create table billing.subscriptions (
  id                     uuid primary key default gen_random_uuid(),
  account_id             uuid        not null references identity.accounts(id),
  stripe_subscription_id text        not null unique,
  plan_id                text        not null references billing.plans(id),
  status                 text        not null,   -- Stripe's vocabulary, stored verbatim:
                                                 -- trialing|active|past_due|canceled|
                                                 -- unpaid|incomplete|incomplete_expired
  current_period_end     timestamptz,
  cancel_at_period_end   boolean     not null default false,
  canceled_at            timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);
create index on billing.subscriptions (account_id);

create table billing.purchases (                 -- one-time lifetime licences
  id                          uuid primary key default gen_random_uuid(),
  account_id                  uuid        not null references identity.accounts(id),
  stripe_payment_intent_id    text        not null unique,
  stripe_checkout_session_id  text        unique,
  plan_id                     text        not null references billing.plans(id),
  amount_minor                integer     not null,
  currency                    text        not null,
  status                      text        not null,  -- succeeded|refunded|
                                                     -- partially_refunded|disputed
  purchased_at                timestamptz not null,
  refunded_at                 timestamptz
);

-- Every money movement, subscription invoices and one-offs alike. This is the
-- table you reconcile against Stripe and the one support reads from.
create table billing.payments (
  id               uuid primary key default gen_random_uuid(),
  account_id       uuid        references identity.accounts(id),
  stripe_object_id text        not null unique,  -- in_… | pi_… | re_… | dp_…
  kind             text        not null check (kind in
                     ('invoice','payment_intent','refund','dispute')),
  amount_minor     integer     not null,         -- negative for refunds
  currency         text        not null,
  status           text        not null,
  card_brand       text,
  card_last4       char(4),
  receipt_url      text,
  occurred_at      timestamptz not null,
  raw              jsonb                          -- trimmed Stripe object, for support
);
create index on billing.payments (account_id, occurred_at desc);

-- The webhook log IS the idempotency mechanism: Stripe's event id as primary
-- key means a duplicate delivery fails the insert instead of double-granting.
create table billing.stripe_events (
  id           text primary key,                  -- evt_…
  type         text        not null,
  api_version  text,
  payload      jsonb       not null,
  received_at  timestamptz not null default now(),
  processed_at timestamptz,
  attempts     integer     not null default 0,
  last_error   text
);
create index on billing.stripe_events (processed_at) where processed_at is null;

-- The computed answer to "what does this account get?" — recomputed inside the
-- same transaction as any billing change. The app and the site read only this.
create table billing.entitlements (
  account_id  uuid primary key references identity.accounts(id) on delete cascade,
  tier        text        not null default 'free' check (tier in ('free','pro')),
  source      text        check (source in ('subscription','lifetime','grant')),
  features    jsonb       not null default '{}',
  valid_until timestamptz,                        -- null = perpetual (lifetime/grant)
  updated_at  timestamptz not null default now()
);

create table billing.audit_log (
  id         bigserial primary key,
  account_id uuid,
  actor      text        not null,                -- 'system' | 'stripe' | admin email
  action     text        not null,
  detail     jsonb,
  at         timestamptz not null default now()
);
```

Money is `integer` minor units throughout. A `float` price is a bug waiting for
a rounding edge case, and `numeric` invites arithmetic in the wrong currency.

### 7.3 Purchase flow

```
Site                    API                         Stripe
 │ POST /v1/checkout ────▶│
 │   {plan_id}            │ verify session cookie
 │                        │ ensure billing.customers row (create Customer if new,
 │                        │   idempotency_key = "cust:"+account_id)
 │                        │ Checkout Session:
 │                        │   mode = subscription | payment   (from plans.kind)
 │                        │   client_reference_id = account_id
 │                        │   metadata = {account_id, plan_id}
 │                        │   automatic_tax = on, customer_update.address = auto
 │                        │   success_url = site/checkout/success?s={CHECKOUT_SESSION_ID}
 │                        │   cancel_url  = site/pricing
 │                        │──────────────────────────▶│
 │◀── {checkout_url} ─────│◀── cs_… ──────────────────│
 │ window.location = checkout_url                     │
 │                          user pays on Stripe's domain (SCA/3DS handled there)
 │                        │◀── POST /webhooks/stripe ─│  checkout.session.completed
 │                        │    verify signature, insert stripe_events, ACK 200
 │                        │    (async) process → subscription/purchase row
 │                        │             → recompute entitlement  ── one transaction
 │◀── redirect to success_url
 │ GET /v1/me → poll up to ~10s for tier=pro, then show "You're Pro"
```

**The success page must not be the thing that grants access.** It is a redirect the
user's browser can lose (closed tab, dead battery, aggressive extension). Only the
webhook grants. The success page polls `/v1/me` and, if the entitlement hasn't
landed within ~10 seconds, says "payment received, activating…" rather than
implying failure — Stripe webhook delivery is typically sub-second but not
guaranteed to be.

### 7.4 Entitlement calculation — one function, one source of truth

```
computeEntitlement(accountId):
    if exists purchase(plan=lifetime, status='succeeded') and not refunded
        → tier=pro, source=lifetime, valid_until=null
    else if exists subscription with status in ('active','trialing')
        → tier=pro, source=subscription, valid_until=current_period_end
    else if exists subscription with status='past_due'
        → tier=pro, valid_until=current_period_end + DUNNING_GRACE (7 days)
    else
        → tier=free, source=null, valid_until=null
```

Called after **every** webhook, every reconciliation pass, and every manual grant,
always inside the same transaction as the change that triggered it. Never inferred
at read time from subscription rows scattered around the codebase — that is how two
code paths end up disagreeing about whether someone is Pro.

The 7-day `past_due` grace exists because a failed renewal is usually an expired
card, not a lapsed customer. Stripe's Smart Retries run for ~2 weeks; cutting
access on day one turns a card update into a support ticket and a refund request.

### 7.5 Webhook pipeline

`POST /webhooks/stripe` — the only unauthenticated write endpoint in the service,
so it gets the most scrutiny.

1. **Read the raw body as a `String`.** Jackson deserialisation before signature
   verification breaks the HMAC (whitespace and key order change). Take
   `@RequestBody String payload` and hand it to `Webhook.constructEvent(payload,
   sigHeader, endpointSecret)`.
2. **Verify or reject with 400.** Signature failure is never retried, never logged
   with the payload body.
3. **Insert into `stripe_events` and return 200 immediately.** A primary-key
   conflict means a duplicate delivery: return 200, do nothing. Stripe times out
   at 10 seconds and retries for 3 days — never do the work inline.
4. **Process asynchronously** (a `@Scheduled` poller over `processed_at is null`,
   with `select … for update skip locked`). Increment `attempts`, record
   `last_error`, exponential backoff, alert after 5 failures. The raw payload is
   retained, so any bug is replayable rather than a lost payment.

Events handled:

| Event | Effect |
|---|---|
| `checkout.session.completed` | Link `client_reference_id` → account. `mode=payment` → `purchases` row; `mode=subscription` → wait for the subscription events (the session alone doesn't carry final status) |
| `customer.subscription.created/updated/deleted` | Upsert `subscriptions`, including plan changes and `cancel_at_period_end` |
| `invoice.paid` | `payments` row; extend `current_period_end` |
| `invoice.payment_failed` | Mark `past_due`; email the user with a Portal link |
| `charge.refunded` | Negative `payments` row; mark purchase refunded → **revokes** entitlement |
| `charge.dispute.created` | Flag account, alert, suspend entitlement pending resolution |

Every branch ends with `computeEntitlement`. Out-of-order delivery is expected:
compare Stripe's object timestamps and ignore stale updates rather than assuming
arrival order.

### 7.6 Reconciliation — because webhooks are best-effort

A nightly job pages Stripe's subscription and charge lists for the last 48 hours
and diffs them against our tables. Discrepancies are repaired and **alerted** — a
silent repair hides a broken webhook endpoint, which is the actual bug. This is
also the recovery path after an outage: Stripe gives up retrying after 3 days.

### 7.7 Refunds, cancellations, disputes

- **Cancellation** is entirely the Billing Portal's job — `cancel_at_period_end`,
  access until the period ends. No custom UI.
- **Refunds** are issued from the Stripe Dashboard; `charge.refunded` propagates
  to us. Publish a plain refund policy (proposal: 14 days, no questions asked —
  cheaper than chargebacks, which cost the amount *plus* a $15 fee).
- **Disputes** suspend the entitlement and alert. Do not automate a response.

---

## 8. Licensing: the token the desktop app checks

### 8.1 Format

An Ed25519 (EdDSA) JWT. Ed25519 over RSA for size and because a 32-byte public
key is easy to bake into a PyInstaller bundle; asymmetric over HMAC because the
app must verify without holding a secret it would ship to every user.

```json
{
  "iss": "https://api.mmaassist.com",
  "sub": "9f1c…",                       // account id
  "aud": "mma-assist-desktop",
  "jti": "…",                            // revocation handle
  "iat": 1786300000,
  "exp": 1787509600,                     // sub: +14d · lifetime: +180d
  "tier": "pro",
  "features": { "cloud_providers": true, "all_platforms": true,
                "kalshi_market": true, "unlimited_history": true },
  "device": "…",                         // devices.id
  "grace_days": 7,
  "email": "user@example.com"            // display only, never trusted for auth
}
```

Header carries `kid`; public keys are served at `/.well-known/jwks.json` so keys
rotate without a client release. The app pins the current key at build time and
falls back to JWKS when it meets an unknown `kid`.

### 8.2 Offline behaviour — the part that matters most

```
on startup, and every 24h:
    read cached token from the data dir
    verify signature (offline) and exp
        valid            → apply features. If exp - now < 3 days, refresh in the
                           background; failure to refresh is silent
        expired ≤ grace  → apply features, show "couldn't reach the licence
                           server, N days left"
        expired > grace  → drop to free tier, non-blocking banner with a Retry
        absent/invalid   → free tier
```

Non-negotiable: **the licence check never blocks startup and never blocks a
prediction.** `SPEC.md` §6.1 already made this mistake once with the AI-provider
status chip and fixed it by moving the check off the render path — the same
discipline applies here. A licence server outage must degrade to "Pro keeps
working", never to "the app hangs".

Effective offline window: 14-day subscription token + 7-day grace = 21 days
without contact; a lifetime token gives ~6 months. Long enough that a laptop
in a hotel with bad wifi is never affected.

### 8.3 Revocation

Short expiry is the primary mechanism — a refunded subscription simply stops
refreshing. `POST /v1/licence/refresh` checks `entitlement_tokens.revoked_at`
for immediate revocation of a specific device (user clicks "sign out this
device"). No CRL is pushed to clients; there is nothing worth the complexity
(§1.1).

---

## 9. API surface

Base `https://api.mmaassist.com/v1`. Browser calls authenticate with the session
cookie; desktop calls with `Authorization: Bearer <access token>`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/auth/{provider}/start` | — | Begin web OAuth; 302 to the IdP |
| GET | `/auth/{provider}/callback` | — | Exchange code, set session cookie, 302 back to the site |
| GET | `/auth/desktop/start` | — | Begin desktop OAuth (PKCE + loopback redirect) |
| POST | `/auth/desktop/token` | — | Exchange code + verifier → access, refresh, licence tokens |
| POST | `/auth/refresh` | refresh | Rotate refresh token; reuse of an old one revokes the family |
| POST | `/auth/logout` | session | Revoke the current session |
| GET | `/me` | session/bearer | `{account, entitlement, devices[], subscription?}` |
| DELETE | `/me` | session | Account deletion (§10.3) |
| GET | `/me/export` | session | GDPR data export (JSON) |
| GET | `/plans` | — | Public plan catalogue from `billing.plans` |
| POST | `/checkout` | session | `{plan_id}` → `{checkout_url}` |
| POST | `/portal` | session | → `{portal_url}` (Stripe Billing Portal) |
| GET | `/payments` | session | Invoice/receipt history for `/account` |
| POST | `/licence` | bearer | Issue a licence token for `{install_id, app_version}` |
| POST | `/licence/refresh` | bearer | Re-issue against current entitlement |
| DELETE | `/devices/{id}` | session/bearer | Revoke a device |
| POST | `/webhooks/stripe` | signature | Stripe events (§7.5) |
| GET | `/.well-known/jwks.json` | — | Ed25519 public keys, `Cache-Control: max-age=3600` |
| GET | `/actuator/health` | — | Railway healthcheck |

Errors are RFC 9457 `application/problem+json` with a stable machine-readable
`type`, so the app can branch on `device_limit_exceeded` without parsing prose.

---

## 10. Security & compliance

### 10.1 Threat-driven checklist

| Risk | Control |
|---|---|
| Webhook forgery → free Pro | Stripe signature verification against the raw body; nothing else may grant an entitlement |
| Replayed webhook → double grant | Stripe event id as primary key |
| Account takeover via unverified email | Verified-email requirement on both providers (§6.3) |
| Stolen session cookie | HttpOnly, Secure, SameSite=Lax, 30-day sliding expiry, server-side revocation, one allowed CORS origin |
| Stolen desktop refresh token | Rotation with reuse detection: replaying a rotated token revokes the whole family |
| Licence-server outage locks users out | Offline verification + grace; the check never blocks (§8.2) |
| OAuth authorisation-code interception | PKCE S256, strict loopback `redirect_uri` allowlist, single-use 60-second codes |
| Enumeration / brute force | Bucket4j: 10/min per IP on auth, 5/min per account on checkout, 60/min on `/me` |
| Secrets in git | All keys from env vars; `.env` gitignored; Stripe restricted keys, live keys only in the Railway service |
| Signing-key compromise | `kid` + JWKS rotation without a client release; keys stored as env-var secrets, never in the DB |
| Log leakage | Never log tokens, cookies, full webhook payloads at INFO, or full email addresses at INFO |

### 10.2 Environment configuration

```
DATABASE_URL                  postgres://…                (Railway-injected)
SITE_ORIGIN                   https://mmaassist.com       (sole CORS origin)
STRIPE_SECRET_KEY             sk_live_…
STRIPE_WEBHOOK_SECRET         whsec_…
GOOGLE_CLIENT_ID/SECRET
GITHUB_CLIENT_ID/SECRET
LICENCE_SIGNING_KEY           base64 Ed25519 private key (current kid)
LICENCE_SIGNING_KID
SESSION_COOKIE_DOMAIN         .mmaassist.com
```

Test-mode Stripe keys and a local Postgres for development; `stripe listen
--forward-to localhost:8080/webhooks/stripe` for webhook testing, which is the
only sane way to develop this.

### 10.3 Data protection

- **Collected**: email, display name, avatar URL, IdP user id, session IP and
  user-agent, device name/version, payment records. **Never collected**: usage
  analytics, prediction content, chat history, API keys — all of which stay on the
  user's machine. That distinction is worth stating explicitly on the site, since
  it is most of the product's privacy claim and it survives this change.
- **Deletion** (`DELETE /me`): personal fields are anonymised in place
  (`email` → `deleted+<uuid>@invalid`, name/avatar nulled), sessions, devices and
  identities are deleted, `status='deleted'`. Payment records are **retained** —
  tax and anti-fraud law requires it (typically 7 years) and the `on delete
  restrict` on `billing.customers` enforces it structurally. The privacy policy
  must say this; "we delete everything" would be a false claim.
- Active subscriptions are cancelled at deletion; the user is told, and told that
  a lifetime licence dies with the account.
- Retention: `stripe_events` payloads pruned at 90 days (ids and status kept),
  sessions at expiry + 30 days, `audit_log` 2 years.

---

## 11. Desktop app changes (`backend/`, Python)

Small and deliberately contained:

```
app/services/licensing/
  __init__.py
  token.py         Ed25519 verification via `cryptography`; baked-in public key
                   + JWKS fallback; pure function, trivially unit-testable
  store.py         cached token + install_id in the data dir (§13.1 rules apply)
  client.py        POST /v1/licence{,/refresh}; short timeouts, never blocking
  entitlement.py   current tier/features, with grace handling (§8.2)
app/blueprints/account/
  routes.py        /account (panel), /account/signin, /account/callback (loopback),
                   /account/signout
```

- `requires_pro(feature)` decorator/helper for gated routes; the UI **shows**
  gated features with an upgrade prompt rather than hiding them, which converts
  better and avoids "where did the Kalshi tab go" support mail.
- Settings gets an Account panel: signed-in email, tier, renewal date, Manage
  Billing (opens the Portal in the system browser), Sign Out.
- New dependency: `cryptography` (already transitively present) — no new heavy
  packages, so the bundle size doesn't move.
- `app/config.py` gains `ACCOUNTS_API_URL` (env-overridable, same pattern as
  `UPDATE_MANIFEST_URL`).
- The licence file is per-data-directory, so a portable copy carries its
  activation to another machine — intentional (§6.5).

---

## 12. Website changes (`frontend/`)

- New routes: `/pricing`, `/login`, `/account`, `/checkout/success`,
  `/checkout/cancel`. All extensionless, so `server.js`'s SPA fallback already
  handles them — **no server changes needed**.
- `src/api/client.ts`: `fetch` wrapper with `credentials: 'include'`, problem+json
  error parsing, and a typed `/me` response.
- `/pricing` renders from `GET /v1/plans` — prices live in the database, not in
  JSX. The three plans use the existing `FeatureCard`/`Reveal` components.
- `/account`: plan and renewal date, Manage Billing, invoice list, device list
  with revoke, delete account.
- Download page keeps its free download prominent. The app is free to install and
  free to use locally; Pro is an upgrade inside it, not a paywall in front of it.
- Add a Content-Security-Policy header in `server.js` before shipping login UI.
- Legal pages: `/privacy`, `/terms`, `/refunds` — required by Stripe, and by law
  in most of the addressable market.

---

## 13. Testing

| Layer | Approach |
|---|---|
| Unit | `EntitlementCalculator` as a table-driven test over every combination of subscription status × lifetime × refund × grace boundary. This is the function that decides who paid — it deserves exhaustive coverage |
| Integration | Testcontainers Postgres, real Flyway migrations. No H2: it disagrees with Postgres on `citext`, `jsonb`, and `skip locked` |
| Stripe | `stripe-mock` for the API surface; webhook handling driven by **real captured event fixtures** (Stripe's own JSON), signed with a test secret. Include a duplicate delivery, an out-of-order pair, and a tampered signature |
| Auth | Full OAuth round trip against WireMock IdPs, including: GitHub with no verified email, Google with `email_verified=false`, `state` mismatch, replayed code |
| Contract | **Cross-language**: a Java test signs a token, a pytest fixture in `backend/tests/test_licensing.py` verifies it with the shipped public key. This is the one seam where a silent break costs every paying user their Pro access, and neither side's tests would catch it alone |
| Manual | Stripe test cards: success, `4000000000000341` (attaches but fails on charge), 3DS-required, and a dispute via the test dashboard |

CI: a GitHub Actions job running `mvn verify` alongside the existing pytest and
vitest jobs.

---

## 14. Deployment

A second Railway service from the same repo (Root Directory `accounts/`), plus
the Railway Postgres plugin. A `Dockerfile` rather than Nixpacks — explicit JDK
version, layered jar, non-root user, and the same build locally as in CI.

- Flyway migrates on boot; `/actuator/health` is the healthcheck (include a DB
  probe, exclude Stripe reachability — a Stripe blip must not restart the service).
- One Stripe webhook endpoint per environment, each with its own signing secret.
- Structured JSON logs; Micrometer metrics. Alert on: unprocessed
  `stripe_events` older than 5 minutes, reconciliation discrepancies, webhook
  signature failures, and 5xx rate.
- Running cost: Railway service + Postgres ≈ $10–25/month, plus Stripe's
  2.9% + $0.30. Fixed cost is dominated by the database — the service itself is
  near-idle at this traffic level.
- **Backups matter now.** Railway's managed Postgres backups must be verified by
  an actual restore before launch; this database holds the only record of who
  paid, and Stripe can rebuild the payments but not the account links.

---

## 15. Build order

Each phase is independently shippable and leaves the product working.

| Phase | Work | Est. |
|---|---|---|
| **0** | **Stripe business approval (§4.2)**, domain purchase, feature-split decision, legal pages drafted | 1–2 d, mostly waiting — start immediately |
| **1** | Service skeleton: Boot app, Dockerfile, Postgres + Flyway, health, CI job, Railway deploy of an empty-but-live service | 2 d |
| **2** | Identity: Google + GitHub OAuth, accounts/identities/sessions, `/me`, linking rules, `/login` + a stub `/account` on the site | 4 d |
| **3** | Billing: plan catalogue, Checkout, webhook pipeline, entitlements, Portal. End-to-end test-mode purchase | 5 d |
| **4** | Licensing: Ed25519 signing, `/licence`, JWKS, devices, cross-language contract test | 3 d |
| **5** | Desktop integration: `licensing/` + account blueprint, feature gates, Settings panel, offline-grace tests | 4 d |
| **6** | Site: `/pricing` from the API, full `/account`, success/cancel, CSP, legal pages live | 3 d |
| **7** | Hardening: reconciliation job, refunds/disputes, GDPR delete/export, rate limits, alerting, restore drill, live-mode switch | 3 d |

≈ **25 working days**. Phases 1–4 are the Java service; 5–6 touch existing code.

Ship order note: **do not enable live-mode Stripe keys until phase 7 is done.**
A payment taken before the reconciliation job and refund path exist is a support
problem with no tooling behind it.

---

## 16. Open questions & risks

1. **Stripe approval for a betting-adjacent product** (§4.2). The single biggest
   risk. Resolve in phase 0. Fallback: Paddle or Lemon Squeezy as merchant of
   record, which also removes the VAT question below, at a higher fee and with a
   less flexible API.
2. **The free/Pro split** (§4.1) is a proposal, not a decision. It determines
   whether any of this earns money.
3. **Sales tax / VAT.** As merchant of record with Stripe, registration
   thresholds are yours — EU VAT MOSS has a €0 threshold for digital goods sold
   to consumers. Stripe Tax computes and files, but the registrations are still
   yours to obtain.
4. **Price changes and grandfathering.** `plans` rows are immutable once
   referenced; a price change means a new row and a new Stripe price. Decide
   whether existing subscribers migrate.
5. **The app is unsigned** (`SPEC.md` §13.1). Asking for money while SmartScreen
   calls the download dangerous is a conversion problem that no amount of backend
   work fixes — code signing arguably outranks this entire feature commercially.
6. **Lifetime licence and long-run cost.** No marginal cost per user today, but a
   future hosted feature (server-side RAG, hosted inference) would be owed to
   lifetime holders forever. Word the lifetime terms around *the desktop app as
   it exists*, not "everything we ever build".
7. **Team accounts / multi-seat** — deliberately out of scope. The schema
   supports adding an `organisations` table later without migrating anything
   above.
8. **Email delivery.** Receipts come from Stripe, but dunning notices and
   account-deletion confirmations need a sender (Resend/Postmark). Unbudgeted
   above; roughly half a day in phase 7.

---

## 17. Implementation status

Written after building phases 1–6. This section is the difference between the
design above and the code that exists, so the two stop disagreeing silently.

### 17.1 What exists

| Phase | State |
|---|---|
| 0 — Stripe approval, domain, legal pages | **Not done.** Still the gating risk (§4.2) |
| 1 — Service skeleton, Postgres, Flyway, Docker, CI | Done. `accounts/`, five migrations, `Dockerfile`, `railway.json`, `.github/workflows/accounts.yml` |
| 2 — Identity: OAuth, accounts, sessions, devices | Done. Google + GitHub brokers, linking rules, web and desktop flows |
| 3 — Billing: plans, Checkout, webhooks, entitlements, Portal | Done, against placeholder Stripe price ids |
| 4 — Licensing: Ed25519, JWKS, devices, contract test | Done |
| 5 — Desktop integration | **Partly.** `backend/app/services/licensing/` (verify, evaluate, cache, client) exists and is tested. The Flask blueprint, Settings panel and feature gates are **not** written |
| 6 — Website | Done: `/pricing`, `/login`, `/account`, `/checkout/success`, API client |
| 7 — Hardening | **Not done.** Reconciliation exists but nothing alerts on it; no restore drill; no dunning email; live keys not configured |

**Tests: 126, of which 122 run without Docker.** 90 Java (4 Testcontainers
tests skip without a Docker daemon), 28 Python, 8 new frontend. The Java suite
covers the entitlement calculator exhaustively, webhook signature verification
against real HMACs, OAuth linking, refresh-token reuse detection, and the
open-redirect and loopback-URI guards.

One real bug was found by its own test while writing this: a webhook POST with
no `Stripe-Signature` header threw `NullPointerException` inside the Stripe SDK
and would have returned 500 instead of 400.

### 17.2 Where the code differs from the design above, and why

- **No Spring Security.** The auth surface is "opaque token → row → account",
  and the CSRF machinery that would justify the framework is unused: the
  session cookie is `SameSite=Lax`, which is the CSRF defence. Headers are set
  explicitly by `SecurityHeadersFilter`; endpoints declare their own
  requirement by taking an `AuthPrincipal` parameter. Revisit if this service
  ever grows roles or scopes.
- **No `citext`, no `inet`, no `jsonb`.** `create extension` needs superuser,
  which a managed Postgres does not guarantee, so case-insensitive email
  uniqueness is a `unique index on (lower(email))` instead. IPs are `text`.
  JSON columns are `text` because nothing queries inside them and the mapping
  could only be validated against a live database; promoting one later is a
  single `ALTER`.
- **One `sessions` table serves browsers and desktop apps**, distinguished by a
  `kind` column, rather than a separate access-token table. Both are "an opaque
  secret that maps to an account", and one lookup path means one place to get
  revocation and expiry right.
- **Desktop access tokens are opaque, not JWTs.** That leaves exactly one JWT
  in the system — the licence token — which Java only signs and Python only
  verifies. It also makes desktop revocation instant.
- **Four schemas, not two:** `platform` (audit), `identity`, `billing`,
  `licensing`. `licence_tokens` moved out of `billing` so the module named on
  the table is the module that owns it.
- **`/v1/auth/desktop/token` does not return a licence.** The app calls
  `/v1/licence` afterwards. Returning it inline would have made `identity`
  depend on `licensing`, which depends on `billing`, which depends on
  `identity` — a cycle. The extra round trip buys an acyclic module graph.
- **Two endpoints were added:** `GET /v1/auth/providers` (which sign-in buttons
  to render) and `GET /v1/billing/summary`. `/v1/me` returns account,
  entitlement, linked providers and devices — subscription detail lives on the
  billing endpoint rather than being folded in.
- **`plans.interval` is `billing_interval`**, because `interval` is a reserved
  word in PostgreSQL.
- **`subscriptions.source_event_at`** was added. Stripe does not order webhook
  deliveries, and without a timestamp to compare against, a retried `past_due`
  arriving after the `active` that resolved it would cut off a customer who has
  already paid.

### 17.3 What is deliberately still missing

- Everything in phase 0 and phase 7 above.
- The desktop app's Flask blueprint, Settings account panel, and the
  `requires_pro` feature gates. The verification half is done and tested; the
  UI half is not.
- Dunning email. Stripe sends receipts, but a failed-payment notice needs a
  sender (Resend or Postmark), which nothing here configures.
- Any live Stripe call. Every Stripe interaction in the test suite is against
  constructed fixtures, and no live or test-mode key has been used.
