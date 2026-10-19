from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.eval.metrics import reciprocal_rank, retrieval_recall_at_k
from pptcopilot.eval.rag_benchmark import run_rag_benchmark


def test_ranking_metrics() -> None:
    ranked = ["s3", "s2", "s1"]
    expected = ["s2"]
    assert retrieval_recall_at_k(ranked, expected, k=1) == 0.0
    assert retrieval_recall_at_k(ranked, expected, k=2) == 1.0
    assert reciprocal_rank(ranked, expected) == 0.5


def test_hash_rag_benchmark_runs_without_model_download(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    rows = [
        {
            "doc_id": "d",
            "slide_id": "d_s001",
            "slide_text": "Margin | Operating margin was 18.7 percent.",
            "notes_text": "",
            "title": "Margin",
            "n_slides": 2,
            "source_path": "/tmp/d.pptx",
            "lang": "en",
            "hash": "1" * 64,
        },
        {
            "doc_id": "d",
            "slide_id": "d_s002",
            "slide_text": "Cash | Cash balance was 74 million dollars.",
            "notes_text": "",
            "title": "Cash",
            "n_slides": 2,
            "source_path": "/tmp/d.pptx",
            "lang": "en",
            "hash": "2" * 64,
        },
    ]
    corpus.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
    dataset = tmp_path / "qa.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "q1",
                "question": "What was the operating margin?",
                "expected_slide_ids": ["d_s001"],
                "acceptable_answers": ["18.7 percent"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "report.json"
    report = run_rag_benchmark(
        corpus_path=corpus,
        dataset_path=dataset,
        out_path=out,
        retrievers=["hash"],
        generator="extractive",
    )
    assert out.exists()
    assert report["systems"][0]["metrics"]["recall_at_5"] == 1.0
    assert report["systems"][0]["metrics"]["answer_accuracy"] == 1.0
