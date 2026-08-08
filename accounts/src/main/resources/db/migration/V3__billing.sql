-- Payments.
--
-- Card numbers, CVCs and expiry dates never reach this service: Stripe Checkout
-- is a redirect to Stripe's own domain, and we only ever see object ids plus the
-- display fields Stripe hands back. Nothing in this schema may hold a PAN.
--
-- All amounts are integer minor units (cents). Never a float, which is one
-- rounding edge case away from a support ticket about a missing penny.
create schema if not exists billing;

-- Plan catalogue. The website renders prices from this table, so a price change
-- is one row rather than a frontend redeploy.
create table billing.plans (
    id              text        primary key,           -- 'pro_monthly' | 'pro_annual' | 'lifetime'
    stripe_price_id text        not null unique,
    kind            text        not null check (kind in ('subscription', 'one_time')),
    billing_interval text       check (billing_interval in ('month', 'year')),
    amount_minor    integer     not null check (amount_minor >= 0),
    currency        text        not null default 'usd',
    features        text        not null default '{}', -- JSON, see README
    display_name    text        not null,
    description     text,
    sort_order      integer     not null default 0,
    active          boolean     not null default true,
    -- a subscription has an interval and a one-off does not; enforced rather
    -- than left to application code, because the checkout mode is derived from it
    constraint plans_interval_matches_kind
        check ((kind = 'subscription') = (billing_interval is not null))
);

-- on delete restrict, not cascade: financial records must outlive an account
-- deletion request. Erasure anonymises the account row instead (AccountService).
create table billing.customers (
    account_id         uuid        primary key references identity.accounts (id) on delete restrict,
    stripe_customer_id text        not null unique,
    created_at         timestamptz not null default now()
);

create table billing.subscriptions (
    id                     uuid        primary key,
    account_id             uuid        not null references identity.accounts (id) on delete restrict,
    stripe_subscription_id text        not null unique,
    plan_id                text        not null references billing.plans (id),
    -- Stripe's own vocabulary, stored verbatim. Translating it into a local
    -- enum would mean guessing at statuses Stripe adds later.
    status                 text        not null,
    current_period_end     timestamptz,
    cancel_at_period_end   boolean     not null default false,
    canceled_at            timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now(),
    -- Stripe's timestamp on the object that produced this row. Webhook delivery
    -- is not ordered, so a stale update is detected by comparing against this.
    source_event_at        timestamptz
);

create index subscriptions_account_idx on billing.subscriptions (account_id);

create table billing.purchases (
    id                         uuid        primary key,
    account_id                 uuid        not null references identity.accounts (id) on delete restrict,
    stripe_payment_intent_id   text        not null unique,
    stripe_checkout_session_id text        unique,
    plan_id                    text        not null references billing.plans (id),
    amount_minor               integer     not null,
    currency                   text        not null,
    status                     text        not null
                               check (status in ('succeeded', 'refunded', 'partially_refunded', 'disputed')),
    purchased_at               timestamptz not null,
    refunded_at                timestamptz
);

create index purchases_account_idx on billing.purchases (account_id);

-- Every money movement, subscription invoices and one-offs alike. This is the
-- table the reconciliation job diffs against Stripe and the one support reads.
create table billing.payments (
    id               uuid        primary key,
    account_id       uuid        references identity.accounts (id) on delete restrict,
    stripe_object_id text        not null unique,   -- in_... | pi_... | re_... | dp_...
    kind             text        not null check (kind in ('invoice', 'payment_intent', 'refund', 'dispute')),
    amount_minor     integer     not null,          -- negative for refunds
    currency         text        not null,
    status           text        not null,
    card_brand       text,                          -- Stripe-supplied display fields:
    card_last4       char(4),                       -- safe to store, and support needs them
    receipt_url      text,
    occurred_at      timestamptz not null,
    raw              text                           -- trimmed Stripe object, JSON
);

create index payments_account_idx on billing.payments (account_id, occurred_at desc);

-- The webhook log IS the idempotency mechanism. Stripe's event id as the primary
-- key means a duplicate delivery loses the insert race instead of granting a
-- second licence.
create table billing.stripe_events (
    id           text        primary key,           -- evt_...
    type         text        not null,
    api_version  text,
    payload      text        not null,              -- raw body, replayable
    received_at  timestamptz not null default now(),
    processed_at timestamptz,
    attempts     integer     not null default 0,
    last_error   text
);

-- Partial index: the processing poller only ever asks for unprocessed rows, and
-- this keeps that query O(backlog) rather than O(all events ever received).
create index stripe_events_unprocessed_idx on billing.stripe_events (received_at)
    where processed_at is null;

-- The computed answer to "what does this account get?", recomputed inside the
-- same transaction as any billing change. The desktop app and the website read
-- only this table, so they can never disagree with each other.
create table billing.entitlements (
    account_id  uuid        primary key references identity.accounts (id) on delete cascade,
    tier        text        not null default 'free' check (tier in ('free', 'pro')),
    source      text        check (source in ('subscription', 'lifetime', 'grant')),
    features    text        not null default '{}',
    valid_until timestamptz,                        -- null = perpetual (lifetime or grant)
    updated_at  timestamptz not null default now()
);
