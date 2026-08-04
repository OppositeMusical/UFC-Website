#!/usr/bin/env python
"""CLI entry point for syncing the fighter database from ufc.com.

Usage:
    python scripts/scrape.py --roster-only
    python scripts/scrape.py --limit 50
    python scripts/scrape.py                 # full sync, resumable

Respects the site's stated 15s crawl-delay (see app/services/scraper/) - a
full sync of thousands of fighters is intentionally slow and safe to
interrupt and re-run.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.services.scraper import pipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync UFC fighter data from ufc.com")
    parser.add_argument("--limit", type=int, default=None, help="Max number of fighters to detail-scrape this run")
    parser.add_argument("--roster-only", action="store_true", help="Only sync the fighter roster (fast), skip detail pages")
    parser.add_argument("--no-resume", action="store_true", help="Re-scrape fighters even if already scraped")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=pipeline.DEFAULT_MAX_AGE_DAYS,
        help=(
            "In resume mode, also re-scrape fighters whose stats are older than this "
            f"many days (default: {pipeline.DEFAULT_MAX_AGE_DAYS}). Use 0 to only "
            "scrape fighters that have never been scraped."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    app = create_app()
    with app.app_context():
        print("Discovering fighters from ufc.com sitemap...")
        count = pipeline.sync_roster()
        print(f"Roster sync complete: {count} fighter slugs known.")

        if args.roster_only:
            return

        def progress(done: int, total: int) -> None:
            print(f"\rScraping fighter details: {done}/{total}", end="", flush=True)

        result = pipeline.scrape_details(
            limit=args.limit,
            resume=not args.no_resume,
            progress_callback=progress,
            max_age_days=args.max_age_days or None,
        )
        print()
        print(f"Done: {result['done']} scraped, {result['errors']} errors, {result['total']} attempted this run.")


if __name__ == "__main__":
    main()
