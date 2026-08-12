"""American moneyline arithmetic.

Pure functions, no I/O - the numbers a user checks by hand against the
sportsbook, so they are kept apart from the AI path and tested directly.

The point of taking a moneyline at all is comparison: the model estimates a
probability from fighter stats, this module converts the book's price into
the probability it implies, and the gap between them is the only thing that
makes a price interesting. See `betting/routes.py` for the rule that keeps
that comparison honest - the model is never shown the odds.
"""
from __future__ import annotations

# American odds express a price relative to a 100-unit stake, so anything
# strictly inside (-100, +100) is not a price - it would mean risking less
# than 100 to win less than 100 at the same time. +100 and -100 are both the
# same thing, even money.
MIN_ABS_MONEYLINE = 100


class InvalidMoneyline(ValueError):
    """Raised for a value that is not a valid American price."""


def parse_moneyline(value: object) -> int:
    """Coerces user input to a valid American moneyline.

    Accepts "+150", "150", "-150", 150, 150.0. A bare positive number is read
    as a plus-money price, which is how books and bettors write it.
    """
    if isinstance(value, bool):  # bool is an int subclass; never a price
        raise InvalidMoneyline("moneyline must be a number")
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if not text:
            raise InvalidMoneyline("moneyline is required")
        # A leading "+" is meaningful to a human and invisible to int().
        try:
            number = int(float(text))
        except ValueError:
            raise InvalidMoneyline(f"'{value}' is not a moneyline") from None
    else:
        try:
            number = int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise InvalidMoneyline("moneyline must be a number") from None

    if abs(number) < MIN_ABS_MONEYLINE:
        raise InvalidMoneyline(
            f"American odds are at least +{MIN_ABS_MONEYLINE} or -{MIN_ABS_MONEYLINE}; "
            f"got {number:+d}"
        )
    return number


def implied_probability_pct(moneyline: int) -> float:
    """The probability the price implies, as a percentage.

    Includes the book's margin: the two sides of a real market add up to
    more than 100%, so this is always a little higher than the book's true
    estimate. Stripping that out needs the opposite side's price, which a
    single-market form does not have - so the UI says so rather than
    pretending the number is clean.
    """
    if moneyline < 0:
        favourite = float(-moneyline)
        return favourite / (favourite + 100.0) * 100.0
    return 100.0 / (float(moneyline) + 100.0) * 100.0


def profit_per_100(moneyline: int) -> float:
    """Profit (not return) on a 100-unit stake if the bet wins."""
    if moneyline < 0:
        return 100.0 / float(-moneyline) * 100.0
    return float(moneyline)


def expected_value_per_100(moneyline: int, probability_pct: float) -> float:
    """Expected profit on a 100-unit stake at the model's probability.

    Positive means the price is worth taking *if the model is right* - which
    is the whole caveat, and why the UI never renders this on its own.
    """
    p = max(0.0, min(1.0, probability_pct / 100.0))
    return p * profit_per_100(moneyline) - (1.0 - p) * 100.0


def format_moneyline(moneyline: int) -> str:
    """`-150` / `+220` - always signed, the way a book displays it."""
    return f"{moneyline:+d}"


# Below this the gap is inside the error bar of an LLM estimate.
NOISE_BAND_PTS = 5.0
# Above this the gap says more about the model than about the price. A
# sportsbook pricing a mainstream market is not wrong by twenty points; a
# language model asked for a probability routinely is. Observed for real
# while building this: a local model priced "KO/TKO in round 2" *higher*
# than "KO/TKO in any round", which is impossible - one is a subset of the
# other - and would have rendered as a 55-point edge worth chasing.
IMPLAUSIBLE_EDGE_PTS = 20.0


def assess(moneyline: int, model_probability_pct: int) -> dict:
    """Compares the model's probability against the price.

    `edge_pct` is in percentage points, not a ratio: "the model is 7 points
    higher than the price implies" is the sentence a bettor actually reasons
    with.

    Both bands are deliberately wide, and they fail in opposite directions on
    purpose: a small gap is noise, and a very large one is a red flag about
    the estimate rather than a jackpot. The app's job is to surface a
    disagreement, not to talk anyone into it.
    """
    implied = implied_probability_pct(moneyline)
    edge = model_probability_pct - implied

    if abs(edge) >= IMPLAUSIBLE_EDGE_PTS:
        verdict = "implausible"
        label = "Gap too large to trust"
    elif edge >= NOISE_BAND_PTS:
        verdict, label = "value", "Model sees value"
    elif edge <= -NOISE_BAND_PTS:
        verdict, label = "overpriced", "Priced above the model"
    else:
        verdict, label = "fair", "Roughly a fair price"

    return {
        "moneyline": moneyline,
        "moneyline_display": format_moneyline(moneyline),
        "impliedProbabilityPct": round(implied, 1),
        "modelProbabilityPct": model_probability_pct,
        "edgePct": round(edge, 1),
        "profitPer100": round(profit_per_100(moneyline), 2),
        "expectedValuePer100": round(expected_value_per_100(moneyline, model_probability_pct), 2),
        "verdict": verdict,
        "verdictLabel": label,
    }
