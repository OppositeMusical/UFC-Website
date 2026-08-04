"""Shared SQLAlchemy plumbing.

Plain SQLAlchemy (not the Flask-SQLAlchemy extension) is used deliberately:
the fighter-sync scraper runs in a background thread outside any Flask
request context, and Flask-SQLAlchemy's session scoping assumes a request
context. A `scoped_session` keyed by thread id works cleanly for both the
request-handling threads and the background scraper thread.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
Session = scoped_session(sessionmaker())


def init_engine(database_uri: str, echo: bool = False):
    """(Re)configure the module-level engine and session factory.

    Called once from the app factory (and again per-test with a fresh
    in-memory/tmp database), so it must be idempotent.
    """
    global engine
    engine = create_engine(database_uri, echo=echo, future=True)
    Session.remove()
    Session.configure(bind=engine)
    return engine
