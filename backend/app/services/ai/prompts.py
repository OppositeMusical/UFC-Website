"""System/user prompt construction for predictions and chat.

Kept in one place so every provider (Ollama included) receives the same
instructions - the app's local-first pitch depends on prediction quality not
depending on which provider is active.
"""
from __future__ import annotations

import json

DISCLAIMER = (
    "This analysis is for informational and entertainment purposes only. "
    "It is not financial or gambling advice."
)

PREDICTION_SYSTEM_PROMPT = (
    "You are an expert MMA analyst helping a user reason about a statistical "
    "prop for an upcoming fight. You are given real career stats for both "
    "fighters. Weigh the stats carefully, consider stance/style matchup and "
    "recent form when mentioned, and give a calibrated, honest confidence "
    "level - do not default to high confidence. "
    "Respond ONLY with a JSON object of the exact shape: "
    '{"direction": "over" or "under", "confidence_pct": integer 1-99, '
    '"reasoning": "2-4 sentence explanation citing specific stats"}. '
    "No text outside the JSON object."
)

MARKET_PROBABILITY_SYSTEM_PROMPT = (
    "You are an expert MMA analyst estimating the probability of a "
    "user-described event contract resolving YES. Kalshi-style markets are "
    "free-form, so the question may be about a method of victory, a round, a "
    "fight outcome, or a statistical threshold. Reason from the fighter "
    "statistics provided, and be honest about uncertainty: if the question "
    "cannot be judged from the stats available, say so in the reasoning and "
    "give a probability near 50 rather than inventing support for a "
    "confident answer. Never state a probability of 0 or 100. "
    "Respond ONLY with a JSON object of the exact shape: "
    '{"probability_pct": integer 1-99, "reasoning": "2-4 sentence '
    'explanation citing specific stats where they apply"}. '
    "No text outside the JSON object."
)

CHAT_SYSTEM_PROMPT = (
    "You are an MMA analytics assistant. You have access to real career "
    "statistics for UFC fighters when they're mentioned in the conversation "
    "(provided below as context, when available). Use that context to give "
    "specific, stat-grounded answers rather than generic commentary. If no "
    "fighter context is provided for a question that needs it, say so rather "
    "than guessing. Keep answers concise. " + DISCLAIMER
)


def build_prediction_prompt(
    *,
    platform: str,
    stat_category_label: str,
    line_value: float,
    fighter_a_name: str,
    fighter_a_context: str,
    fighter_b_name: str,
    fighter_b_context: str,
) -> str:
    return (
        f"Platform: {platform}\n"
        f"Prop: {fighter_a_name} — {stat_category_label}, line {line_value}\n"
        f"Opponent: {fighter_b_name}\n\n"
        f"{fighter_a_name} stats:\n{fighter_a_context}\n\n"
        f"{fighter_b_name} stats:\n{fighter_b_context}\n\n"
        f"Will {fighter_a_name}'s {stat_category_label} go over or under {line_value}? "
        "Respond with the JSON object described in your instructions."
    )


def build_market_probability_prompt(*, question: str, fighter_context_block: str) -> str:
    """Free-text Kalshi market question. Unlike the prop prompt there is no
    fixed pair of fighters - whoever the question names is matched against
    the database and their stats injected, and the block is empty when
    nobody matched (the system prompt tells the model to widen its
    uncertainty in that case rather than bluff).
    """
    context = fighter_context_block or "(No fighter stats matched this question.)"
    return (
        f"Market question: {question}\n\n"
        f"Available fighter stats:\n{context}\n\n"
        "Estimate the probability that this market resolves YES. "
        "Respond with the JSON object described in your instructions."
    )


def parse_prediction_response(raw: str) -> dict:
    """Strict-JSON-first, regex-fallback parser for prediction responses.

    Returns {"direction": "over"|"under", "confidence_pct": int, "reasoning": str}.
    Raises ValueError if nothing usable could be extracted.
    """
    return _parse_json_response(raw, _normalize_prediction, "prediction")


def parse_probability_response(raw: str) -> dict:
    """Same parsing strategy as predictions, different payload shape.

    Returns {"probability_pct": int, "reasoning": str}.
    """
    return _parse_json_response(raw, _normalize_probability, "probability")


def _parse_json_response(raw: str, normalize, label: str) -> dict:
    text = raw.strip()
    # Strip markdown code fences some models add despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return normalize(json.loads(text))
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: find the first {...} block and try again.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return normalize(json.loads(text[start : end + 1]))
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"Could not parse a {label} JSON object from model output: {raw[:200]!r}")


def _normalize_probability(data: dict) -> dict:
    raw_pct = data.get("probability_pct", data.get("probability"))
    try:
        # Models sometimes answer 0.62 instead of 62 despite the instructions.
        value = float(raw_pct)
    except (TypeError, ValueError):
        raise ValueError(f"invalid probability_pct: {raw_pct!r}") from None
    if 0 < value <= 1:
        value *= 100
    probability = max(1, min(99, int(round(value))))
    reasoning = str(data.get("reasoning", "")).strip() or "No reasoning provided."
    return {"probability_pct": probability, "reasoning": reasoning}


def _normalize_prediction(data: dict) -> dict:
    direction = str(data.get("direction", "")).strip().lower()
    if direction not in ("over", "under"):
        raise ValueError(f"invalid direction: {direction!r}")
    confidence = int(data.get("confidence_pct", 50))
    confidence = max(1, min(99, confidence))
    reasoning = str(data.get("reasoning", "")).strip() or "No reasoning provided."
    return {"direction": direction, "confidence_pct": confidence, "reasoning": reasoning}
