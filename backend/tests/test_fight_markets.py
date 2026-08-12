"""The three priced DraftKings markets (method, method-in-round, round reached)."""
from __future__ import annotations

import pytest

import app.blueprints.betting.routes as betting_routes
from app.blueprints.betting.markets import InvalidMarket, MarketType, VictoryMethod, describe, parse_market
from app.extensions import Session
from app.models.fighter import Fighter
from app.models.market_prediction import MarketPrediction


class FakeProvider:
    """Captures the prompt so tests can assert on what the model was told."""

    def __init__(self, raw: str):
        self.raw = raw
        self.last_prompt = ""
        self.last_system = ""

    def generate(self, messages, system=None, json_mode=False):
        self.last_prompt = messages[0]["content"]
        self.last_system = system or ""
        return self.raw


def _fighters(app):
    with app.app_context():
        session = Session()
        a = Fighter(ufc_slug="fighter-a", name="Fighter A", weight_class="Middleweight")
        b = Fighter(ufc_slug="fighter-b", name="Fighter B", weight_class="Middleweight")
        session.add_all([a, b])
        session.commit()
        ids = (a.id, b.id)
        Session.remove()
    return ids


def _install(monkeypatch, pct=40, reasoning="because of the stats"):
    provider = FakeProvider(f'{{"probability_pct": {pct}, "reasoning": "{reasoning}"}}')
    monkeypatch.setattr(betting_routes, "get_active_provider", lambda: provider)
    return provider


# ---- The rule the whole feature rests on --------------------------------


def test_the_model_is_never_shown_the_moneyline(app, client, monkeypatch):
    """The app's output is the gap between the model's probability and the
    price. Showing the model the price would let it anchor, turning that gap
    into a measure of how well it echoes its input.
    """
    a_id, b_id = _fighters(app)
    provider = _install(monkeypatch)

    resp = client.post(
        "/betting/draftkings/market",
        json={
            "fighter_a_id": a_id,
            "fighter_b_id": b_id,
            "market_type": "method",
            "method": "ko_tko",
            "moneyline": "+275",
        },
    )
    assert resp.status_code == 200

    haystack = f"{provider.last_prompt}\n{provider.last_system}"
    for leak in ("275", "+275", "moneyline", "26.7", "odds"):
        assert leak.lower() not in haystack.lower(), f"prompt leaked the price via {leak!r}"


# ---- Happy paths for each of the three markets ---------------------------


