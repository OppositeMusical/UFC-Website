"""Deterministic fuzzy-match of fighter names mentioned in free text.

Used instead of model-driven tool-calling so context injection behaves
identically for Ollama and every cloud provider - the local-first pitch
depends on answer quality not varying by provider. See docs/SPEC.md
section 8.

Shared by the chat blueprint and the Kalshi free-text market endpoint,
which both take arbitrary prose and need whatever fighters it names.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process as fuzz_process

from app.models.fighter import Fighter
from app.services.rag.retrieve import get_context_by_slugs

# Below this the matcher starts pulling in unrelated fighters on common
# words; a question naming nobody should return nothing rather than a
# near-miss the model would then reason from.
SCORE_CUTOFF = 85

# Per-token bar for the confirmation pass below. Loose enough to survive a
# typo ("Jon Jons" -> "Jones" scores 89), tight enough to reject a different
# person who merely shares a surname.
TOKEN_MATCH_CUTOFF = 85

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def find_mentioned_fighters(session, text: str, limit: int = 2) -> list[Fighter]:
    names = [row[0] for row in session.query(Fighter.name).all()]
    if not names:
        return []

    # Recall first, precision second.
    #
    # partial_ratio + str.lower, because the name is short and the text is a
    # whole sentence: the previous default (WRatio, no processor) scored a
    # short name against a long question poorly and was case-sensitive, so
    # "how good is jon jons at wrestling" matched nobody at all.
    #
    # Then confirm, because the fuzzy pass alone matches on a surname: "Will
    # Jon Jones win by KO?" also returned Antonio Jones and Carlton Jones,
    # whose stats went into the prompt as though they were participants -
    # the model duly explained that Jon's "opponent Carlton Jones" is a
    # grappling specialist. Every part of a name must actually appear before
    # a fighter counts as mentioned.
    candidates = fuzz_process.extract(
        text,
        names,
        scorer=fuzz.partial_ratio,
        processor=str.lower,
        score_cutoff=SCORE_CUTOFF,
        limit=limit * 8,
    )
    text_tokens = _TOKEN_RE.findall(text.lower())
    confirmed = [name for name, _score, _i in candidates if _all_name_parts_present(name, text_tokens)]

    matched_names = confirmed[:limit]
    if not matched_names:
        return []
    return session.query(Fighter).filter(Fighter.name.in_(matched_names)).all()


def _all_name_parts_present(name: str, text_tokens: list[str]) -> bool:
    parts = [p for p in _TOKEN_RE.findall(name.lower()) if len(p) > 2]
    if not parts:
        return False
    return all(
        any(fuzz.ratio(part, token) >= TOKEN_MATCH_CUTOFF for token in text_tokens) for part in parts
    )


def build_context_block(fighters: list[Fighter]) -> str:
    """Chroma-backed stat summaries for the given fighters, one per line.

    Falls back to the SQLite row's own summary when a fighter has no vector
    yet (possible for anyone added by a roster sync but not detail-scraped).
    """
    if not fighters:
        return ""
    context = get_context_by_slugs([f.ufc_slug for f in fighters])
    return "\n".join(context.get(f.ufc_slug, f.to_summary_text()) for f in fighters)
