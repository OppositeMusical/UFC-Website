from __future__ import annotations

import app.blueprints.betting.routes as betting_routes
from app.extensions import Session
from app.models.fighter import Fighter


class FakeProvider:
    def __init__(self, raw: str):
        self.raw = raw

    def generate(self, messages, system=None, json_mode=False):
        return self.raw


def _make_fighters(app):
    with app.app_context():
        session = Session()
        a = Fighter(ufc_slug="fighter-a", name="Fighter A", weight_class="Lightweight")
        b = Fighter(ufc_slug="fighter-b", name="Fighter B", weight_class="Lightweight")
        session.add_all([a, b])
        session.commit()
        a_id, b_id = a.id, b.id
        Session.remove()
    return a_id, b_id


def test_predict_success(app, client, monkeypatch):
    a_id, b_id = _make_fighters(app)
    monkeypatch.setattr(
        betting_routes,
        "get_active_provider",
        lambda: FakeProvider('{"direction": "over", "confidence_pct": 70, "reasoning": "test reasoning"}'),
    )
    resp = client.post(
        "/betting/prizepicks/predict",
        json={"fighter_a_id": a_id, "fighter_b_id": b_id, "stat_category": "takedowns", "line_value": 1.5},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["prediction"]["direction"] == "over"
    assert data["prediction"]["confidence_pct"] == 70
    assert "conversation_id" in data


def test_predict_missing_fields(client):
    resp = client.post("/betting/prizepicks/predict", json={})
    assert resp.status_code == 400


def test_predict_unknown_platform(client):
    resp = client.post("/betting/nope/predict", json={})
    assert resp.status_code == 404


def test_predict_invalid_stat_category(app, client):
    a_id, b_id = _make_fighters(app)
    resp = client.post(
        "/betting/prizepicks/predict",
        json={"fighter_a_id": a_id, "fighter_b_id": b_id, "stat_category": "not-a-category", "line_value": 1.5},
    )
    assert resp.status_code == 400


def test_predict_bad_provider_json_returns_502(app, client, monkeypatch):
    a_id, b_id = _make_fighters(app)
    monkeypatch.setattr(betting_routes, "get_active_provider", lambda: FakeProvider("not json at all"))
    resp = client.post(
        "/betting/prizepicks/predict",
        json={"fighter_a_id": a_id, "fighter_b_id": b_id, "stat_category": "takedowns", "line_value": 1.5},
    )
    assert resp.status_code == 502


def test_market_probability_success_and_saves_conversation(app, client, monkeypatch):
    """Free-text Kalshi question -> probability, plus a conversation so the
    estimate is saved and 'Continue in Chat' has somewhere to go.
    """
    from app.models.conversation import Conversation
    from app.models.message import Message

    _make_fighters(app)
    monkeypatch.setattr(
        betting_routes,
        "get_active_provider",
        lambda: FakeProvider('{"probability_pct": 63, "reasoning": "test reasoning"}'),
    )

    resp = client.post(
        "/betting/kalshi/market-probability",
        json={"question": "Will Fighter A win by knockout in round 1?"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["probability_pct"] == 63
    assert data["reasoning"] == "test reasoning"
    assert "Fighter A" in data["matched_fighters"]

    with app.app_context():
        session = Session()
        convo = session.get(Conversation, data["conversation_id"])
        assert convo.platform == "kalshi"
        messages = session.query(Message).filter_by(conversation_id=convo.id).all()
        assert len(messages) == 1
        assert "63% YES" in messages[0].content
        Session.remove()


def test_market_probability_without_matching_fighter_still_answers(app, client, monkeypatch):
    """A question naming nobody in the database must not 500 - it should
    answer and flag that the estimate isn't stat-grounded.
    """
    _make_fighters(app)
    monkeypatch.setattr(
        betting_routes,
        "get_active_provider",
        lambda: FakeProvider('{"probability_pct": 50, "reasoning": "not enough information"}'),
    )
    resp = client.post(
        "/betting/kalshi/market-probability",
        json={"question": "Will the main event go to a decision?"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["matched_fighters"] == []


def test_market_probability_rejected_on_other_platforms(client):
    """Only Kalshi declares supports_market_question - PrizePicks and
    DraftKings list fixed stat lines, so the endpoint must refuse rather
    than silently answer for a platform whose page has no such form.
    """
    for platform in ("prizepicks", "draftkings"):
        resp = client.post(f"/betting/{platform}/market-probability", json={"question": "Anything?"})
        assert resp.status_code == 400, platform


def test_market_probability_requires_question(client):
    resp = client.post("/betting/kalshi/market-probability", json={"question": "   "})
    assert resp.status_code == 400


def test_market_probability_rejects_overlong_question(client):
    resp = client.post("/betting/kalshi/market-probability", json={"question": "x" * 501})
    assert resp.status_code == 400


def test_market_probability_unparseable_response_is_502(app, client, monkeypatch):
    _make_fighters(app)
    monkeypatch.setattr(
        betting_routes, "get_active_provider", lambda: FakeProvider("I cannot answer that.")
    )
    resp = client.post("/betting/kalshi/market-probability", json={"question": "Will Fighter A win?"})
    assert resp.status_code == 502


def test_kalshi_page_shows_market_form_others_do_not(client):
    assert b'id="market-form"' in client.get("/betting/kalshi").data
    assert b'id="market-form"' not in client.get("/betting/prizepicks").data
