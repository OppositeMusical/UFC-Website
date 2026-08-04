from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from app.blueprints.betting.platforms import get_platform
from app.extensions import Session
from app.models.conversation import Conversation
from app.models.fighter import Fighter
from app.models.message import Message
from app.models.prediction import Prediction
from app.services.ai.base import ProviderError
from app.services.ai.factory import get_active_provider
from app.services.ai.prompts import (
    MARKET_PROBABILITY_SYSTEM_PROMPT,
    PREDICTION_SYSTEM_PROMPT,
    build_market_probability_prompt,
    build_prediction_prompt,
    parse_prediction_response,
    parse_probability_response,
)
from app.services.fighter_mentions import build_context_block, find_mentioned_fighters
from app.services.rag.retrieve import get_context_by_slugs

MAX_QUESTION_CHARS = 500

bp = Blueprint("betting", __name__, url_prefix="/betting")


@bp.route("/<platform>")
def form(platform: str):
    config = get_platform(platform)
    if config is None:
        abort(404)
    return render_template("betting/form.html", platform=platform, config=config)


@bp.route("/<platform>/market-probability", methods=["POST"])
def market_probability(platform: str):
    """Free-text event-contract question -> probability estimate.

    Deliberately does not write a Prediction row: that table requires two
    fighters, a stat category and a numeric line, none of which a question
    like "will this fight end inside the distance?" necessarily has. Forcing
    one in would mean inventing values. A Conversation plus its opening
    assistant message is written instead, so the estimate is saved and
    "Continue in Chat" works exactly as it does for a stat prop.
    """
    config = get_platform(platform)
    if config is None:
        abort(404)
    if not config.get("supports_market_question"):
        return jsonify({"error": f"{config['display_name']} does not support market questions"}), 400

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > MAX_QUESTION_CHARS:
        return jsonify({"error": f"question must be {MAX_QUESTION_CHARS} characters or fewer"}), 400

    session = Session()
    try:
        # Whoever the question names gets their stats injected. A question
        # naming nobody still goes through - the system prompt tells the
        # model to widen its uncertainty rather than invent support.
        mentioned = find_mentioned_fighters(session, question, limit=3)
        prompt = build_market_probability_prompt(
            question=question,
            fighter_context_block=build_context_block(mentioned),
        )

        try:
            provider = get_active_provider()
            raw = provider.generate(
                messages=[{"role": "user", "content": prompt}],
                system=MARKET_PROBABILITY_SYSTEM_PROMPT,
                json_mode=True,
            )
            parsed = parse_probability_response(raw)
        except ProviderError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": f"Could not parse a probability from the AI response: {exc}"}), 502

        title = question if len(question) <= 60 else question[:57] + "..."
        conversation = Conversation(title=f"Kalshi: {title}", platform=platform)
        session.add(conversation)
        session.flush()

        matched_note = (
            "Matched fighter stats: " + ", ".join(f.name for f in mentioned)
            if mentioned
            else "No fighter in the database matched this question, so this estimate is not stat-grounded."
        )
        summary = (
            f"Market: {question}\n\n"
            f"Estimated probability: {parsed['probability_pct']}% YES.\n\n"
            f"{parsed['reasoning']}\n\n{matched_note}"
        )
        session.add(Message(conversation_id=conversation.id, role="assistant", content=summary))
        session.commit()

        return jsonify(
            {
                "conversation_id": conversation.id,
                "probability_pct": parsed["probability_pct"],
                "reasoning": parsed["reasoning"],
                "matched_fighters": [f.name for f in mentioned],
            }
        )
    finally:
        Session.remove()


@bp.route("/<platform>/predict", methods=["POST"])
def predict(platform: str):
    config = get_platform(platform)
    if config is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    fighter_a_id = payload.get("fighter_a_id")
    fighter_b_id = payload.get("fighter_b_id")
    stat_category = payload.get("stat_category")
    line_value = payload.get("line_value")

    if not all([fighter_a_id, fighter_b_id, stat_category]) or line_value is None:
        return (
            jsonify({"error": "fighter_a_id, fighter_b_id, stat_category, and line_value are required"}),
            400,
        )
    try:
        line_value = float(line_value)
    except (TypeError, ValueError):
        return jsonify({"error": "line_value must be a number"}), 400

    valid_categories = {c.value for c in config["stat_categories"]}
    if stat_category not in valid_categories:
        return jsonify({"error": f"stat_category must be one of {sorted(valid_categories)}"}), 400

    session = Session()
    try:
        fighter_a = session.get(Fighter, fighter_a_id)
        fighter_b = session.get(Fighter, fighter_b_id)
        if fighter_a is None or fighter_b is None:
            return jsonify({"error": "unknown fighter_a_id or fighter_b_id"}), 400

        context = get_context_by_slugs([fighter_a.ufc_slug, fighter_b.ufc_slug])
        fighter_a_context = context.get(fighter_a.ufc_slug, fighter_a.to_summary_text())
        fighter_b_context = context.get(fighter_b.ufc_slug, fighter_b.to_summary_text())

        stat_label = next(c.label for c in config["stat_categories"] if c.value == stat_category)
        prompt = build_prediction_prompt(
            platform=config["display_name"],
            stat_category_label=stat_label,
            line_value=line_value,
            fighter_a_name=fighter_a.name,
            fighter_a_context=fighter_a_context,
            fighter_b_name=fighter_b.name,
            fighter_b_context=fighter_b_context,
        )

        try:
            provider = get_active_provider()
            raw = provider.generate(
                messages=[{"role": "user", "content": prompt}],
                system=PREDICTION_SYSTEM_PROMPT,
                json_mode=True,
            )
            parsed = parse_prediction_response(raw)
        except ProviderError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": f"Could not parse a prediction from the AI response: {exc}"}), 502

        conversation = Conversation(
            title=f"{config['display_name']}: {fighter_a.name} vs {fighter_b.name}",
            platform=platform,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
        )
        session.add(conversation)
        session.flush()

        prediction = Prediction(
            conversation_id=conversation.id,
            platform=platform,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            stat_category=stat_category,
            line_value=line_value,
            direction_predicted=parsed["direction"],
            confidence_pct=parsed["confidence_pct"],
            reasoning=parsed["reasoning"],
        )
        session.add(prediction)

        summary = (
            f"Prediction for {fighter_a.name} — {stat_label}, line {line_value}: "
            f"{parsed['direction'].upper()} ({parsed['confidence_pct']}% confidence).\n\n{parsed['reasoning']}"
        )
        session.add(Message(conversation_id=conversation.id, role="assistant", content=summary))
        session.commit()

        return jsonify(
            {
                "conversation_id": conversation.id,
                "prediction": {
                    "direction": parsed["direction"],
                    "confidence_pct": parsed["confidence_pct"],
                    "reasoning": parsed["reasoning"],
                },
                "fighter_a": {"name": fighter_a.name, "record": fighter_a.record},
                "fighter_b": {"name": fighter_b.name, "record": fighter_b.record},
            }
        )
    finally:
        Session.remove()
