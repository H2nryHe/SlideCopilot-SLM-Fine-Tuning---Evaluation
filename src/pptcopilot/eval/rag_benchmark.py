"""Held-out RAG benchmark comparing retrieval strategies end to end."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from pptcopilot.eval.metrics import (
    answer_match,
    citation_recall,
    reciprocal_rank,
    retrieval_recall_at_k,
)
from pptcopilot.qa.answer import answer_question
from pptcopilot.retrieval.index_faiss import build_index
from pptcopilot.retrieval.retrieve import retrieve_top_k


def _read_jsonl(path: str | Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _pct(values: list[float]) -> float:
    return round(mean(values) if values else 0.0, 4)


def run_rag_benchmark(
    *,
    corpus_path: str | Path,
    dataset_path: str | Path,
    out_path: str | Path,
    retrievers: list[str] | None = None,
    generator: str = "extractive",
    embedding_model: str | None = None,
    answer_top_k: int = 5,
) -> dict[str, object]:
    """Evaluate retrieval and answer quality on a frozen held-out QA set."""
    retrievers = retrievers or ["hash", "dense"]
    corpus = Path(corpus_path)
    dataset = Path(dataset_path)
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    examples = _read_jsonl(dataset)
    if not examples:
        raise ValueError("RAG evaluation dataset is empty")

    system_results: list[dict[str, object]] = []
    for retriever in retrievers:
        index_dir = output.parent / "_rag_indices" / retriever
        index_meta = build_index(
            corpus,
            index_dir,
            retriever=retriever,
            embedding_model=embedding_model,
        )

        per_query: list[dict[str, object]] = []
        recall_1: list[float] = []
        recall_5: list[float] = []
        recall_10: list[float] = []
        mrr: list[float] = []
        answer_scores: list[float] = []
        citation_scores: list[float] = []

        for example in examples:
            question = str(example["question"])
            expected_slides = [str(x) for x in example["expected_slide_ids"]]
            acceptable_answers = [str(x) for x in example.get("acceptable_answers", [])]

            retrieval = retrieve_top_k(index_dir, question, top_k=10)
            ranked_slides = [str(hit["slide_id"]) for hit in retrieval["hits"]]
            r1 = retrieval_recall_at_k(ranked_slides, expected_slides, k=1)
            r5 = retrieval_recall_at_k(ranked_slides, expected_slides, k=5)
            r10 = retrieval_recall_at_k(ranked_slides, expected_slides, k=10)
            rr = reciprocal_rank(ranked_slides, expected_slides)

            answer = answer_question(
                index_dir=index_dir,
                question=question,
                top_k=answer_top_k,
                debug=False,
                generator=generator,
            )
            answer_metric = answer_match(str(answer["answer"]), acceptable_answers)
            citation_metric = citation_recall(
                [str(x) for x in answer["cited_slide_ids"]],
                expected_slides,
            )

            recall_1.append(r1)
            recall_5.append(r5)
            recall_10.append(r10)
            mrr.append(rr)
            answer_scores.append(1.0 if answer_metric["matched"] else 0.0)
            citation_scores.append(float(citation_metric["recall"]))
            per_query.append(
                {
                    "id": example.get("id"),
                    "question": question,
                    "expected_slide_ids": expected_slides,
                    "top_10_slide_ids": ranked_slides[:10],
                    "answer": answer["answer"],
                    "cited_slide_ids": answer["cited_slide_ids"],
                    "metrics": {
                        "recall_at_1": round(r1, 4),
                        "recall_at_5": round(r5, 4),
                        "recall_at_10": round(r10, 4),
                        "reciprocal_rank": round(rr, 4),
                        "answer_correct": bool(answer_metric["matched"]),
                        "citation_recall": citation_metric["recall"],
                    },
                }
            )

        system_results.append(
            {
                "retriever": retriever,
                "generator": generator,
                "index": index_meta,
                "metrics": {
                    "recall_at_1": _pct(recall_1),
                    "recall_at_5": _pct(recall_5),
                    "recall_at_10": _pct(recall_10),
                    "mrr": _pct(mrr),
                    "answer_accuracy": _pct(answer_scores),
                    "citation_recall": _pct(citation_scores),
                    "n_queries": len(examples),
                },
                "queries": per_query,
            }
        )

    report = {
        "benchmark": "milestone1_heldout_rag",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_path": str(corpus.resolve()),
        "dataset_path": str(dataset.resolve()),
        "generator": generator,
        "systems": system_results,
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return report
