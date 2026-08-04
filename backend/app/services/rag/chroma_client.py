from __future__ import annotations

import chromadb

from app.config import Config
from app.services.rag.embeddings import get_embedding_function

COLLECTION_NAME = "fighters"

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(Config.chroma_dir()))
    return _client


def get_fighters_collection():
    global _collection
    if _collection is None:
        _collection = get_client().get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=get_embedding_function(),
        )
    return _collection


def reset_for_tests() -> None:
    """Used by pytest fixtures to force a fresh client/collection against a
    tmp_path-backed Config.chroma_dir() between test cases.
    """
    global _client, _collection
    _client = None
    _collection = None
