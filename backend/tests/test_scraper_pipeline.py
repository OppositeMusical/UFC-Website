from __future__ import annotations

import datetime as dt
from pathlib import Path

import responses

from app.extensions import Session
from app.models.fighter import Fighter
from app.models.scrape_checkpoint import ScrapeCheckpoint
from app.services.scraper import pipeline
from app.services.scraper.ufc_client import UfcClient

FIXTURE = Path(__file__).parent / "fixtures" / "ufc_athlete_sample.html"

SITEMAP_INDEX = """<?xml version="1.0"?>
<sitemapindex><sitemap><loc>https://www.ufc.com/sitemap.xml?page=1</loc></sitemap></sitemapindex>"""

SUB_SITEMAP = """<?xml version="1.0"?>
<urlset>
<url><loc>https://www.ufc.com/athlete/fighter-one</loc></url>
<url><loc>https://www.ufc.com/athlete/fighter-two</loc></url>
</urlset>"""


@responses.activate
def test_sync_roster_creates_stub_fighters_and_checkpoints(app):
    responses.add(responses.GET, "https://www.ufc.com/sitemap.xml", body=SITEMAP_INDEX, status=200)
    responses.add(responses.GET, "https://www.ufc.com/sitemap.xml?page=1", body=SUB_SITEMAP, status=200)

    with app.app_context():
        client = UfcClient(crawl_delay=0)
        count = pipeline.sync_roster(client=client)
        assert count == 2

        session = Session()
        slugs = {f.ufc_slug for f in session.query(Fighter).all()}
        assert slugs == {"fighter-one", "fighter-two"}
        checkpoint_statuses = {c.fighter_slug: c.status for c in session.query(ScrapeCheckpoint).all()}
        assert checkpoint_statuses == {"fighter-one": "pending", "fighter-two": "pending"}
        Session.remove()


@responses.activate
def test_scrape_details_resumes_and_records_errors(app):
    """One fighter scrapes successfully (overwriting the stub with real
    parsed data), one 404s - the checkpoint/resume bookkeeping must reflect
    that so a re-run only retries the failed one.
    """
    with app.app_context():
        session = Session()
        session.add(Fighter(ufc_slug="fighter-one", name="Fighter One Stub"))
        session.add(Fighter(ufc_slug="fighter-two", name="Fighter Two Stub"))
        session.add(ScrapeCheckpoint(fighter_slug="fighter-one", status="pending"))
        session.add(ScrapeCheckpoint(fighter_slug="fighter-two", status="pending"))
        session.commit()
        Session.remove()

        sample_html = FIXTURE.read_text(encoding="utf-8")
        responses.add(responses.GET, "https://www.ufc.com/athlete/fighter-one", body=sample_html, status=200)
        responses.add(responses.GET, "https://www.ufc.com/athlete/fighter-two", status=404)

        client = UfcClient(crawl_delay=0)
        result = pipeline.scrape_details(client=client)
        assert result["total"] == 2
        assert result["done"] == 1
        assert result["errors"] == 1

        session = Session()
        fighter_one = session.query(Fighter).filter_by(ufc_slug="fighter-one").one()
        assert fighter_one.name == "Jon Jones"  # overwritten by the real parsed page
        assert fighter_one.stats_scraped_at is not None

        fighter_two = session.query(Fighter).filter_by(ufc_slug="fighter-two").one()
        assert fighter_two.stats_scraped_at is None

        checkpoint_two = session.query(ScrapeCheckpoint).filter_by(fighter_slug="fighter-two").one()
        assert checkpoint_two.status == "error"
        Session.remove()


@responses.activate
def test_scrape_details_refreshes_stale_but_skips_fresh(app):
    """A seeded install has every fighter already scraped, so resume mode
    must key off staleness - otherwise Sync Now would never refresh
    anything and seeded stats would be frozen forever (see
    app/utils/seed.py).
    """
    with app.app_context():
        now = dt.datetime.utcnow()
        session = Session()
        session.add(
            Fighter(
                ufc_slug="fighter-one",
                name="Stale Fighter",
                stats_scraped_at=now - dt.timedelta(days=90),
            )
        )
        session.add(
            Fighter(
                ufc_slug="fighter-two",
                name="Fresh Fighter",
                stats_scraped_at=now - dt.timedelta(days=2),
            )
        )
        session.add(ScrapeCheckpoint(fighter_slug="fighter-one", status="done"))
        session.add(ScrapeCheckpoint(fighter_slug="fighter-two", status="done"))
        session.commit()
        Session.remove()

        sample_html = FIXTURE.read_text(encoding="utf-8")
        responses.add(responses.GET, "https://www.ufc.com/athlete/fighter-one", body=sample_html, status=200)

        client = UfcClient(crawl_delay=0)
        result = pipeline.scrape_details(client=client, max_age_days=30)

        # only the stale one is even attempted; the fresh one is left alone
        assert result["total"] == 1
        assert result["done"] == 1
        assert result["errors"] == 0

        session = Session()
        assert session.query(Fighter).filter_by(ufc_slug="fighter-one").one().name == "Jon Jones"
        assert session.query(Fighter).filter_by(ufc_slug="fighter-two").one().name == "Fresh Fighter"
        Session.remove()


@responses.activate
def test_scrape_details_max_age_none_never_refreshes(app):
    """max_age_days=None preserves the original scraped-once-is-done
    behaviour, for callers that only want genuinely new fighters.
    """
    with app.app_context():
        session = Session()
        session.add(
            Fighter(
                ufc_slug="fighter-one",
                name="Ancient Fighter",
                stats_scraped_at=dt.datetime.utcnow() - dt.timedelta(days=900),
            )
        )
        session.commit()
        Session.remove()

        client = UfcClient(crawl_delay=0)
        result = pipeline.scrape_details(client=client, max_age_days=None)
        assert result["total"] == 0
