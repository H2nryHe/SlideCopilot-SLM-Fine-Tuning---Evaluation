"""RAG-style QA using retrieved slide chunks, generation, and citations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pptcopilot.config import get_generation_defaults, get_retrieval_defaults
from pptcopilot.qa.citations import select_answer_citations
from pptcopilot.qa.generate import generate_answer
from pptcopilot.retrieval.retrieve import retrieve_top_k


def answer_question(
    *,
    index_dir: str | Path,
    question: str,
    top_k: int | None = None,
    debug: bool = False,
    generator: str = "extractive",
) -> dict[str, object]:
    retrieval_defaults = get_retrieval_defaults()
    generation_defaults = get_generation_defaults()
    top_k = retrieval_defaults.top_k if top_k is None else top_k

    retrieval = retrieve_top_k(index_dir, question, top_k=top_k)
    hits = retrieval["hits"]
    answer = generate_answer(
        question,
        hits,
        backend=generator,
        max_new_tokens=generation_defaults.max_new_tokens,
    )
    citations = select_answer_citations(answer, hits)

    payload: dict[str, object] = {
        "question": question,
        "answer": answer,
        "cited_slide_ids": citations,
        "metadata": {
            "top_k": top_k,
            "retriever": retrieval.get("retriever", "hash"),
            "retrieval_backend": retrieval["backend"],
            "generator": generator,
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
