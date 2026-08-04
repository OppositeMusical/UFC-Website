from __future__ import annotations

from app.models.fighter import Fighter
from app.services.rag.chroma_client import get_fighters_collection


def upsert_fighter(fighter: Fighter) -> None:
    collection = get_fighters_collection()
    collection.upsert(
        ids=[fighter.ufc_slug],
        documents=[fighter.to_summary_text()],
        metadatas=[fighter.to_metadata()],
    )


def upsert_fighters(fighters: list[Fighter]) -> None:
    if not fighters:
        return
    collection = get_fighters_collection()
    collection.upsert(
        ids=[f.ufc_slug for f in fighters],
        documents=[f.to_summary_text() for f in fighters],
        metadatas=[f.to_metadata() for f in fighters],
    )
