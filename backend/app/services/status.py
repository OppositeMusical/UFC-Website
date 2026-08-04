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
