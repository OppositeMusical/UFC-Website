-- Platform-wide tables. Kept in their own schema so the `platform` Java module
-- never has to import from `identity` or `billing` to write an audit record.
create schema if not exists platform;

create table platform.audit_log (
    id         bigserial   primary key,
    account_id uuid,                              -- deliberately NOT a foreign key:
                                                  -- the audit trail must survive
                                                  -- account deletion (see V3 notes)
    actor      text        not null,              -- 'system' | 'stripe' | admin email
    action     text        not null,
    detail     text,                              -- JSON, see README "why text not jsonb"
    at         timestamptz not null default now()
);

create index audit_log_account_idx on platform.audit_log (account_id, at desc);
create index audit_log_action_idx  on platform.audit_log (action, at desc);
