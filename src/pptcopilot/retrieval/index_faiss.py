"""Build retrieval indices for the hash baseline or real dense retrieval."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.config import get_retrieval_defaults
from pptcopilot.io.chunking import chunk_record
from pptcopilot.io.ingest_pptx import validate_records
from pptcopilot.retrieval.embed import embed_dense_texts, embed_texts

CHUNKS_FILE = "chunks.jsonl"
EMBEDDINGS_FILE = "embeddings.json"
METADATA_FILE = "metadata.json"
FAISS_FILE = "index.faiss"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_json(payload: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_faiss(
    embeddings: list[list[float]],
    *,
    dimension: int,
    output_path: Path,
    required: bool,
) -> bool:
    try:
        import faiss  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        if required:
            raise RuntimeError(
                "Dense retrieval requires FAISS and numpy. "
                "Install with: python -m pip install -e '.[rag]'"
            ) from exc
        return False

    arr = np.asarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(dimension)
    index.add(arr)
    faiss.write_index(index, str(output_path))
    return True


def build_index(
    input_jsonl: str | Path,
    index_dir: str | Path,
    *,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
    embedding_dim: int | None = None,
    retriever: str = "hash",
    embedding_model: str | None = None,
) -> dict[str, object]:
    """Build an index.

    retriever="hash" preserves the deterministic baseline. retriever="dense"
    uses a real SentenceTransformer model and requires FAISS.
    """
    defaults = get_retrieval_defaults()
    chunk_size_tokens = (
        defaults.chunk_size_tokens if chunk_size_tokens is None else chunk_size_tokens
    )
    chunk_overlap_tokens = (
        defaults.chunk_overlap_tokens if chunk_overlap_tokens is None else chunk_overlap_tokens
    )
    embedding_dim = defaults.embedding_dim if embedding_dim is None else embedding_dim
    retriever = retriever.strip().lower()
    if retriever not in {"hash", "dense"}:
        raise ValueError("retriever must be 'hash' or 'dense'")

    input_path = Path(input_jsonl)
    out_dir = Path(index_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = _read_jsonl(input_path)
    validate_records(records)

    chunks: list[dict[str, object]] = []
    for record in records:
        chunks.extend(
            chunk_record(
                record,
                chunk_size_tokens=chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
            )
        )
    if not chunks:
        raise ValueError("No chunks generated from input records")

    texts = [str(c["chunk_text"]) for c in chunks]
    actual_embedding_model: str | None = None
    if retriever == "dense":
        actual_embedding_model = embedding_model or defaults.dense_embedding_model
        embeddings = embed_dense_texts(texts, model_name=actual_embedding_model)
        actual_dim = len(embeddings[0])
        _write_faiss(
            embeddings,
            dimension=actual_dim,
            output_path=out_dir / FAISS_FILE,
            required=True,
        )
        backend = "faiss"
        if (out_dir / EMBEDDINGS_FILE).exists():
            (out_dir / EMBEDDINGS_FILE).unlink()
    else:
        embeddings = embed_texts(texts, dim=embedding_dim)
        actual_dim = embedding_dim
        faiss_available = _write_faiss(
            embeddings,
            dimension=actual_dim,
            output_path=out_dir / FAISS_FILE,
            required=False,
        )
        backend = "faiss" if faiss_available else "bruteforce"
        if not faiss_available:
            _write_json({"embeddings": embeddings}, out_dir / EMBEDDINGS_FILE)

    _write_jsonl(chunks, out_dir / CHUNKS_FILE)
    metadata = {
        "input_jsonl": str(input_path.resolve()),
        "index_dir": str(out_dir.resolve()),
        "retriever": retriever,
        "backend": backend,
        "embedding_model": actual_embedding_model,
        "n_records": len(records),
        "n_chunks": len(chunks),
        "chunk_size_tokens": chunk_size_tokens,
        "chunk_overlap_tokens": chunk_overlap_tokens,
        "embedding_dim": actual_dim,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(metadata, out_dir / METADATA_FILE)
    return metadata
