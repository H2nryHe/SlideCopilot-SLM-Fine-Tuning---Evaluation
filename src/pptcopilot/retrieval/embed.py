"""Embedding backends for retrieval.

The legacy hash embedding is intentionally retained as a deterministic baseline.
Dense retrieval uses a real SentenceTransformer model and L2-normalized vectors.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import math
from typing import Iterable

from pptcopilot.config import get_retrieval_defaults
from pptcopilot.io.chunking import tokenize


def _hash_token(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def embed_text(text: str, *, dim: int) -> list[float]:
    """Legacy deterministic hash embedding used for the baseline retriever."""
    if dim <= 0:
        raise ValueError("dim must be positive")
    vec = [0.0] * dim
    for token in tokenize(text):
        h = _hash_token(token)
        idx = h % dim
        sign = 1.0 if ((h >> 1) & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def embed_texts(texts: Iterable[str], *, dim: int) -> list[list[float]]:
    """Legacy deterministic hash embeddings used for baseline comparisons."""
    return [embed_text(text, dim=dim) for text in texts]


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Dense retrieval requires sentence-transformers. "
            "Install with: python -m pip install -e '.[rag]'"
        ) from exc
    return SentenceTransformer(model_name)


def embed_dense_texts(
    texts: Iterable[str],
    *,
    model_name: str | None = None,
) -> list[list[float]]:
    """Embed text with a real SentenceTransformer model.

    Embeddings are normalized so FAISS inner-product search is cosine similarity.
    """
    items = list(texts)
    if not items:
        return []
    model_name = model_name or get_retrieval_defaults().dense_embedding_model
    model = _load_sentence_transformer(model_name)
    arr = model.encode(
        items,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [[float(value) for value in row] for row in arr]


def embed_dense_text(text: str, *, model_name: str | None = None) -> list[float]:
    rows = embed_dense_texts([text], model_name=model_name)
    return rows[0]
