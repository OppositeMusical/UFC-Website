from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.extensions import Session
from app.models.fighter import Fighter

bp = Blueprint("fighters", __name__, url_prefix="/api/fighters")


@bp.route("/autocomplete")
def autocomplete():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify([])
    session = Session()
    try:
        like = f"%{query}%"
        rows = (
            session.query(Fighter)
            .filter(or_(Fighter.name.ilike(like), Fighter.nickname.ilike(like)))
            .order_by(Fighter.name)
            .limit(15)
            .all()
        )
        return jsonify([{"id": f.id, "name": f.name, "weight_class": f.weight_class or ""} for f in rows])
    finally:
        Session.remove()
