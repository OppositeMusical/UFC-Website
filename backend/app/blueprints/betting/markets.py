"""Moneyline markets: method of victory, method-in-round, and round reached.

These are priced markets rather than stat lines, so they take a moneyline
instead of an over/under number. Kept apart from `platforms.py`'s
StatCategory because the two answer different questions - "will this number
be higher or lower" versus "how likely is this outcome, and is the price
right".

The three markets overlap by design (a KO in round 2 is also a KO, and also
a fight reaching round 2). They are listed and priced separately because a
sportsbook prices them separately, and the interesting question is usually
whether those prices agree with each other.
"""
from __future__ import annotations

from enum import Enum


class VictoryMethod(str, Enum):
    KO_TKO = "ko_tko"
    SUBMISSION = "submission"
    DECISION = "decision"
    DRAW = "draw"

    @property
    def label(self) -> str:
        return _METHOD_LABELS[self]


_METHOD_LABELS = {
    VictoryMethod.KO_TKO: "KO/TKO",
    VictoryMethod.SUBMISSION: "Submission",
    VictoryMethod.DECISION: "Decision",
    VictoryMethod.DRAW: "Draw",
}


class MarketType(str, Enum):
    METHOD = "method"
    METHOD_IN_ROUND = "method_in_round"
    ROUND_REACHED = "round_reached"


# A UFC bout is three rounds, or five for a main event or title fight. Rounds
# 4 and 5 therefore only exist for some bouts - the form says so rather than
# hiding them, because whether a fight is five rounds is something the user
# knows and the app does not.
ROUNDS = (1, 2, 3, 4, 5)
FIVE_ROUND_ONLY = (4, 5)

# A draw is scored after the final round, so it cannot happen *in* a round.
# Offering "Draw in round 2" would be offering a bet that can never win.
METHOD_IN_ROUND_METHODS = tuple(m for m in VictoryMethod if m is not VictoryMethod.DRAW)

# Every fight reaches round 1 by definition, so pricing it is meaningless.
ROUND_REACHED_ROUNDS = tuple(r for r in ROUNDS if r > 1)


# The three forms the page renders, as data rather than three near-identical
# blocks of HTML and three near-identical submit handlers. The template loops
# over this and betting.js binds every `.market-card` the same way, so adding
# a fourth market is an entry here rather than a fourth copy of everything.
FIGHT_MARKET_FORMS = (
    {
        "key": "method",
        "market_type": MarketType.METHOD.value,
        "title": "Method of Victory",
        "blurb": (
            "How the fight ends, without saying when. Paste the price "
            "DraftKings is offering and the model prices it independently."
        ),
        "methods": tuple(VictoryMethod),
        "rounds": (),
    },
    {
        "key": "method-in-round",
        "market_type": MarketType.METHOD_IN_ROUND.value,
        "title": "Method of Victory in a Round",
        "blurb": (
            "The same outcomes pinned to a single round - a much narrower "
            "target, and priced far longer. Draw is not offered here: a draw "
            "is scored after the final round, so it cannot land in one."
        ),
        "methods": METHOD_IN_ROUND_METHODS,
        "rounds": ROUNDS,
    },
    {
        "key": "round-reached",
        "market_type": MarketType.ROUND_REACHED.value,
        "title": "Fight Reaches a Round",
        "blurb": (
            "Whether the bout is still going when a round begins - no view on "
            "who wins or how. Round 1 is not offered: every fight reaches it."
        ),
        "methods": (),
        "rounds": ROUND_REACHED_ROUNDS,
    },
)


class InvalidMarket(ValueError):
    """Raised for a market/method/round combination that cannot occur."""


def parse_round(value: object, *, allowed: tuple[int, ...]) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InvalidMarket("round must be a whole number") from None
    if number not in allowed:
        raise InvalidMarket(f"round must be one of {list(allowed)}; got {number}")
    return number


def parse_method(value: object, *, allowed: tuple[VictoryMethod, ...]) -> VictoryMethod:
    try:
        method = VictoryMethod(str(value))
    except ValueError:
        raise InvalidMarket(
            f"method must be one of {[m.value for m in allowed]}; got {value!r}"
        ) from None
    if method not in allowed:
        raise InvalidMarket(
            f"method must be one of {[m.value for m in allowed]}; got {method.value}"
        )
    return method


def describe(
    *,
    market_type: MarketType,
    fighter_a_name: str,
    fighter_b_name: str,
    method: VictoryMethod | None,
    round_number: int | None,
) -> str:
    """The market as a plain-English question.

    This string is what the model is asked to price and what the UI shows
    back, so the two can never describe different bets.

    A draw is the one case where naming a winner is wrong - the bet is on the
    bout, not on either fighter - so it gets its own phrasing.
    """
    if market_type is MarketType.ROUND_REACHED:
        return f"Will {fighter_a_name} vs {fighter_b_name} reach round {round_number}?"

    if method is VictoryMethod.DRAW:
        return f"Will {fighter_a_name} vs {fighter_b_name} end in a draw?"

    beats = f"Will {fighter_a_name} beat {fighter_b_name} by {method.label}"
    if market_type is MarketType.METHOD_IN_ROUND:
        return f"{beats} in round {round_number}?"
    return f"{beats}?"


def parse_market(payload: dict) -> dict:
    """Validates a market request into the pieces the route needs.

    Returns {"market_type", "method", "round_number"}. Raises InvalidMarket
    with a message aimed at the user, not at a developer.
    """
    raw_type = str(payload.get("market_type", "")).strip()
    try:
        market_type = MarketType(raw_type)
    except ValueError:
        raise InvalidMarket(
            f"market_type must be one of {[m.value for m in MarketType]}; got {raw_type!r}"
        ) from None

    if market_type is MarketType.METHOD:
        return {
            "market_type": market_type,
            "method": parse_method(payload.get("method"), allowed=tuple(VictoryMethod)),
            "round_number": None,
        }

    if market_type is MarketType.METHOD_IN_ROUND:
        return {
            "market_type": market_type,
            "method": parse_method(payload.get("method"), allowed=METHOD_IN_ROUND_METHODS),
            "round_number": parse_round(payload.get("round_number"), allowed=ROUNDS),
        }

    return {
        "market_type": market_type,
        "method": None,
        "round_number": parse_round(payload.get("round_number"), allowed=ROUND_REACHED_ROUNDS),
    }
