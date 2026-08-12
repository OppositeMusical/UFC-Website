from __future__ import annotations

import threading

from flask import Blueprint, jsonify, render_template, request

from app.config import Config
from app.extensions import Session
from app.models.app_setting import KEY_ACTIVE_OLLAMA_MODEL, KEY_ACTIVE_PROVIDER
from app.services.ai.base import ProviderError
from app.services.ai.factory import PROVIDER_NAMES, build_provider
from app.services.ai.ollama_provider import OllamaProvider
from app.services.db.session import get_setting, set_setting
from app.services.secrets import secret_manager
from app.services.status import fighter_db_detail
from app.version import get_current_version

bp = Blueprint("settings", __name__, url_prefix="/settings")

# In-memory only: a single background fighter-sync job at a time, reflecting
# progress back to the polling endpoint. Not persisted - a restart mid-sync
# just means the next click starts fresh (resumable via stats_scraped_at).
_sync_state = {"running": False, "done": 0, "total": 0, "last_error": None}
_sync_lock = threading.Lock()


@bp.route("/")
def index():
    active_provider = get_setting(KEY_ACTIVE_PROVIDER, default="ollama")
    active_ollama_model = get_setting(KEY_ACTIVE_OLLAMA_MODEL, default="")
    configured = {name: secret_manager.has_key(name) for name in PROVIDER_NAMES if name != "ollama"}
    # Deliberately not last_fighter_sync_at: that setting only exists after a
    # manual sync, so it reported "Never synced" on a seeded database. The
    # fighters table itself is the source of truth - see fighter_db_detail.
    return render_template(
        "settings.html",
        providers=PROVIDER_NAMES,
        active_provider=active_provider,
        active_ollama_model=active_ollama_model,
        configured=configured,
        db_detail=fighter_db_detail(),
        current_version=get_current_version(),
    )


@bp.route("/provider", methods=["POST"])
def set_provider():
    payload = request.get_json(silent=True) or {}
    provider = payload.get("provider")
    if provider not in PROVIDER_NAMES:
        return jsonify({"error": f"provider must be one of {PROVIDER_NAMES}"}), 400
    set_setting(KEY_ACTIVE_PROVIDER, provider)
    api_key = payload.get("api_key")
    if api_key:
        secret_manager.set_key(provider, api_key)
    model = payload.get("model")
    if provider == "ollama" and model:
        set_setting(KEY_ACTIVE_OLLAMA_MODEL, model)
    return jsonify({"ok": True})


@bp.route("/ollama/models")
def ollama_models():
    provider = OllamaProvider(base_url=Config.OLLAMA_BASE_URL, model="")
    return jsonify({"models": provider.list_models()})


@bp.route("/test-connection", methods=["POST"])
def test_connection():
    payload = request.get_json(silent=True) or {}
    provider_name = payload.get("provider") or get_setting(KEY_ACTIVE_PROVIDER, default="ollama")
    try:
        provider = build_provider(provider_name, model=payload.get("model"))
        reply = provider.generate(messages=[{"role": "user", "content": "Reply with the single word: OK"}])
        return jsonify({"ok": True, "reply": reply})
    except ProviderError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.route("/sync-fighters", methods=["POST"])
def sync_fighters():
    from app.services.scraper import pipeline

    with _sync_lock:
        if _sync_state["running"]:
            return jsonify({"error": "a sync is already running"}), 409
        _sync_state.update(running=True, done=0, total=0, last_error=None)

    def progress(done: int, total: int) -> None:
        _sync_state.update(done=done, total=total)

    def worker() -> None:
        try:
            pipeline.sync_roster()
            pipeline.scrape_details(progress_callback=progress)
        except Exception as exc:  # pragma: no cover - background thread
            _sync_state["last_error"] = str(exc)
        finally:
            _sync_state["running"] = False
            # No teardown_appcontext fires on this thread, so the
            # thread-local session the pipeline opened has to be released
            # here or it holds a sqlite connection for the process lifetime.
            Session.remove()

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/sync-fighters/status")
def sync_fighters_status():
    return jsonify(_sync_state)
