"""Parses a ufc.com athlete profile page.

Every selector is a named constant, verified against a real fetched page
(Jon Jones's profile, saved as tests/fixtures/ufc_athlete_sample.html). If
the live markup changes, the parser test against that fixture keeps passing
while a live re-check would fail - that's the intended signal to come back
here and update these constants, rather than silently ingesting bad data.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Hero section: name / nickname / weight class / record
CLS_NAME = "hero-profile__name"
CLS_NICKNAME = "hero-profile__nickname"
CLS_DIVISION_TITLE = "hero-profile__division-title"
CLS_DIVISION_RECORD = "hero-profile__division-body"
CLS_STATUS_TAG = "hero-profile__tag"

# Bio "tale of the tape" fields
CLS_BIO_FIELD = "c-bio__field"
CLS_BIO_LABEL = "c-bio__label"
CLS_BIO_TEXT = "c-bio__text"

# Career stat comparisons
CLS_STAT_GROUP = "c-stat-compare__group"
CLS_STAT_NUMBER = "c-stat-compare__number"
CLS_STAT_LABEL = "c-stat-compare__label"

STATUS_VALUES = {"active", "not fighting", "retired"}

# Bio label text -> Fighter model field. A leading underscore means "known
# but intentionally not stored" (kept here so a future column addition is
# a one-line change, not a re-discovery of the label).
BIO_LABEL_MAP: dict[str, str] = {
    "Status": "status",
    "Place of Birth": "place_of_birth",
    "Trains at": "trains_at",
    "Height": "height_in",
    "Weight": "_weight_lbs",
    "Octagon Debut": "octagon_debut",
    "Reach": "reach_in",
    "Leg reach": "leg_reach_in",
    "Stance": "stance",
}

# Stat label text -> Fighter model field.
STAT_LABEL_MAP: dict[str, str] = {
    "Sig. Str. Landed": "slpm",
    "Sig. Str. Absorbed": "sapm",
    "Sig. Str. Defense": "sig_str_defense_pct",
    "Takedown avg": "td_avg",
    "Takedown Defense": "td_defense_pct",
    "Submission avg": "sub_avg",
    "Knockdown Avg": "knockdown_avg",
    "Average fight time": "avg_fight_time",
}

FLOAT_FIELDS = {
    "height_in",
    "reach_in",
    "leg_reach_in",
    "slpm",
    "sapm",
    "sig_str_defense_pct",
    "td_avg",
    "td_defense_pct",
    "sub_avg",
    "knockdown_avg",
}

_NUMBER_RE = re.compile(r"-?\d+\.?\d*")
_RECORD_RE = re.compile(r"(\d+)-(\d+)-(\d+)")
_NC_RE = re.compile(r"\((\d+)\s*NC\)", re.IGNORECASE)
_FIGHT_TIME_RE = re.compile(r"\d+:\d+")


def _first_number(text: str) -> str | None:
    match = _NUMBER_RE.search(text)
    return match.group(0) if match else None


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def parse_athlete_page(html: str, source_url: str = "") -> dict:
    """Returns a dict of Fighter-model-shaped fields. Missing/unparseable
    fields are simply absent from the dict rather than raising - callers
    decide what a "good enough" scrape looks like.
    """
    soup = BeautifulSoup(html, "lxml")
    data: dict = {}
    if source_url:
        data["source_url"] = source_url

    name_el = soup.select_one(f".{CLS_NAME}")
    if name_el:
        data["name"] = name_el.get_text(strip=True)

    nickname_el = soup.select_one(f".{CLS_NICKNAME}")
    if nickname_el:
        nickname = nickname_el.get_text(strip=True).strip("\"“”")
        if nickname:
            data["nickname"] = nickname

    division_el = soup.select_one(f".{CLS_DIVISION_TITLE}")
    if division_el:
        data["weight_class"] = division_el.get_text(strip=True).replace(" Division", "").strip()

    record_el = soup.select_one(f".{CLS_DIVISION_RECORD}")
    if record_el:
        record_text = record_el.get_text(strip=True)
        match = _RECORD_RE.match(record_text)
        if match:
            data["wins"], data["losses"], data["draws"] = (int(g) for g in match.groups())
        nc_match = _NC_RE.search(record_text)
        data["no_contests"] = int(nc_match.group(1)) if nc_match else 0

    for tag_el in soup.select(f".{CLS_STATUS_TAG}"):
        tag_text = tag_el.get_text(strip=True)
        if tag_text.lower() in STATUS_VALUES:
            data["status"] = tag_text
            break

    for field_el in soup.select(f".{CLS_BIO_FIELD}"):
        label_el = field_el.select_one(f".{CLS_BIO_LABEL}")
        text_el = field_el.select_one(f".{CLS_BIO_TEXT}")
        if not label_el or not text_el:
            continue
        model_field = BIO_LABEL_MAP.get(label_el.get_text(strip=True))
        if not model_field or model_field.startswith("_"):
            continue
        raw_value = text_el.get_text(strip=True)
        if model_field in FLOAT_FIELDS:
            num = _first_number(raw_value)
            if num is not None:
                data[model_field] = float(num)
        elif raw_value:
            data[model_field] = raw_value

    for group_el in soup.select(f".{CLS_STAT_GROUP}"):
        number_el = group_el.select_one(f".{CLS_STAT_NUMBER}")
        label_el = group_el.select_one(f".{CLS_STAT_LABEL}")
        if not number_el or not label_el:
            continue
        model_field = STAT_LABEL_MAP.get(label_el.get_text(strip=True))
        if not model_field:
            continue
        raw_value = number_el.get_text(strip=True)
        if model_field == "avg_fight_time":
            match = _FIGHT_TIME_RE.search(raw_value)
            if match:
                data[model_field] = match.group(0)
        else:
            num = _first_number(raw_value)
            if num is not None:
                data[model_field] = float(num)

    return data
