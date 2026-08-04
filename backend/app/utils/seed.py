"""First-run seed-data bootstrap.

The packaged app ships with a pre-scraped SQLite database and ChromaDB
collection (app/seed_data/, bundled via PyInstaller's `datas` - see
pyinstaller/app.spec) so a fresh install already has real UFC fighter stats
instead of an empty database the user has to wait hours to populate via a
live scrape. Users can still get current data anytime via
Settings -> Sync Now; this only removes the *initial* wait, not the need to
occasionally refresh.

This must run before app.extensions.init_engine()/init_db() ever touch the
sqlite file - once SQLAlchemy has created an empty (but non-zero-byte) db
file, the "is data already present" check below would see a file and skip
seeding.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import Config
from app.utils.paths import resource_path

logger = logging.getLogger(__name__)

SEED_DB_FILENAME = "ufc_predictor.seed.db"
SEED_CHROMA_DIRNAME = "chroma_db"


def maybe_seed_data_dir() -> None:
    """Copies bundled seed data into the user's app data directory if (and
    only if) that directory doesn't already have real data. Never
    overwrites an existing install - safe to call on every startup.
    """
    _maybe_seed_sqlite()
    _maybe_seed_chroma()


def _maybe_seed_sqlite() -> None:
    sqlite_path = Config.sqlite_path()
    if sqlite_path.exists() and sqlite_path.stat().st_size > 0:
        return  # an install already has a database - never overwrite it

    seed_db = resource_path("seed_data", SEED_DB_FILENAME)
    if not seed_db.exists():
        logger.info("no bundled seed database found at %s - starting empty", seed_db)
        return

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed_db, sqlite_path)
    logger.info("seeded %s from bundled %s", sqlite_path, seed_db)


def _maybe_seed_chroma() -> None:
    chroma_dir = Config.chroma_dir()  # side effect: creates the dir if missing
    if _dir_has_contents(chroma_dir):
        return  # an install already has vector data - never overwrite it

    seed_chroma = resource_path("seed_data", SEED_CHROMA_DIRNAME)
    if not seed_chroma.exists():
        logger.info("no bundled seed ChromaDB found at %s - starting empty", seed_chroma)
        return

    shutil.copytree(seed_chroma, chroma_dir, dirs_exist_ok=True)
    logger.info("seeded %s from bundled %s", chroma_dir, seed_chroma)


def _dir_has_contents(path: Path) -> bool:
    return path.exists() and any(path.iterdir())
