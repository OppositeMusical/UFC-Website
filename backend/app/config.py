"""Application configuration.

All writable app data (SQLite DB, ChromaDB persistent directory, the Fernet
fallback keyfile) lives under the OS-appropriate user data directory, never
next to the installed program files (which may be read-only once packaged).
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "UFCPredictor"


class Config:
    """Base configuration. Resolves paths lazily so tests can override
    UFC_PREDICTOR_DATA_DIR before the app factory runs.
    """

    TESTING = False

    @staticmethod
    def data_dir() -> Path:
        override = os.environ.get("UFC_PREDICTOR_DATA_DIR")
        base = Path(override) if override else Path(user_data_dir(APP_NAME, appauthor=False))
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def sqlite_path(cls) -> Path:
        return cls.data_dir() / "ufc_predictor.db"

    @classmethod
    def SQLALCHEMY_DATABASE_URI(cls) -> str:  # noqa: N802 - Flask-SQLAlchemy convention
        return f"sqlite:///{cls.sqlite_path()}"

    @classmethod
    def chroma_dir(cls) -> Path:
        path = cls.data_dir() / "chroma_db"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def fallback_secrets_path(cls) -> Path:
        return cls.data_dir() / ".secrets.enc"

    @classmethod
    def fallback_key_path(cls) -> Path:
        return cls.data_dir() / ".secrets.key"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_PORT = 8765
    UFC_BASE_URL = "https://www.ufc.com"
    UFC_CRAWL_DELAY_SECONDS = 15
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class TestConfig(Config):
    TESTING = True

    @staticmethod
    def data_dir() -> Path:
        override = os.environ.get("UFC_PREDICTOR_DATA_DIR")
        if not override:
            raise RuntimeError("TestConfig requires UFC_PREDICTOR_DATA_DIR to be set (use a tmp_path fixture)")
        base = Path(override)
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def SQLALCHEMY_DATABASE_URI(cls) -> str:  # noqa: N802
        # A real file under the tmp data dir, not true in-memory sqlite -
        # ":memory:" is a fresh empty DB per connection under the default
        # pool, which silently breaks scoped_session across threads/requests.
        return f"sqlite:///{cls.sqlite_path()}"
