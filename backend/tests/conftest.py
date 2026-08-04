from __future__ import annotations

import pytest

from app import create_app
from app.config import TestConfig


@pytest.fixture()
def app(tmp_path, monkeypatch):
    data_dir = tmp_path / "ufc_predictor_data"
    monkeypatch.setenv("UFC_PREDICTOR_DATA_DIR", str(data_dir))
    application = create_app(TestConfig)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()
