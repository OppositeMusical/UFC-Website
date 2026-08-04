from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path",
    ["/", "/betting/prizepicks", "/betting/draftkings", "/betting/kalshi", "/chat/", "/settings/"],
)
def test_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200


def test_unknown_platform_404s(client):
    resp = client.get("/betting/not-a-real-platform")
    assert resp.status_code == 404


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_autocomplete_short_query_returns_empty(client):
    resp = client.get("/api/fighters/autocomplete?q=a")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_dashboard_renders_saved_predictions(client, app):
    """Regression: the dashboard used to 500 as soon as one prediction
    existed. get_setting() called Session.remove(), and Python evaluates it
    as a render_template() argument *before* rendering - so the prediction
    rows were detached by the time Jinja read p.fighter_a.name
    (DetachedInstanceError). An empty table hid it: no rows, no lazy load.
    """
    from app.extensions import Session
    from app.models.fighter import Fighter
    from app.models.prediction import Prediction

    with app.app_context():
        session = Session()
        fighter_a = Fighter(ufc_slug="alex-pereira", name="Alex Pereira")
        fighter_b = Fighter(ufc_slug="israel-adesanya", name="Israel Adesanya")
        session.add_all([fighter_a, fighter_b])
        session.flush()
        session.add(
            Prediction(
                platform="prizepicks",
                fighter_a_id=fighter_a.id,
                fighter_b_id=fighter_b.id,
                stat_category="significant_strikes",
                line_value=72.5,
                direction_predicted="over",
                confidence_pct=64,
                reasoning="test",
            )
        )
        session.commit()
        Session.remove()

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Alex Pereira" in body
    assert "Israel Adesanya" in body
