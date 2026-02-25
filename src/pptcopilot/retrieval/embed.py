"""Deterministic text embeddings for retrieval."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable

from pptcopilot.io.chunking import tokenize


def _hash_token(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def embed_text(text: str, *, dim: int) -> list[float]:
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
    return [embed_text(text, dim=dim) for text in texts]