@pytest.mark.parametrize(
    "payload,expected_question",
    [
        (
            {"market_type": "method", "method": "ko_tko"},
            "Will Fighter A beat Fighter B by KO/TKO?",
        ),
        (
            {"market_type": "method", "method": "draw"},
            "Will Fighter A vs Fighter B end in a draw?",
        ),
        (
            {"market_type": "method_in_round", "method": "submission", "round_number": 2},
            "Will Fighter A beat Fighter B by Submission in round 2?",
        ),
        (
            {"market_type": "round_reached", "round_number": 3},
            "Will Fighter A vs Fighter B reach round 3?",
        ),
    ],
)
def test_each_market_prices_and_persists(app, client, monkeypatch, payload, expected_question):
    a_id, b_id = _fighters(app)
    _install(monkeypatch, pct=40)

    resp = client.post(
        "/betting/draftkings/market",
        json={"fighter_a_id": a_id, "fighter_b_id": b_id, "moneyline": "+200", **payload},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()

    assert data["question"] == expected_question
    assert data["modelProbabilityPct"] == 40
    # +200 implies 33.3%, so a 40% model estimate is a 6.7-point edge.
    assert data["impliedProbabilityPct"] == pytest.approx(33.3, abs=0.1)
    assert data["edgePct"] == pytest.approx(6.7, abs=0.1)
    assert data["verdict"] == "value"
    assert data["conversation_id"]

    with app.app_context():
        row = Session().query(MarketPrediction).one()
        assert row.question == expected_question
        assert row.moneyline == 200
        assert row.platform == "draftkings"
        Session.remove()


# ---- Combinations that cannot occur --------------------------------------


def test_draw_in_a_round_is_rejected(app, client, monkeypatch):
    """A draw is scored after the final round, so it cannot land in one -
    offering it would be offering a bet that can never win."""
    a_id, b_id = _fighters(app)
    _install(monkeypatch)
    resp = client.post(
        "/betting/draftkings/market",
        json={
            "fighter_a_id": a_id,
            "fighter_b_id": b_id,
            "market_type": "method_in_round",
            "method": "draw",
            "round_number": 2,
            "moneyline": "+500",
        },
    )
    assert resp.status_code == 400
    assert "method" in resp.get_json()["error"]


def test_round_one_reached_is_rejected(app, client, monkeypatch):
    """Every fight reaches round 1, so pricing it is meaningless."""
    a_id, b_id = _fighters(app)
    _install(monkeypatch)
    resp = client.post(
        "/betting/draftkings/market",
        json={
            "fighter_a_id": a_id,
            "fighter_b_id": b_id,
            "market_type": "round_reached",
            "round_number": 1,
            "moneyline": "-400",
        },
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"market_type": "nope", "moneyline": "+100"},
        {"market_type": "method", "method": "headbutt", "moneyline": "+100"},
        {"market_type": "method", "method": "ko_tko", "moneyline": "+50"},
        {"market_type": "method", "method": "ko_tko", "moneyline": "abc"},
        {"market_type": "method", "method": "ko_tko"},
        {"market_type": "round_reached", "round_number": 9, "moneyline": "+100"},
        {"market_type": "method_in_round", "method": "ko_tko", "moneyline": "+100"},
    ],
)
def test_bad_requests_are_rejected_before_the_model_runs(app, client, monkeypatch, payload):
    a_id, b_id = _fighters(app)
    provider = _install(monkeypatch)
    resp = client.post(
        "/betting/draftkings/market",
        json={"fighter_a_id": a_id, "fighter_b_id": b_id, **payload},
    )
    assert resp.status_code == 400
    assert provider.last_prompt == "", "validation must happen before spending a model call"


def test_missing_fighters_rejected(client):
    resp = client.post("/betting/draftkings/market", json={"market_type": "method", "method": "ko_tko"})
    assert resp.status_code == 400


def test_unknown_platform_is_404(client):
    resp = client.post("/betting/nope/market", json={})
    assert resp.status_code == 404


def test_platforms_without_fight_markets_refuse(app, client):
    """Only DraftKings lists these, so the other two must not quietly accept
    a market request that their page never renders."""
    a_id, b_id = _fighters(app)
    for platform in ("prizepicks", "kalshi"):
        resp = client.post(
            f"/betting/{platform}/market",
            json={
                "fighter_a_id": a_id,
                "fighter_b_id": b_id,
                "market_type": "method",
                "method": "ko_tko",
                "moneyline": "+100",
            },
        )
        assert resp.status_code == 400, platform


def test_provider_failure_is_502(app, client, monkeypatch):
    a_id, b_id = _fighters(app)
    monkeypatch.setattr(betting_routes, "get_active_provider", lambda: FakeProvider("not json"))
    resp = client.post(
        "/betting/draftkings/market",
        json={
            "fighter_a_id": a_id,
            "fighter_b_id": b_id,
            "market_type": "method",
            "method": "decision",
            "moneyline": "-120",
        },
    )
    assert resp.status_code == 502


# ---- The page itself ------------------------------------------------------


def test_draftkings_page_renders_all_three_markets(client):
    body = client.get("/betting/draftkings").get_data(as_text=True)
    assert 'data-market-type="method"' in body
    assert 'data-market-type="method_in_round"' in body
    assert 'data-market-type="round_reached"' in body
    # Draw is offered for the plain method market but not the in-round one.
    assert body.count('value="draw"') == 1


def test_other_platforms_do_not_render_fight_markets(client):
    for platform in ("prizepicks", "kalshi"):
        body = client.get(f"/betting/{platform}").get_data(as_text=True)
        assert "market-card" not in body, platform


def test_describe_never_names_a_winner_for_a_draw():
    assert describe(
        market_type=MarketType.METHOD,
        fighter_a_name="A",
        fighter_b_name="B",
        method=VictoryMethod.DRAW,
        round_number=None,
    ) == "Will A vs B end in a draw?"


def test_parse_market_rejects_unknown_type():
    with pytest.raises(InvalidMarket):
        parse_market({"market_type": ""})
