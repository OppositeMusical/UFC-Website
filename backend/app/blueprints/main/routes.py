from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from app.extensions import Session
from app.models.market_prediction import MarketPrediction
from app.models.prediction import Prediction
from app.services.odds import format_moneyline
from app.services.status import fighter_db_status, provider_status
from app.services.updates import check_for_update
from app.version import get_current_version

bp = Blueprint("main", __name__)


RECENT_LIMIT = 5


def _recent_rows(session, limit: int = RECENT_LIMIT) -> list[dict]:
    """The two prediction kinds, merged into one newest-first list.

    Stat props and priced markets live in separate tables (see
    models/market_prediction.py) but they are the same thing to a user
    looking at "what did I ask about recently". Flattening them here rather
    than in the template keeps Jinja from having to know which is which.

    joinedload, not lazy: the template renders both fighters' names for every
    row, so this is 1 query instead of 1+2N - and it means the rows carry
    their data rather than needing a live session at render time, which is
    what broke this page once predictions existed.
    """
    props = (
        session.query(Prediction)
        .options(joinedload(Prediction.fighter_a), joinedload(Prediction.fighter_b))
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
    markets = (
        session.query(MarketPrediction)
        .options(joinedload(MarketPrediction.fighter_a), joinedload(MarketPrediction.fighter_b))
        .order_by(MarketPrediction.created_at.desc())
        .limit(limit)
        .all()
    )

    rows = [
        {
            "created_at": p.created_at,
            "platform": p.platform,
            "matchup": f"{p.fighter_a.name} vs {p.fighter_b.name}",
            "market": f"{p.stat_category.replace('_', ' ').title()} @ {p.line_value}",
            "call": p.direction_predicted.upper(),
            "call_class": p.direction_predicted,
            "figure": f"{p.confidence_pct}% confidence",
            "conversation_id": p.conversation_id,
        }
        for p in props
    ] + [
        {
            "created_at": m.created_at,
            "platform": m.platform,
            "matchup": f"{m.fighter_a.name} vs {m.fighter_b.name}",
            "market": m.question,
            "call": format_moneyline(m.moneyline),
            "call_class": m.verdict,
            "figure": f"{m.model_probability_pct}% vs {m.implied_probability_pct}% implied",
            "conversation_id": m.conversation_id,
        }
        for m in markets
    ]

    # Each query was already limited, so this sorts at most 2*limit rows.
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return rows[:limit]


@bp.route("/")
def dashboard():
    session = Session()
    try:
        recent_predictions = _recent_rows(session)
        # The provider chip is filled in by JS from /api/status/provider
        # instead of being rendered here: checking it means a network call
        # (is Ollama up? is a key in the keyring?) and the dashboard
        # shouldn't stall behind that.
        return render_template(
            "index.html",
            db_status=fighter_db_status(),
            recent_predictions=recent_predictions,
            prediction_count=(
                session.query(Prediction).count() + session.query(MarketPrediction).count()
            ),
        )
    finally:
        Session.remove()


@bp.route("/api/status/provider")
def api_provider_status():
    return jsonify(provider_status())


@bp.route("/api/updates/check")
def api_check_updates():
    # ?force=1 bypasses the 6h cache, for the explicit "Check now" button in
    # Settings - a user who just published a release shouldn't have to wait
    # out the cache to see it.
    force = request.args.get("force") == "1"
    return jsonify(check_for_update(force=force))


@bp.route("/health")
def health():
    return {"status": "ok"}
