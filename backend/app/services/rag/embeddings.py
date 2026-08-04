"""ChromaDB's bundled default embedding function (ONNX MiniLM-L6-v2).

Deliberately not sentence-transformers/torch - that pulls multiple GB into a
PyInstaller build. The tradeoff: on first use, Chroma downloads a small ONNX
model file to a local cache directory. A packaged, possibly-offline install
must pre-seed that cache as part of the build (see docs/SPEC.md section 11)
or embedding will fail the first time with no internet access.
"""
from __future__ import annotations

from chromadb.utils import embedding_functions


def get_embedding_function():
    return embedding_functions.DefaultEmbeddingFunction()
