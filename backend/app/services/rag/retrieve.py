"""Two distinct retrieval modes, not conflated:

- Betting pages already resolve fighters to a specific `ufc_slug` via the
  autocomplete endpoint, so `get_context_by_slugs` is a deterministic
  `collection.get(ids=...)` - no risk of retrieving the wrong fighter.
- The chatbot fuzzy-matches fighter names mentioned in free text against the
  SQLite `fighters` table (see blueprints/chat/routes.py), then calls this
  same deterministic lookup with the matched slugs. There is no semantic
  `collection.query()` path in v1 - see docs/SPEC.md section 8 for why.
"""
from __future__ import annotations

from app.services.rag.chroma_client import get_fighters_collection


def get_context_by_slugs(slugs: list[str]) -> dict[str, str]:
    """Returns {slug: document_text} for whichever of the given slugs exist
    in the collection. Missing slugs are silently omitted, not errored -
    callers should handle a fighter with no ingested stats yet.
    """
    slugs = [s for s in slugs if s]
    if not slugs:
        return {}
    collection = get_fighters_collection()
    result = collection.get(ids=slugs)
    ids = result.get("ids", [])
    documents = result.get("documents", [])
    return dict(zip(ids, documents))
