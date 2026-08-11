from __future__ import annotations

import datetime as dt

import requests
import responses

from app.extensions import Session
from app.models.fighter import Fighter
from app.services.db.session import set_setting
from app.services.status import fighter_db_detail, fighter_db_status, provider_status


def _add_fighter(session, slug, *, slpm=4.2, scraped_days_ago=1):
    session.add(
        Fighter(
            ufc_slug=slug,
            name=slug.replace("-", " ").title(),
            slpm=slpm,
            stats_scraped_at=dt.datetime.utcnow() - dt.timedelta(days=scraped_days_ago),
        )
    )


def test_seeded_db_reports_ok_not_unsynced(app):
    """Regression: a freshly seeded install has fighters with real scrape
    timestamps but no `last_fighter_sync_at` setting. The old chip keyed off
    that setting and told every new user the database wasn't synced, on top
    of a full roster.
    """
    with app.app_context():
        session = Session()
        for i in range(3):
            _add_fighter(session, f"fighter-{i}", scraped_days_ago=2)
        session.commit()

        status = fighter_db_status()
        assert status["level"] == "ok"
        assert status["with_stats"] == 3
        assert "3 fighters with stats" in status["label"]
        Session.remove()


def test_settings_card_never_claims_unsynced_on_a_seeded_db(app, client):
    """Regression: the Settings > Fighter Database card read the
    `last_fighter_sync_at` setting, which only a manual sync writes. On a
    seeded install it was absent, so the card said "Never synced -
    predictions won't have real stats until you sync" while the dashboard,
    querying the same table, reported thousands of fighters with stats.
    """
    with app.app_context():
        session = Session()
        for i in range(3):
            _add_fighter(session, f"fighter-{i}", scraped_days_ago=2)
        session.commit()
        Session.remove()

        detail = fighter_db_detail()
        assert detail["level"] == "ok"
        assert "3 of 3 fighters have career stats" in detail["chip"]

        body = client.get("/settings/").get_data(as_text=True)
        assert "Never synced" not in body
        assert "3 of 3 fighters have career stats" in body
        Session.remove()


def test_settings_card_says_what_a_sync_would_fetch(app):
    """The old card never distinguished "nothing to do" from "thousands of
    fighters are missing stats" - both rendered the same sentence next to the
    button that starts a multi-hour scrape.
    """
    with app.app_context():
        session = Session()
        _add_fighter(session, "has-stats", scraped_days_ago=1)
        session.add(Fighter(ufc_slug="name-only", name="Name Only"))
        session.commit()
        Session.remove()

        detail = fighter_db_detail()
        assert "1 of 2 fighters have career stats" in detail["chip"]
        assert "remaining 1" in detail["advice"]
        Session.remove()


def test_settings_card_reports_nothing_to_fetch_when_complete(app):
    with app.app_context():
        session = Session()
        _add_fighter(session, "complete-one", scraped_days_ago=0)
        session.commit()
        Session.remove()

        detail = fighter_db_detail()
        assert detail["level"] == "ok"
        assert "scraped today" in detail["chip"]
        assert "nothing to fetch" in detail["advice"]
        Session.remove()


def test_settings_card_flags_stale_stats(app):
    with app.app_context():
        session = Session()
        _add_fighter(session, "ancient", scraped_days_ago=120)
        session.commit()
        Session.remove()

        detail = fighter_db_detail()
        assert detail["level"] == "warn"
        assert "more than 30 days old" in detail["advice"]
        Session.remove()


def test_empty_db_reports_error(app):
    with app.app_context():
        status = fighter_db_status()
        assert status["level"] == "err"
        assert status["with_stats"] == 0
        assert "Sync Now" in status["detail"]
        Session.remove()


def test_stats_only_stubs_report_error(app):
    """Roster stubs exist but nothing has been detail-scraped yet - there is
    nothing for the AI to reason about, so this is not an 'ok' state.
    """
    with app.app_context():
        session = Session()
        session.add(Fighter(ufc_slug="stub-one", name="Stub One"))
        session.commit()

        status = fighter_db_status()
        assert status["level"] == "err"
        assert status["total"] == 1
        assert status["with_stats"] == 0
        Session.remove()


def test_stale_db_reports_warn(app):
    with app.app_context():
        session = Session()
        _add_fighter(session, "ancient-fighter", scraped_days_ago=120)
        session.commit()

        status = fighter_db_status()
        assert status["level"] == "warn"
        assert status["age_days"] == 120
        assert "120d ago" in status["label"]
        Session.remove()


@responses.activate
def test_provider_status_ollama_down_is_error(app):
    responses.add(
        responses.GET,
        "http://localhost:11434/api/tags",
        body=requests.exceptions.ConnectionError("refused"),
    )
    with app.app_context():
        status = provider_status()
        assert status["level"] == "err"
        assert "not running" in status["label"]
        Session.remove()


@responses.activate
def test_provider_status_ollama_up_with_model_is_ok(app):
    responses.add(
        responses.GET,
        "http://localhost:11434/api/tags",
        json={"models": [{"name": "llama3.1:latest"}]},
        status=200,
    )
    with app.app_context():
        status = provider_status()
        assert status["level"] == "ok"
        Session.remove()


@responses.activate
def test_provider_status_ollama_running_without_models_warns(app):
    responses.add(
        responses.GET, "http://localhost:11434/api/tags", json={"models": []}, status=200
    )
    with app.app_context():
        status = provider_status()
        assert status["level"] == "warn"
        assert "no models" in status["label"]
        Session.remove()


def test_provider_status_hosted_without_key_is_error(app, monkeypatch):
    from app.services.secrets import secret_manager

    monkeypatch.setattr(secret_manager, "has_key", lambda provider: False)
    with app.app_context():
        set_setting("active_provider", "openai")
        status = provider_status()
        assert status["level"] == "err"
        assert "no API key" in status["label"]
        Session.remove()


def test_provider_status_hosted_with_key_is_ok(app, monkeypatch):
    from app.services.secrets import secret_manager

    monkeypatch.setattr(secret_manager, "has_key", lambda provider: True)
    with app.app_context():
        set_setting("active_provider", "claude")
        status = provider_status()
        assert status["level"] == "ok"
        assert "API key set" in status["label"]
        Session.remove()


def test_provider_status_endpoint(client):
    resp = client.get("/api/status/provider")
    assert resp.status_code == 200
    assert resp.get_json()["level"] in {"ok", "warn", "err"}
