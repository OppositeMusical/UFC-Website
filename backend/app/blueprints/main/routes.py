from __future__ import annotations

from flask import Blueprint, jsonify, render_template
from sqlalchemy.orm import joinedload

from app.extensions import Session
from app.models.prediction import Prediction
from app.services.status import fighter_db_status, provider_status

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    session = Session()
    try:
        # joinedload, not lazy: the template renders both fighters' names for
        # every row, so this is 1 query instead of 1+2N - and it means the
        # rows carry their data rather than needing a live session at render
        # time, which is what broke this page once predictions existed.
        recent_predictions = (
            session.query(Prediction)
            .options(joinedload(Prediction.fighter_a), joinedload(Prediction.fighter_b))
            .order_by(Prediction.created_at.desc())
            .limit(5)
            .all()
        )
        # The provider chip is filled in by JS from /api/status/provider
        # instead of being rendered here: checking it means a network call
        # (is Ollama up? is a key in the keyring?) and the dashboard
        # shouldn't stall behind that.
        return render_template(
            "index.html",
            db_status=fighter_db_status(),
            recent_predictions=recent_predictions,
            prediction_count=session.query(Prediction).count(),
        )
    finally:
        Session.remove()


@bp.route("/api/status/provider")
def api_provider_status():
    return jsonify(provider_status())


@bp.route("/health")
def health():
    return {"status": "ok"}
