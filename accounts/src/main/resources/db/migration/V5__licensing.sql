-- Issued licence tokens.
--
-- Its own schema rather than a corner of `billing`, so the module that owns the
-- table is the module named on it. Licensing reads entitlements and devices;
-- nothing reads back the other way.
create schema if not exists licensing;

create table licensing.licence_tokens (
    jti        uuid        primary key,
    account_id uuid        not null references identity.accounts (id) on delete cascade,
    device_id  uuid        references identity.devices (id) on delete cascade,
    issued_at  timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz
);

create index licence_tokens_device_idx  on licensing.licence_tokens (device_id);
create index licence_tokens_account_idx on licensing.licence_tokens (account_id);
