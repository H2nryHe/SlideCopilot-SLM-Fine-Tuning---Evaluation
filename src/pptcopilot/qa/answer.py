"""RAG-style QA using retrieved slide chunks and citations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.config import get_retrieval_defaults
from pptcopilot.qa.citations import unique_slide_citations
from pptcopilot.retrieval.retrieve import retrieve_top_k


def answer_question(
    *,
    index_dir: str | Path,
    question: str,
    top_k: int | None = None,
    debug: bool = False,
) -> dict[str, object]:
    defaults = get_retrieval_defaults()
    top_k = defaults.top_k if top_k is None else top_k
    retrieval = retrieve_top_k(index_dir, question, top_k=top_k)
    hits = retrieval["hits"]
    citations = unique_slide_citations(hits)

    if not hits:
        answer = "I could not find relevant slide context to answer this question."
    else:
        snippets = [str(h["chunk_text"]) for h in hits[:2]]
        answer = f"Based on retrieved slides: {' | '.join(snippets)}"

    payload: dict[str, object] = {
        "question": question,
        "answer": answer,
        "cited_slide_ids": citations,
        "metadata": {
            "top_k": top_k,
            "retrieval_backend": retrieval["backend"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    if debug:
        payload["retrieved_chunks"] = hits
    return payload


def write_answer(payload: dict[str, object], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path
