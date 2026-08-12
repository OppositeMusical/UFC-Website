from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from app.blueprints.betting.markets import (
    FIGHT_MARKET_FORMS,
    FIVE_ROUND_ONLY,
    InvalidMarket,
    describe,
    parse_market,
)
from app.blueprints.betting.platforms import get_platform
from app.extensions import Session
from app.models.conversation import Conversation
from app.models.fighter import Fighter
from app.models.market_prediction import MarketPrediction
from app.models.message import Message
from app.models.prediction import Prediction
from app.services.ai.base import ProviderError
from app.services.ai.factory import get_active_provider
from app.services.ai.prompts import (
    FIGHT_MARKET_SYSTEM_PROMPT,
    MARKET_PROBABILITY_SYSTEM_PROMPT,
    PREDICTION_SYSTEM_PROMPT,
    build_fight_market_prompt,
    build_market_probability_prompt,
    build_prediction_prompt,
    parse_prediction_response,
    parse_probability_response,
)
from app.services.fighter_mentions import build_context_block, find_mentioned_fighters
from app.services.odds import InvalidMoneyline, assess, parse_moneyline
from app.services.rag.retrieve import get_context_by_slugs

MAX_QUESTION_CHARS = 500

bp = Blueprint("betting", __name__, url_prefix="/betting")


def _platform_or_404(platform: str) -> dict:
    config = get_platform(platform)
    if config is None:
        abort(404)
    return config


def _ask_model(prompt: str, system: str, parse, noun: str):
    """Runs the active provider in JSON mode and parses the reply.

    Returns (parsed, None) on success, or (None, error_response) for the two
    failures every betting route handles identically: the provider being
    unusable, and a reply that doesn't parse. Both are 502s - the request
    was fine, the AI side wasn't - and `noun` names what the parser was
    looking for so the message says which route's contract was broken.
    """
    try:
        raw = get_active_provider().generate(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            json_mode=True,
        )
        return parse(raw), None
    except ProviderError as exc:
        return None, (jsonify({"error": str(exc)}), 502)
    except ValueError as exc:
        return None, (
            jsonify({"error": f"Could not parse a {noun} from the AI response: {exc}"}),
            502,
        )


@bp.route("/<platform>")
def form(platform: str):
    config = _platform_or_404(platform)
    return render_template(
        "betting/form.html",
        platform=platform,
        config=config,
        fight_markets=FIGHT_MARKET_FORMS if config.get("supports_fight_markets") else (),
        five_round_only=FIVE_ROUND_ONLY,
    )


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
    config = _platform_or_404(platform)
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

        parsed, error = _ask_model(
            prompt, MARKET_PROBABILITY_SYSTEM_PROMPT, parse_probability_response, "probability"
        )
        if error:
            return error

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


@bp.route("/<platform>/market", methods=["POST"])
def fight_market(platform: str):
    """Prices one of the three moneyline markets (see betting/markets.py).

    The order here matters and is the point of the feature: the model is
    asked for a probability from the fighters' stats *without being shown the
    moneyline*, and only then is the price compared against it. Handing the
    model the odds first would collapse the comparison into a paraphrase of
    the book - see build_fight_market_prompt.
    """
    config = _platform_or_404(platform)
    if not config.get("supports_fight_markets"):
        return jsonify({"error": f"{config['display_name']} does not offer moneyline markets"}), 400

    payload = request.get_json(silent=True) or {}
    fighter_a_id = payload.get("fighter_a_id")
    fighter_b_id = payload.get("fighter_b_id")
    if not fighter_a_id or not fighter_b_id:
        return jsonify({"error": "fighter_a_id and fighter_b_id are required"}), 400

    try:
        market = parse_market(payload)
        moneyline = parse_moneyline(payload.get("moneyline"))
    except (InvalidMarket, InvalidMoneyline) as exc:
        return jsonify({"error": str(exc)}), 400

    session = Session()
    try:
        fighter_a = session.get(Fighter, fighter_a_id)
        fighter_b = session.get(Fighter, fighter_b_id)
        if fighter_a is None or fighter_b is None:
            return jsonify({"error": "unknown fighter_a_id or fighter_b_id"}), 400

        context = get_context_by_slugs([fighter_a.ufc_slug, fighter_b.ufc_slug])
        question = describe(
            market_type=market["market_type"],
            fighter_a_name=fighter_a.name,
            fighter_b_name=fighter_b.name,
            method=market["method"],
            round_number=market["round_number"],
        )
        prompt = build_fight_market_prompt(
            question=question,
            fighter_a_name=fighter_a.name,
            fighter_a_context=context.get(fighter_a.ufc_slug, fighter_a.to_summary_text()),
            fighter_b_name=fighter_b.name,
            fighter_b_context=context.get(fighter_b.ufc_slug, fighter_b.to_summary_text()),
        )

        parsed, error = _ask_model(
            prompt, FIGHT_MARKET_SYSTEM_PROMPT, parse_probability_response, "probability"
        )
        if error:
            return error

        priced = assess(moneyline, parsed["probability_pct"])

        conversation = Conversation(
            title=f"{config['display_name']}: {question}",
            platform=platform,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
        )
        session.add(conversation)
        session.flush()

        session.add(
            MarketPrediction(
                conversation_id=conversation.id,
                platform=platform,
                fighter_a_id=fighter_a.id,
                fighter_b_id=fighter_b.id,
                market_type=market["market_type"].value,
                victory_method=market["method"].value if market["method"] else None,
                round_number=market["round_number"],
                question=question,
                moneyline=moneyline,
                model_probability_pct=priced["modelProbabilityPct"],
                implied_probability_pct=priced["impliedProbabilityPct"],
                edge_pct=priced["edgePct"],
                verdict=priced["verdict"],
                reasoning=parsed["reasoning"],
            )
        )

        summary = (
            f"{question}\n\n"
            f"Model probability: {priced['modelProbabilityPct']}%. "
            f"Price {priced['moneyline_display']} implies "
            f"{priced['impliedProbabilityPct']}%. "
            f"{priced['verdictLabel']} ({priced['edgePct']:+.1f} points).\n\n"
            f"{parsed['reasoning']}"
        )
        session.add(Message(conversation_id=conversation.id, role="assistant", content=summary))
        session.commit()

        return jsonify(
            {
                "conversation_id": conversation.id,
                "question": question,
                "reasoning": parsed["reasoning"],
                **priced,
            }
        )
    finally:
        Session.remove()


@bp.route("/<platform>/predict", methods=["POST"])
def predict(platform: str):
    config = _platform_or_404(platform)

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

        parsed, error = _ask_model(prompt, PREDICTION_SYSTEM_PROMPT, parse_prediction_response, "prediction")
        if error:
            return error

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
