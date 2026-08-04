"""Database bootstrap: create tables on first run, track a schema_version
row for cheap additive upgrades between releases (no Alembic - this is a
single-user desktop app, migration tooling of that weight is unjustified).
"""
from __future__ import annotations

import datetime as dt

from app import models  # noqa: F401 - ensures all models are registered on Base
from app.extensions import Base, Session
from app.models.app_setting import (
    CURRENT_SCHEMA_VERSION,
    KEY_SCHEMA_VERSION,
    AppSetting,
)


def init_db() -> None:
    """Create any missing tables and ensure the schema_version row exists.

    Safe to call every app startup - `create_all` is a no-op for tables that
    already exist. Additive column changes between versions should be
    handled with small hand-written `ALTER TABLE` functions gated on the
    stored schema_version, added here as the schema evolves.
    """
    Base.metadata.create_all(bind=Session().get_bind())
    Session.remove()

    session = Session()
    try:
        row = session.query(AppSetting).filter_by(key=KEY_SCHEMA_VERSION).one_or_none()
        if row is None:
            session.add(
                AppSetting(
                    key=KEY_SCHEMA_VERSION,
                    value=CURRENT_SCHEMA_VERSION,
                    updated_at=dt.datetime.utcnow(),
                )
            )
            session.commit()
    finally:
        Session.remove()


# NOTE: neither helper below calls Session.remove(). `Session` is a
# thread-scoped session shared by everything running on the current thread,
# so tearing it down here would detach ORM objects the *caller* had already
# loaded - and callers can't see that happening. That bit the dashboard:
# `render_template(..., active_provider=get_setting(...), predictions=rows)`
# evaluates get_setting() before rendering, so the rows were detached by the
# time Jinja touched a lazy-loaded relationship (DetachedInstanceError).
# Request-scoped cleanup belongs to the teardown_appcontext handler in
# app/__init__.py; background threads clean up in their own finally blocks.
def get_setting(key: str, default: str | None = None) -> str | None:
    session = Session()
    row = session.query(AppSetting).filter_by(key=key).one_or_none()
    return row.value if row is not None else default


def set_setting(key: str, value: str) -> None:
    session = Session()
    row = session.query(AppSetting).filter_by(key=key).one_or_none()
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
        row.updated_at = dt.datetime.utcnow()
    session.commit()
