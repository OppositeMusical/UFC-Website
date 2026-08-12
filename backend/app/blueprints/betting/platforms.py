"""Shared config for the PrizePicks/DraftKings/Kalshi pages - one form
pattern, one prediction pipeline (routes.py), branded per platform only by
what's declared here. See docs/SPEC.md section "Shared Betting Blueprint".
"""
from __future__ import annotations

from enum import Enum


class StatCategory(str, Enum):
    SIG_STRIKES_LANDED = "sig_strikes_landed"
    TAKEDOWNS = "takedowns"
    TAKEDOWN_ACCURACY = "takedown_accuracy"
    SUBMISSION_ATTEMPTS = "submission_attempts"
    CONTROL_TIME = "control_time"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    StatCategory.SIG_STRIKES_LANDED: "Significant Strikes Landed",
    StatCategory.TAKEDOWNS: "Takedowns",
    StatCategory.TAKEDOWN_ACCURACY: "Takedown Accuracy",
    StatCategory.SUBMISSION_ATTEMPTS: "Submission Attempts",
    StatCategory.CONTROL_TIME: "Control Time (minutes)",
}

PLATFORM_CONFIG = {
    "prizepicks": {
        "display_name": "PrizePicks",
        "brand_color": "#7C3AED",
        "stat_categories": [
            StatCategory.SIG_STRIKES_LANDED,
            StatCategory.TAKEDOWNS,
            StatCategory.SUBMISSION_ATTEMPTS,
        ],
    },
    "draftkings": {
        "display_name": "DraftKings",
        "brand_color": "#53D337",
        "stat_categories": [
            StatCategory.SIG_STRIKES_LANDED,
            StatCategory.TAKEDOWNS,
            StatCategory.TAKEDOWN_ACCURACY,
            StatCategory.CONTROL_TIME,
        ],
        # DraftKings lists priced fight markets alongside stat props: method
        # of victory, method in a given round, and whether the fight reaches
        # a round. Those take a moneyline rather than an over/under line, so
        # they get their own form and endpoint - see betting/markets.py.
        "supports_fight_markets": True,
    },
    "kalshi": {
        "display_name": "Kalshi",
        "brand_color": "#00D964",
        "stat_categories": [
            StatCategory.SIG_STRIKES_LANDED,
            StatCategory.TAKEDOWNS,
            StatCategory.SUBMISSION_ATTEMPTS,
            StatCategory.CONTROL_TIME,
        ],
        # Kalshi trades free-form event contracts ("will X win by KO?"), not
        # just fixed stat props, so this page also takes a plain-language
        # market question and returns a probability. The other two platforms
        # only list fixed stat lines, so they don't get the extra form.
        "supports_market_question": True,
    },
}


def get_platform(platform_key: str) -> dict | None:
    return PLATFORM_CONFIG.get(platform_key)
