"""American moneyline arithmetic.

Worked by hand rather than against the implementation - these are numbers a
user can check on any odds calculator, so getting them subtly wrong would be
invisible in the UI and wrong in the wallet.
"""
from __future__ import annotations

import pytest

from app.services.odds import (
    InvalidMoneyline,
    assess,
    expected_value_per_100,
    format_moneyline,
    implied_probability_pct,
    parse_moneyline,
    profit_per_100,
)


@pytest.mark.parametrize(
    "moneyline,expected",
    [
        (-150, 60.0),  # 150 / (150 + 100)
        (150, 40.0),  # 100 / (150 + 100)
        (-110, 52.380952),  # the standard vig price
        (100, 50.0),  # even money, either sign
        (-100, 50.0),
        (450, 18.181818),
        (-900, 90.0),
    ],
)
def test_implied_probability(moneyline, expected):
    assert implied_probability_pct(moneyline) == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize(
    "moneyline,expected",
    [(150, 150.0), (-150, 66.666667), (-100, 100.0), (100, 100.0)],
)
def test_profit_per_100(moneyline, expected):
    assert profit_per_100(moneyline) == pytest.approx(expected, abs=1e-5)


def test_expected_value_matches_hand_calculation():
    # +450 at a 30% true chance: 0.30 * 450 - 0.70 * 100 = +65
    assert expected_value_per_100(450, 30) == pytest.approx(65.0)
    # -150 at 72%: profit 66.67 -> 0.72 * 66.67 - 0.28 * 100 = +20
    assert expected_value_per_100(-150, 72) == pytest.approx(20.0, abs=0.01)


def test_expected_value_is_zero_at_the_implied_probability():
    """The break-even point: a price is exactly fair at its own implied
    probability, so any edge the app reports has to come from the model
    disagreeing with the price, not from the arithmetic."""
    for moneyline in (-150, 150, -110, 450):
        implied = implied_probability_pct(moneyline)
        assert expected_value_per_100(moneyline, implied) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("value,expected", [("+150", 150), ("150", 150), ("-150", -150), (150.0, 150), (" -110 ", -110)])
def test_parse_accepts_the_forms_people_actually_type(value, expected):
    assert parse_moneyline(value) == expected


@pytest.mark.parametrize("value", ["abc", "", None, 50, -99, 0, 99, True, [], {}])
def test_parse_rejects_non_prices(value):
    """Anything strictly inside (-100, +100) is not an American price, and a
    bool is not a number no matter what Python thinks."""
    with pytest.raises(InvalidMoneyline):
        parse_moneyline(value)


def test_format_is_always_signed():
    assert format_moneyline(150) == "+150"
    assert format_moneyline(-150) == "-150"


def test_assess_flags_value_only_outside_the_noise_band():
    """A couple of points of "edge" is inside the error bar of an LLM
    estimate; reporting that as value would dress a coin flip up as a signal."""
    assert assess(-110, 54)["verdict"] == "fair"  # implied 52.4, edge +1.6
    assert assess(-110, 60)["verdict"] == "value"  # edge +7.6
    assert assess(-110, 45)["verdict"] == "overpriced"  # edge -7.4


@pytest.mark.parametrize("model_pct", [90, 5])
def test_a_huge_gap_is_flagged_as_suspect_not_as_a_jackpot(model_pct):
    """Symmetric in both directions. A sportsbook is not wrong by twenty
    points on a mainstream market, but a language model asked for a
    probability routinely is - a local model was observed pricing
    "KO/TKO in round 2" above "KO/TKO in any round", which is impossible.
    Rendering that as enormous value is the worst thing this page could do.
    """
    assert assess(-110, model_pct)["verdict"] == "implausible"


def test_expected_value_is_still_reported_for_plausible_gaps():
    """The suspect band must not swallow ordinary results."""
    result = assess(-110, 60)
    assert result["verdict"] == "value"
    assert result["expectedValuePer100"] > 0


def test_assess_reports_the_gap_in_percentage_points():
    result = assess(150, 50)  # implied 40.0
    assert result["impliedProbabilityPct"] == 40.0
    assert result["modelProbabilityPct"] == 50
    assert result["edgePct"] == pytest.approx(10.0)
    assert result["moneyline_display"] == "+150"
