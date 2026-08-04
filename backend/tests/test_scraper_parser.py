from __future__ import annotations

from pathlib import Path

from app.services.scraper.parser import parse_athlete_page, slug_from_url

FIXTURE = Path(__file__).parent / "fixtures" / "ufc_athlete_sample.html"


def test_parse_real_athlete_page():
    """Parses a real, saved ufc.com/athlete/jon-jones page. If ufc.com's
    markup ever changes, this test - not a silent bad-data ingest - is
    what should catch it.
    """
    html = FIXTURE.read_text(encoding="utf-8")
    data = parse_athlete_page(html, source_url="https://www.ufc.com/athlete/jon-jones")

    assert data["name"] == "Jon Jones"
    assert data["nickname"] == "Bones"
    assert data["weight_class"] == "Heavyweight"
    assert data["wins"] == 28
    assert data["losses"] == 1
    assert data["draws"] == 0
    assert data["status"] == "Active"
    assert data["height_in"] == 76.0
    assert data["reach_in"] == 84.5
    assert data["leg_reach_in"] == 45.0
    assert data["slpm"] == 4.38
    assert data["sapm"] == 2.24
    assert data["td_avg"] == 1.89
    assert data["sub_avg"] == 0.46
    assert data["sig_str_defense_pct"] == 64.0
    assert data["td_defense_pct"] == 95.0
    assert data["knockdown_avg"] == 0.25
    assert data["avg_fight_time"] == "14:52"
    assert data["source_url"] == "https://www.ufc.com/athlete/jon-jones"


def test_slug_from_url():
    assert slug_from_url("https://www.ufc.com/athlete/jon-jones") == "jon-jones"
    assert slug_from_url("https://www.ufc.com/athlete/jon-jones/") == "jon-jones"


def test_parse_empty_html_returns_empty_dict():
    assert parse_athlete_page("<html><body></body></html>") == {}
