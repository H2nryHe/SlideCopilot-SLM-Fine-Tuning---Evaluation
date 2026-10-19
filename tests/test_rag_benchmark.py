from __future__ import annotations

import json
from pathlib import Path

import pytest

from pptcopilot.eval.metrics import reciprocal_rank, retrieval_recall_at_k
from pptcopilot.eval.generation_benchmark import run_generation_benchmark
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


def test_generation_benchmark_separates_dense_and_oracle_contexts(
    tmp_path: Path, monkeypatch
) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "doc_id": "d",
                "slide_id": "d_s001",
                "slide_text": "Cash | Cash balance was 74 million dollars.",
                "notes_text": "",
                "title": "Cash",
                "n_slides": 1,
                "source_path": "/tmp/d.pptx",
                "lang": "en",
                "hash": "1" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    dataset = tmp_path / "qa.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "q1",
                "question": "How much cash?",
                "expected_slide_ids": ["d_s001"],
                "acceptable_answers": ["74 million"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_build_index(input_path, index_dir, **kwargs):
        index_root = Path(index_dir)
        index_root.mkdir(parents=True)
        (index_root / "chunks.jsonl").write_text(
            json.dumps(
                {
                    "chunk_id": "d_s001_c000",
                    "doc_id": "d",
                    "slide_id": "d_s001",
                    "chunk_text": "Cash balance was 74 million dollars.",
                    "title": "Cash",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return {"retriever": "dense", "backend": "faiss", **kwargs}

    def fake_retrieve(*args, **kwargs):
        return {
            "hits": [
                {
                    "rank": 1,
                    "score": 1.0,
                    "chunk_id": "d_s001_c000",
                    "doc_id": "d",
                    "slide_id": "d_s001",
                    "chunk_text": "Cash balance was 74 million dollars.",
                    "title": "Cash",
                }
            ]
        }

    monkeypatch.setattr(
        "pptcopilot.eval.generation_benchmark.build_index", fake_build_index
    )
    monkeypatch.setattr(
        "pptcopilot.eval.generation_benchmark.retrieve_top_k", fake_retrieve
    )
    monkeypatch.setattr(
        "pptcopilot.eval.generation_benchmark.generate_answer",
        lambda question, hits, backend: "74 million",
    )
    report = run_generation_benchmark(
        corpus_path=corpus,
        dataset_path=dataset,
        out_path=tmp_path / "generation.json",
        generators=["extractive"],
        answer_top_k=5,
        enforce_frozen_protocol=False,
    )

    assert report["retrieval_metrics"]["recall_at_1"] == 1.0
    assert [system["context_condition"] for system in report["systems"]] == [
        "dense_top_k",
        "dense_top_1",
        "oracle_evidence",
    ]
    assert all(system["metrics"]["answer_accuracy"] == 1.0 for system in report["systems"])
    assert all(system["error_counts"] == {"success": 1} for system in report["systems"])


def test_generation_benchmark_rejects_changed_frozen_inputs(tmp_path: Path) -> None:
    corpus = tmp_path / "changed_corpus.jsonl"
    dataset = tmp_path / "changed_dataset.jsonl"
    corpus.write_text("{}\n", encoding="utf-8")
    dataset.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="frozen protocol violation"):
        run_generation_benchmark(
            corpus_path=corpus,
            dataset_path=dataset,
            out_path=tmp_path / "report.json",
            generators=["extractive"],
        )
