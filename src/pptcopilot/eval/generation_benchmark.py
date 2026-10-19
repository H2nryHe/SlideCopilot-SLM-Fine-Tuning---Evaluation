"""Generation-only evaluation on the frozen Milestone 1 Dense retriever."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from pptcopilot.eval.metrics import (
    answer_match,
    citation_recall,
    reciprocal_rank,
    retrieval_recall_at_k,
)
from pptcopilot.qa.citations import select_answer_citations
from pptcopilot.qa.generate import generate_answer, get_hf_model_metadata
from pptcopilot.retrieval.index_faiss import CHUNKS_FILE, build_index
from pptcopilot.retrieval.retrieve import retrieve_top_k


FROZEN_CORPUS_SHA256 = "82f8942c01f0e0c37e0e734eeaf2cdadf820522cf6fe4051149380ac63cdaf77"
FROZEN_DATASET_SHA256 = "4eea99dca6c5e78afab678f848a12be66c6680245e48c5accc016f6f93c3c9d6"
FROZEN_DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_GENERATORS = [
    "hf:google/flan-t5-small",
    "hf:google/flan-t5-base",
    "hf-qa:deepset/roberta-base-squad2",
]


def _read_jsonl(path: str | Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mean(values: list[float]) -> float:
    return round(mean(values) if values else 0.0, 4)


def _oracle_hits(
    chunks: list[dict[str, object]], expected_slide_ids: list[str]
) -> list[dict[str, object]]:
    expected = set(expected_slide_ids)
    hits: list[dict[str, object]] = []
    for chunk in chunks:
        if str(chunk.get("slide_id", "")) not in expected:
            continue
        hits.append(
            {
                "rank": len(hits) + 1,
                "score": None,
                "chunk_id": chunk["chunk_id"],
                "slide_id": chunk["slide_id"],
                "doc_id": chunk["doc_id"],
                "chunk_text": chunk["chunk_text"],
                "title": chunk.get("title", ""),
            }
        )
    return hits


def _condition_hits(
    *,
    condition: str,
    dense_hits: list[dict[str, object]],
    oracle_hits: list[dict[str, object]],
    answer_top_k: int,
) -> list[dict[str, object]]:
    if condition == "dense_top_k":
        return dense_hits[:answer_top_k]
    if condition == "dense_top_1":
        return dense_hits[:1]
    if condition == "oracle_evidence":
        return oracle_hits
    raise ValueError(f"Unknown generation context condition: {condition}")


def _error_cause(
    *,
    answer_correct: bool,
    recall_at_1: float,
    context_slide_ids: list[str],
    expected_slide_ids: list[str],
) -> str:
    if answer_correct:
        return "success"
    if recall_at_1 < 1.0:
        return "retrieval_miss_at_rank_1"
    if not set(context_slide_ids).intersection(expected_slide_ids):
        return "expected_evidence_missing_from_generation_context"
    return "generation_failure_with_expected_evidence"


def _validate_frozen_protocol(
    *,
    corpus_sha256: str,
    dataset_sha256: str,
    embedding_model: str,
) -> None:
    mismatches: list[str] = []
    if corpus_sha256 != FROZEN_CORPUS_SHA256:
        mismatches.append(
            f"corpus SHA-256 {corpus_sha256} != frozen {FROZEN_CORPUS_SHA256}"
        )
    if dataset_sha256 != FROZEN_DATASET_SHA256:
        mismatches.append(
            f"dataset SHA-256 {dataset_sha256} != frozen {FROZEN_DATASET_SHA256}"
        )
    if embedding_model != FROZEN_DENSE_MODEL:
        mismatches.append(
            f"embedding model {embedding_model!r} != frozen {FROZEN_DENSE_MODEL!r}"
        )
    if mismatches:
        raise ValueError("Milestone 1.5 frozen protocol violation: " + "; ".join(mismatches))


def run_generation_benchmark(
    *,
    corpus_path: str | Path,
    dataset_path: str | Path,
    out_path: str | Path,
    generators: list[str] | None = None,
    embedding_model: str = FROZEN_DENSE_MODEL,
    answer_top_k: int = 5,
    enforce_frozen_protocol: bool = True,
) -> dict[str, object]:
    """Compare generators and evidence contexts without changing retrieval.

    Dense retrieval is built once and queried once per held-out question. The
    generated answer is then evaluated with Dense top-k, Dense top-1, and oracle
    evidence contexts so retrieval and generation errors can be separated.
    """
    if answer_top_k <= 1:
        raise ValueError("answer_top_k must be greater than 1 for the top-k ablation")

    corpus = Path(corpus_path)
    dataset = Path(dataset_path)
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    corpus_sha256 = _sha256(corpus)
    dataset_sha256 = _sha256(dataset)
    if enforce_frozen_protocol:
        _validate_frozen_protocol(
            corpus_sha256=corpus_sha256,
            dataset_sha256=dataset_sha256,
            embedding_model=embedding_model,
        )

    examples = _read_jsonl(dataset)
    if not examples:
        raise ValueError("Generation evaluation dataset is empty")
    generators = generators or list(DEFAULT_GENERATORS)
    if not generators:
        raise ValueError("At least one generator is required")

    index_dir = output.parent / "_generation_index" / "dense"
    index_meta = build_index(
        corpus,
        index_dir,
        retriever="dense",
        embedding_model=embedding_model,
    )
    chunks = _read_jsonl(index_dir / CHUNKS_FILE)

    prepared: list[dict[str, object]] = []
    recall_1: list[float] = []
    recall_5: list[float] = []
    recall_10: list[float] = []
    reciprocal_ranks: list[float] = []
    for example in examples:
        question = str(example["question"])
        expected_slides = [str(value) for value in example["expected_slide_ids"]]
        retrieval = retrieve_top_k(index_dir, question, top_k=10)
        dense_hits = list(retrieval["hits"])
        ranked_slides = [str(hit["slide_id"]) for hit in dense_hits]
        r1 = retrieval_recall_at_k(ranked_slides, expected_slides, k=1)
        r5 = retrieval_recall_at_k(ranked_slides, expected_slides, k=5)
        r10 = retrieval_recall_at_k(ranked_slides, expected_slides, k=10)
        rr = reciprocal_rank(ranked_slides, expected_slides)
        recall_1.append(r1)
        recall_5.append(r5)
        recall_10.append(r10)
        reciprocal_ranks.append(rr)
        prepared.append(
            {
                "example": example,
                "dense_hits": dense_hits,
                "oracle_hits": _oracle_hits(chunks, expected_slides),
                "retrieval": {
                    "top_10_slide_ids": ranked_slides[:10],
                    "recall_at_1": round(r1, 4),
                    "recall_at_5": round(r5, 4),
                    "recall_at_10": round(r10, 4),
                    "reciprocal_rank": round(rr, 4),
                },
            }
        )

    retrieval_metrics = {
        "recall_at_1": _mean(recall_1),
        "recall_at_5": _mean(recall_5),
        "recall_at_10": _mean(recall_10),
        "mrr": _mean(reciprocal_ranks),
        "n_queries": len(examples),
    }
    conditions = ["dense_top_k", "dense_top_1", "oracle_evidence"]
    systems: list[dict[str, object]] = []

    for generator in generators:
        for condition in conditions:
            started = time.perf_counter()
            answer_scores: list[float] = []
            citation_scores: list[float] = []
            errors: Counter[str] = Counter()
            queries: list[dict[str, object]] = []
            for item in prepared:
                example = item["example"]
                expected_slides = [str(value) for value in example["expected_slide_ids"]]
                hits = _condition_hits(
                    condition=condition,
                    dense_hits=item["dense_hits"],
                    oracle_hits=item["oracle_hits"],
                    answer_top_k=answer_top_k,
                )
                answer = generate_answer(
                    str(example["question"]),
                    hits,
                    backend=generator,
                )
                citations = select_answer_citations(answer, hits)
                match = answer_match(
                    answer,
                    [str(value) for value in example.get("acceptable_answers", [])],
                )
                citation = citation_recall(citations, expected_slides)
                context_slide_ids = [str(hit["slide_id"]) for hit in hits]
                cause = _error_cause(
                    answer_correct=bool(match["matched"]),
                    recall_at_1=float(item["retrieval"]["recall_at_1"]),
                    context_slide_ids=context_slide_ids,
                    expected_slide_ids=expected_slides,
                )
                errors[cause] += 1
                answer_scores.append(1.0 if match["matched"] else 0.0)
                citation_scores.append(float(citation["recall"]))
                queries.append(
                    {
                        "id": example.get("id"),
                        "question": example["question"],
                        "expected_slide_ids": expected_slides,
                        "acceptable_answers": example.get("acceptable_answers", []),
                        "retrieval": item["retrieval"],
                        "context_slide_ids": context_slide_ids,
                        "answer": answer,
                        "cited_slide_ids": citations,
                        "metrics": {
                            "answer_correct": bool(match["matched"]),
                            "matched_answer": match["matched_answer"],
                            "citation_recall": citation["recall"],
                        },
                        "error_cause": cause,
                    }
                )

            model_metadata: dict[str, object] | None = None
            if generator.startswith(
                ("hf:", "hf-qa:", "hf-span:", "hf-causal:", "hf-causal-span:")
            ):
                model_metadata = get_hf_model_metadata(
                    generator.split(":", 1)[1],
                    causal=generator.startswith(("hf-causal:", "hf-causal-span:")),
                    question_answering=generator.startswith("hf-qa:"),
                )
            prompt_version = "legacy_grounded_v1"
            if generator.startswith(("hf-span:", "hf-causal-span:")):
                prompt_version = "exact_span_v1"
            elif generator.startswith("hf-qa:"):
                prompt_version = "extractive_qa_v1"
            systems.append(
                {
                    "generator": generator,
                    "model": model_metadata,
                    "prompt_version": prompt_version,
                    "context_condition": condition,
                    "context_top_k": answer_top_k if condition == "dense_top_k" else 1,
                    "metrics": {
                        **retrieval_metrics,
                        "answer_accuracy": _mean(answer_scores),
                        "citation_recall": _mean(citation_scores),
                        "runtime_seconds": round(time.perf_counter() - started, 3),
                    },
                    "error_counts": dict(sorted(errors.items())),
                    "queries": queries,
                }
            )

    report: dict[str, object] = {
        "benchmark": "milestone1_5_generation_upgrade",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "frozen": enforce_frozen_protocol,
            "corpus": {
                "path": str(corpus),
                "sha256": corpus_sha256,
                "expected_sha256": FROZEN_CORPUS_SHA256,
            },
            "dataset": {
                "path": str(dataset),
                "sha256": dataset_sha256,
                "expected_sha256": FROZEN_DATASET_SHA256,
            },
            "retriever": "dense",
            "embedding_model": embedding_model,
            "retrieval_evaluation_depth": 10,
            "generation_contexts": {
                "dense_top_k": answer_top_k,
                "dense_top_1": 1,
                "oracle_evidence": "all chunks from expected_slide_ids",
            },
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "index": index_meta,
        "retrieval_metrics": retrieval_metrics,
        "systems": systems,
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return report


def write_sha256_sidecar(path: str | Path) -> Path:
    """Write a portable digest sidecar for the completed JSON artifact."""
    artifact = Path(path)
    sidecar = artifact.with_suffix(artifact.suffix + ".sha256")
    sidecar.write_text(f"{_sha256(artifact)}  {artifact.name}\n", encoding="utf-8")
    return sidecar
