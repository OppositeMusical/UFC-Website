# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the UFC Predictor desktop app.

Build (from backend/): `pyinstaller pyinstaller/app.spec`
Produces dist/UFCPredictor/ (onedir, not onefile - see docs/SPEC.md section
2 "Packaging" for why onedir was chosen: onefile re-extracts 150-300MB to a
temp dir on every launch and trips more antivirus heuristics).

MANDATORY pre-build step (not automated here): ChromaDB's bundled embedding
function downloads a ~80MB ONNX model to a local cache directory
(~/.cache/chroma/onnx_models/...) the first time it's used. Run the app
once with internet access before building so that download has already
happened, then confirm app/utils/paths.py's first-run bootstrap (documented
in docs/SPEC.md) can find/restore it in the packaged environment - otherwise
RAG silently has nothing to embed against on an offline install.
"""
import os

from PyInstaller.utils.hooks import collect_all

BACKEND_DIR = os.path.join(SPECPATH, "..")  # noqa: F821 - SPECPATH is injected by PyInstaller

datas = [
    (os.path.join(BACKEND_DIR, "app", "templates"), os.path.join("app", "templates")),
    (os.path.join(BACKEND_DIR, "app", "static"), os.path.join("app", "static")),
    # Pre-scraped fighter database, baked by scripts/build_seed_data.py, so
    # a fresh install isn't empty - see app/utils/seed.py and
    # docs/SPEC.md section 11. This directory must exist (even if only the
    # placeholder README) before running PyInstaller.
    (os.path.join(BACKEND_DIR, "app", "seed_data"), os.path.join("app", "seed_data")),
]
binaries = []
hiddenimports = [
    # keyring's backend auto-discovery relies on importlib.metadata entry
    # points, which aren't reliably preserved in a frozen build - the app
    # already imports this explicitly at runtime (see
    # app/services/secrets/keyring_store.py), but list it here too as a
    # belt-and-suspenders hint to PyInstaller's static analysis.
    "keyring.backends.Windows",
]

# chromadb pulls in onnxruntime and tokenizers via dynamic imports that
# static analysis alone won't catch - collect_all is the documented fix.
for pkg in ("chromadb", "onnxruntime", "tokenizers"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [os.path.join(BACKEND_DIR, "run.py")],
    pathex=[BACKEND_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UFCPredictor",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="UFCPredictor",
)
