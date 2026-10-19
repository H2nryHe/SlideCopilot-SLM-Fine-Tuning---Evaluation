from __future__ import annotations

from pathlib import Path

import pytest

from pptcopilot.eval.rag_benchmark import run_rag_benchmark


@pytest.mark.rag
def test_real_dense_faiss_and_llm_end_to_end(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report = run_rag_benchmark(
        corpus_path=repo_root / "data/eval/milestone1_corpus.jsonl",
        dataset_path=repo_root / "data/eval/milestone1_qa.jsonl",
        out_path=tmp_path / "real_rag.json",
        retrievers=["dense"],
        generator="hf:google/flan-t5-small",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    system = report["systems"][0]
    assert system["index"]["backend"] == "faiss"
    assert system["index"]["retriever"] == "dense"
    assert system["metrics"]["recall_at_5"] >= 0.5
    assert system["metrics"]["n_queries"] == 10
