"""Query retrieval index and return top-k chunks."""

from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.retrieval.embed import embed_text
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
    qvec = embed_text(question, dim=dim)
    backend = str(metadata["backend"])

    scored: list[tuple[int, float]] = []
    if backend == "faiss" and (root / FAISS_FILE).exists():
        import faiss  # type: ignore
        import numpy as np  # type: ignore

        index = faiss.read_index(str(root / FAISS_FILE))
        qarr = np.array([qvec], dtype="float32")
        scores, indices = index.search(qarr, min(top_k, len(chunks)))
        for rank, (i, score) in enumerate(zip(indices[0], scores[0]), start=1):
            if i < 0:
                continue
            scored.append((int(i), float(score)))
    else:
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
    return {"backend": backend, "hits": results}
