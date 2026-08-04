from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Config
from app.utils import seed as seed_module


@pytest.fixture()
def fake_seed_source(tmp_path, monkeypatch):
    """A fake bundled seed_data/ directory with a tiny db file and a
    ChromaDB-shaped directory, so the test never touches the real
    (multi-hundred-MB, still being baked) seed data.
    """
    source_dir = tmp_path / "fake_seed_data"
    source_dir.mkdir()
    (source_dir / seed_module.SEED_DB_FILENAME).write_bytes(b"fake sqlite bytes")
    chroma_source = source_dir / seed_module.SEED_CHROMA_DIRNAME
    chroma_source.mkdir()
    (chroma_source / "chroma.sqlite3").write_bytes(b"fake chroma bytes")

    def fake_resource_path(*parts: str) -> Path:
        assert parts[0] == "seed_data"
        return source_dir.joinpath(*parts[1:])

    monkeypatch.setattr(seed_module, "resource_path", fake_resource_path)
    return source_dir


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "app_data"
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(d))
    return d


def test_seeds_empty_install(fake_seed_source, data_dir):
    assert not Config.sqlite_path().exists()

    seed_module.maybe_seed_data_dir()

    assert Config.sqlite_path().read_bytes() == b"fake sqlite bytes"
    assert (Config.chroma_dir() / "chroma.sqlite3").read_bytes() == b"fake chroma bytes"


def test_never_overwrites_existing_database(fake_seed_source, data_dir):
    Config.sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    Config.sqlite_path().write_bytes(b"real user data - do not touch")

    seed_module.maybe_seed_data_dir()

    assert Config.sqlite_path().read_bytes() == b"real user data - do not touch"


def test_never_overwrites_existing_chroma_dir(fake_seed_source, data_dir):
    chroma_dir = Config.chroma_dir()
    (chroma_dir / "already_here.txt").write_bytes(b"real user vector data")

    seed_module.maybe_seed_data_dir()

    assert (chroma_dir / "already_here.txt").exists()
    assert not (chroma_dir / "chroma.sqlite3").exists()


def test_noop_when_no_bundled_seed_exists(data_dir, monkeypatch):
    def fake_resource_path(*parts: str) -> Path:
        return Path("/definitely/does/not/exist").joinpath(*parts)

    monkeypatch.setattr(seed_module, "resource_path", fake_resource_path)

    # Must not raise even though nothing exists to seed from.
    seed_module.maybe_seed_data_dir()

    assert not Config.sqlite_path().exists()
