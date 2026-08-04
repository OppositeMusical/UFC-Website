#!/usr/bin/env python
"""Bakes app/seed_data/ from a completed scrape, for bundling into the
packaged app so fresh installs start with real fighter data already loaded
instead of an empty database (see app/utils/seed.py and docs/SPEC.md
section 11).

Usage:
    python scripts/build_seed_data.py --source-data-dir /path/to/scraped/data

`--source-data-dir` is whatever UFC_PREDICTOR_DATA_DIR pointed at while
scripts/scrape.py ran - it must contain a completed `ufc_predictor.db` and
`chroma_db/`.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_DATA_DIR = BACKEND_DIR / "app" / "seed_data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bake app/seed_data/ from a completed fighter-data scrape")
    parser.add_argument(
        "--source-data-dir",
        required=True,
        help="Data directory containing a completed scrape (ufc_predictor.db + chroma_db/)",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_data_dir)
    source_db = source_dir / "ufc_predictor.db"
    source_chroma = source_dir / "chroma_db"

    if not source_db.exists():
        sys.exit(f"No database found at {source_db} - point --source-data-dir at a completed scrape")
    if not source_chroma.exists():
        sys.exit(f"No ChromaDB directory found at {source_chroma}")

    SEED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    dest_db = SEED_DATA_DIR / "ufc_predictor.seed.db"
    print(f"Copying {source_db} -> {dest_db}")
    shutil.copyfile(source_db, dest_db)

    dest_chroma = SEED_DATA_DIR / "chroma_db"
    if dest_chroma.exists():
        print(f"Removing old {dest_chroma}")
        shutil.rmtree(dest_chroma)
    print(f"Copying {source_chroma} -> {dest_chroma}")
    shutil.copytree(source_chroma, dest_chroma)

    db_size_mb = dest_db.stat().st_size / (1024 * 1024)
    chroma_size_mb = sum(f.stat().st_size for f in dest_chroma.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"Done. Seed DB: {db_size_mb:.1f} MB, Seed ChromaDB: {chroma_size_mb:.1f} MB")
    print("Rebuild the PyInstaller package to bundle the new seed data: pyinstaller pyinstaller/app.spec")


if __name__ == "__main__":
    main()
