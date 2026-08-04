from __future__ import annotations

from app.extensions import Session
from app.models.fighter import Fighter
from app.services.fighter_mentions import find_mentioned_fighters


def _seed(app, names):
    with app.app_context():
        session = Session()
        for name in names:
            session.add(Fighter(ufc_slug=name.lower().replace(" ", "-"), name=name))
        session.commit()
        Session.remove()


def test_surname_namesakes_are_not_matched(app):
    """Regression: fuzzy matching alone matched every fighter sharing a
    surname, so "Will Jon Jones win by KO?" pulled in Antonio Jones and
    Carlton Jones too. Their stats went into the prompt as if they were
    participants and the model described Carlton as Jon's opponent.
    """
    _seed(app, ["Jon Jones", "Antonio Jones", "Carlton Jones"])

    with app.app_context():
        session = Session()
        matched = find_mentioned_fighters(session, "Will Jon Jones win his next fight by knockout?", limit=3)
        assert [f.name for f in matched] == ["Jon Jones"]
        Session.remove()


def test_matches_both_fighters_when_both_named(app):
    _seed(app, ["Alex Pereira", "Israel Adesanya", "Michel Pereira"])

    with app.app_context():
        session = Session()
        matched = find_mentioned_fighters(session, "Alex Pereira vs Israel Adesanya striking", limit=3)
        assert {f.name for f in matched} == {"Alex Pereira", "Israel Adesanya"}
        Session.remove()


def test_tolerates_a_typo_in_one_name_part(app):
    """The confirmation pass is per-token fuzzy, not exact, so a small
    misspelling still resolves - that tolerance is the whole reason the
    fuzzy matcher exists.
    """
    _seed(app, ["Jon Jones"])

    with app.app_context():
        session = Session()
        matched = find_mentioned_fighters(session, "how good is jon jons at wrestling", limit=2)
        assert [f.name for f in matched] == ["Jon Jones"]
        Session.remove()


def test_question_naming_nobody_matches_nothing(app):
    _seed(app, ["Jon Jones", "Alex Pereira"])

    with app.app_context():
        session = Session()
        matched = find_mentioned_fighters(session, "Will the main event go to a decision?", limit=3)
        assert matched == []
        Session.remove()


def test_empty_database_returns_nothing(app):
    with app.app_context():
        session = Session()
        assert find_mentioned_fighters(session, "Jon Jones", limit=2) == []
        Session.remove()
