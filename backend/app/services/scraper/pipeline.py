"""Orchestrates a fighter-database sync: roster discovery, then per-fighter
detail scraping, committing to SQLite and upserting to ChromaDB after each
fighter so an interrupted run loses at most one fighter's progress.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import or_

from app.extensions import Session
from app.models.fighter import Fighter
from app.models.scrape_checkpoint import ScrapeCheckpoint
from app.services.rag.ingest import upsert_fighter
from app.services.scraper.parser import parse_athlete_page
from app.services.scraper.sitemap import discover_athlete_slugs
from app.services.scraper.ufc_client import UfcClient

logger = logging.getLogger(__name__)

# How old a fighter's stats may get before a resume-mode sync re-fetches
# them. Fight stats only change when someone competes, so refreshing far
# more often than this just spends 15s-apart requests to rewrite identical
# rows; a full refresh of the whole roster takes ~28 hours.
DEFAULT_MAX_AGE_DAYS = 30


def sync_roster(client: UfcClient | None = None) -> int:
    """Discovers fighter slugs from the sitemap and upserts stub rows.
    Returns the number of slugs discovered.
    """
    client = client or UfcClient()
    slugs = discover_athlete_slugs(client)
    session = Session()
    try:
        now = dt.datetime.utcnow()
        for slug in slugs:
            fighter = session.query(Fighter).filter_by(ufc_slug=slug).one_or_none()
            if fighter is None:
                fighter = Fighter(ufc_slug=slug, name=slug.replace("-", " ").title())
                session.add(fighter)
            fighter.roster_synced_at = now
            checkpoint = session.query(ScrapeCheckpoint).filter_by(fighter_slug=slug).one_or_none()
            if checkpoint is None:
                session.add(ScrapeCheckpoint(fighter_slug=slug, status="pending"))
        session.commit()
        return len(slugs)
    finally:
        Session.remove()


def scrape_details(
    limit: int | None = None,
    resume: bool = True,
    client: UfcClient | None = None,
    progress_callback=None,
    max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
) -> dict:
    """Fetches and parses detail pages for fighters not yet scraped
    (or all of them if resume=False). Commits + upserts to Chroma per
    fighter. Returns a summary dict.

    In resume mode a fighter is picked up when it has never been scraped
    *or* its stats are older than `max_age_days`. Staleness matters because
    installs ship with a pre-scraped seed database (app/utils/seed.py):
    without it every seeded fighter would look "already done" forever and a
    user's periodic sync would only ever pick up debutants, leaving records
    and stats frozen at the date the seed was baked. Pass max_age_days=None
    to keep the old never-refresh behaviour.
    """
    client = client or UfcClient()
    session = Session()
    done = 0
    errors = 0
    try:
        query = session.query(Fighter)
        if resume:
            unscraped = Fighter.stats_scraped_at.is_(None)
            if max_age_days is None:
                query = query.filter(unscraped)
            else:
                cutoff = dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
                query = query.filter(or_(unscraped, Fighter.stats_scraped_at < cutoff))
            # Oldest data first, so an interrupted or limited run spends its
            # requests on the most out-of-date fighters. NULLs sort first in
            # SQLite, which puts never-scraped fighters at the front.
            query = query.order_by(Fighter.stats_scraped_at.asc())
        if limit:
            query = query.limit(limit)
        fighters = query.all()
        total = len(fighters)

        for fighter in fighters:
            checkpoint = (
                session.query(ScrapeCheckpoint).filter_by(fighter_slug=fighter.ufc_slug).one_or_none()
            )
            try:
                resp = client.get(f"/athlete/{fighter.ufc_slug}")
                if resp is None:
                    raise RuntimeError("no response")
                parsed = parse_athlete_page(resp.text, source_url=resp.url)
                for key, value in parsed.items():
                    if hasattr(fighter, key):
                        setattr(fighter, key, value)
                fighter.stats_scraped_at = dt.datetime.utcnow()
                if checkpoint is not None:
                    checkpoint.status = "done"
                    checkpoint.last_attempt_at = dt.datetime.utcnow()
                session.commit()
                upsert_fighter(fighter)
                done += 1
            except Exception:
                logger.exception("failed to scrape fighter %s", fighter.ufc_slug)
                session.rollback()
                if checkpoint is not None:
                    checkpoint.status = "error"
                    checkpoint.last_attempt_at = dt.datetime.utcnow()
                    session.commit()
                errors += 1
            if progress_callback:
                progress_callback(done + errors, total)
        return {"total": total, "done": done, "errors": errors}
    finally:
        Session.remove()
