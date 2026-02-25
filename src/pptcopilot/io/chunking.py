"""Chunking utilities for retrieval."""

from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def chunk_tokens(tokens: list[str], *, chunk_size: int, overlap: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not tokens:
        return [[]]

    chunks: list[list[str]] = []
    step = chunk_size - overlap
    for start in range(0, len(tokens), step):
        piece = tokens[start : start + chunk_size]
        if not piece:
            continue
        chunks.append(piece)
        if start + chunk_size >= len(tokens):
            break
    return chunks


def chunk_record(
    record: dict[str, object],
    *,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
) -> list[dict[str, object]]:
    slide_text = str(record.get("slide_text", "")).strip()
    notes_text = str(record.get("notes_text", "")).strip()
    combined = " ".join(x for x in [slide_text, notes_text] if x).strip()
    tokens = tokenize(combined)
    token_chunks = chunk_tokens(
        tokens,
        chunk_size=chunk_size_tokens,
        overlap=chunk_overlap_tokens,
    )

    chunks: list[dict[str, object]] = []
    slide_id = str(record.get("slide_id", ""))
    for idx, tok_chunk in enumerate(token_chunks):
        chunk_text = " ".join(tok_chunk).strip()
        if not chunk_text:
            chunk_text = "(empty)"
        chunks.append(
            {
                "chunk_id": f"{slide_id}_c{idx:03d}",
                "doc_id": str(record.get("doc_id", "")),
                "slide_id": slide_id,
                "chunk_index": idx,
                "chunk_text": chunk_text,
                "title": str(record.get("title", "")),
            }
        )
    return chunks
