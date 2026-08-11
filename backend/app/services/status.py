"""Real, measured app status for the dashboard chips.

Deliberately derived from what's actually in the database / actually
reachable, not from configuration alone. The previous chips reported
`active_provider` as green whether or not that provider could be used, and
declared "Fighter DB not synced yet" whenever the `last_fighter_sync_at`
setting was missing - which is exactly the state a freshly seeded install
is in, so every new user was told to start a ~28h scrape on top of a
database that already had 6,746 fighters in it.

Levels are "ok" | "warn" | "err", matching the CSS chip modifiers.
"""
from __future__ import annotations

import datetime as dt

import requests
from sqlalchemy import func

from app.config import Config
from app.extensions import Session
from app.models.app_setting import KEY_ACTIVE_OLLAMA_MODEL, KEY_ACTIVE_PROVIDER
from app.models.fighter import Fighter
from app.services.db.session import get_setting
from app.services.secrets import secret_manager

# Mirrors pipeline.DEFAULT_MAX_AGE_DAYS: past this, a sync would actually
# re-fetch fighters, so that's the honest point to start nudging the user.
STALE_AFTER_DAYS = 30

PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "deepseek": "Deepseek",
    "claude": "Claude",
}


def fighter_db_status() -> dict:
    """Counts and freshness straight from the fighters table.

    `stats_scraped_at` is the source of truth for freshness rather than the
    `last_fighter_sync_at` setting, because a seeded install has real
    per-fighter scrape timestamps but no sync setting.
    """
    session = Session()
    total, with_stats, newest = session.query(
        func.count(Fighter.id),
        func.count(Fighter.slpm),
        func.max(Fighter.stats_scraped_at),
    ).one()

    if not total or not with_stats:
        return {
            "level": "err",
            "label": "Fighter database empty",
            "detail": "Predictions need fighter stats. Open Settings and run Sync Now.",
            "total": total or 0,
            "with_stats": with_stats or 0,
            "age_days": None,
        }

    age_days = None
    if newest is not None:
        age_days = max((dt.datetime.utcnow() - newest).days, 0)

    stats_label = f"{with_stats:,} fighters with stats"
    if age_days is None:
        return {
            "level": "ok",
            "label": stats_label,
            "detail": f"{total:,} fighters known.",
            "total": total,
            "with_stats": with_stats,
            "age_days": None,
        }

    freshness = "updated today" if age_days == 0 else f"updated {age_days}d ago"
    stale = age_days >= STALE_AFTER_DAYS
    return {
        "level": "warn" if stale else "ok",
        "label": f"{stats_label}, {freshness}",
        "detail": (
            f"{total:,} fighters known. Stats are over {STALE_AFTER_DAYS} days old - "
            "run Sync Now in Settings to refresh."
            if stale
            else f"{total:,} fighters known."
        ),
        "total": total,
        "with_stats": with_stats,
        "age_days": age_days,
    }


def fighter_db_detail() -> dict:
    """Prose for the Settings -> Fighter Database card.

    Built on fighter_db_status()'s measured counts, deliberately, because
    the card used to read the `last_fighter_sync_at` setting instead. That
    setting is only written by a user-triggered sync, so a seeded install
    has none - and the card told those users "Never synced - predictions
    won't have real stats until you sync" while the dashboard, querying the
    same table, reported thousands of fighters with stats. Two surfaces,
    one database, opposite answers, and the wrong one sat next to the
    button that starts a multi-hour scrape.

    Returns a chip label matching the dashboard's, plus the one thing the
    old card never said: whether syncing would actually fetch anything.
    """
    status = fighter_db_status()
    total = status["total"]
    with_stats = status["with_stats"]
    age_days = status["age_days"]

    if not total or not with_stats:
        return {
            "level": "err",
            "chip": "No fighter stats loaded",
            "advice": (
                "Predictions have no real numbers to reason about until this is filled in. "
                "The app ships with a database included, so an empty one usually means the "
                "data folder was cleared - Sync Now rebuilds it from ufc.com."
            ),
        }

    missing = total - with_stats
    chip = f"{with_stats:,} of {total:,} fighters have career stats"
    if age_days is not None:
        chip += " · scraped today" if age_days == 0 else f" · scraped {age_days}d ago"

    if age_days is not None and age_days >= STALE_AFTER_DAYS:
        advice = f"These are more than {STALE_AFTER_DAYS} days old, so Sync Now will refresh them"
        advice += (
            f", and fill in the {missing:,} fighters that still have only a name and record."
            if missing
            else "."
        )
    elif missing:
        advice = (
            f"The remaining {missing:,} are known by name and record but have no striking or "
            "grappling numbers yet, so predictions involving them lean on the model instead of "
            "the data. Sync Now fetches the ones that are missing."
        )
    else:
        advice = (
            "Every fighter on record has full stats and they are recent, so there is nothing "
            f"to fetch until they age past {STALE_AFTER_DAYS} days."
        )

    return {"level": status["level"], "chip": chip, "advice": advice}


def provider_status() -> dict:
    """Whether the configured AI provider is actually usable right now.

    For Ollama that means the daemon answers and has at least one model
    pulled; for the hosted providers it means an API key is stored. Neither
    check spends tokens or runs inference - Settings -> Test Connection is
    the deliberate, user-initiated version of that.
    """
    name = get_setting(KEY_ACTIVE_PROVIDER, default="ollama")
    label = PROVIDER_LABELS.get(name, name)

    if name == "ollama":
        return _ollama_status(label)

    if secret_manager.has_key(name):
        return {"level": "ok", "label": f"{label} - API key set", "provider": name}
    return {
        "level": "err",
        "label": f"{label} - no API key",
        "detail": f"Add your {label} API key in Settings, or switch to Ollama to run locally.",
        "provider": name,
    }


def _ollama_status(label: str) -> dict:
    try:
        resp = requests.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=2)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
    except requests.exceptions.RequestException:
        return {
            "level": "err",
            "label": f"{label} - not running",
            "detail": (
                f"Nothing is answering at {Config.OLLAMA_BASE_URL}. Start Ollama, or "
                "switch to a hosted provider in Settings."
            ),
            "provider": "ollama",
        }

    if not models:
        return {
            "level": "warn",
            "label": f"{label} - no models pulled",
            "detail": "Ollama is running but has no models. Run `ollama pull llama3.1`.",
            "provider": "ollama",
        }

    selected = get_setting(KEY_ACTIVE_OLLAMA_MODEL, default="")
    # Ollama reports models tag-qualified ("llama3.1:latest"); a bare name
    # the user picked earlier should still count as present.
    if selected and not any(m == selected or m.split(":")[0] == selected.split(":")[0] for m in models):
        return {
            "level": "warn",
            "label": f"{label} - '{selected}' not pulled",
            "detail": f"Selected model isn't installed. Run `ollama pull {selected}` or pick another in Settings.",
            "provider": "ollama",
        }

    return {
        "level": "ok",
        "label": f"{label} - {selected or models[0]}",
        "provider": "ollama",
    }
