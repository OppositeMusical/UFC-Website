"""Path helpers that work identically in dev and inside a PyInstaller freeze.

Templates/static files are bundled read-only inside the frozen app (or next
to source files in dev) and must be resolved with resource_path(). Anything
the app *writes* (DB, Chroma dir, secrets) must go through
Config.data_dir()/related helpers in app/config.py instead - never through
resource_path(), since the bundle/install directory may be read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Root of the `app` package, whether running from source or frozen."""
    if is_frozen():
        # PyInstaller extracts bundled `datas` under sys._MEIPASS; app.spec
        # places the `app` folder's contents at "app/" inside the bundle.
        return Path(getattr(sys, "_MEIPASS")) / "app"
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)
