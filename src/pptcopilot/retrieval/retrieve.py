"""Query a retrieval index and return top-k slide chunks."""

from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.retrieval.embed import embed_dense_text, embed_text
from pptcopilot.retrieval.index_faiss import CHUNKS_FILE, EMBEDDINGS_FILE, FAISS_FILE, METADATA_FILE


def _dot(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def retrieve_top_k(index_dir: str | Path, question: str, *, top_k: int) -> dict[str, object]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    root = Path(index_dir)
    metadata = _read_json(root / METADATA_FILE)
    chunks = _read_jsonl(root / CHUNKS_FILE)
    dim = int(metadata["embedding_dim"])
    retriever = str(metadata.get("retriever", "hash"))
    backend = str(metadata["backend"])

    if retriever == "dense":
        model_name = str(metadata.get("embedding_model") or "")
        if not model_name:
            raise RuntimeError("Dense index metadata is missing embedding_model")
        qvec = embed_dense_text(question, model_name=model_name)
    else:
        qvec = embed_text(question, dim=dim)

    scored: list[tuple[int, float]] = []
    if backend == "faiss" and (root / FAISS_FILE).exists():
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "FAISS index exists but faiss/numpy are not installed. "
                "Install with: python -m pip install -e '.[rag]'"
            ) from exc

        index = faiss.read_index(str(root / FAISS_FILE))
        qarr = np.asarray([qvec], dtype="float32")
        scores, indices = index.search(qarr, min(top_k, len(chunks)))
        for i, score in zip(indices[0], scores[0]):
            if i >= 0:
                scored.append((int(i), float(score)))
    else:
        if retriever == "dense":
            raise RuntimeError("Dense retrieval requires a persisted FAISS index")
        embeddings_payload = _read_json(root / EMBEDDINGS_FILE)
        embeddings = embeddings_payload["embeddings"]
        pairs = []
        for idx, emb in enumerate(embeddings):
            score = _dot(qvec, [float(x) for x in emb])
            pairs.append((idx, score))
        pairs.sort(key=lambda x: x[1], reverse=True)
        scored = pairs[: min(top_k, len(pairs))]
        backend = "bruteforce"

    results: list[dict[str, object]] = []
    for rank, (idx, score) in enumerate(scored, start=1):
        chunk = chunks[idx]
        results.append(
            {
                "rank": rank,
                "score": round(float(score), 6),
                "chunk_id": chunk["chunk_id"],
                "slide_id": chunk["slide_id"],
                "doc_id": chunk["doc_id"],
                "chunk_text": chunk["chunk_text"],
                "title": chunk.get("title", ""),
            }
        )
    return {"retriever": retriever, "backend": backend, "hits": results}
