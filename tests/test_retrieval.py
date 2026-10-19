from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.qa.answer import answer_question
from pptcopilot.qa.citations import select_answer_citations
from pptcopilot.qa.generate import generate_answer
from pptcopilot.retrieval.index_faiss import build_index
from pptcopilot.retrieval.retrieve import retrieve_top_k


def _write_controlled_jsonl(path: Path) -> Path:
    rows = [
        {
            "doc_id": "deck1",
            "slide_id": "deck1_s001",
            "slide_text": "Roadmap Overview | Timeline and milestones for launch.",
            "notes_text": "",
            "title": "Roadmap Overview",
            "n_slides": 3,
            "source_path": "/tmp/deck1.pptx",
            "lang": "en",
            "hash": "1" * 64,
        },
        {
            "doc_id": "deck1",
            "slide_id": "deck1_s002",
            "slide_text": "Evaluation Harness | Smoke scenarios and regression metrics.",
            "notes_text": "focus on scenario pass rate",
            "title": "Evaluation Harness",
            "n_slides": 3,
            "source_path": "/tmp/deck1.pptx",
            "lang": "en",
            "hash": "2" * 64,
        },
        {
            "doc_id": "deck1",
            "slide_id": "deck1_s003",
            "slide_text": "Budget | Cost estimate by quarter.",
            "notes_text": "",
            "title": "Budget",
            "n_slides": 3,
            "source_path": "/tmp/deck1.pptx",
            "lang": "en",
            "hash": "3" * 64,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_retrieval_returns_expected_slide_id(tmp_path: Path) -> None:
    input_jsonl = _write_controlled_jsonl(tmp_path / "controlled.jsonl")
    index_dir = tmp_path / "index"
    build_index(input_jsonl, index_dir)

    retrieval = retrieve_top_k(index_dir, "Which slide covers smoke scenarios?", top_k=2)
    top_hit = retrieval["hits"][0]
    assert top_hit["slide_id"] == "deck1_s002"


def test_qa_returns_citations_and_debug_chunks(tmp_path: Path) -> None:
    input_jsonl = _write_controlled_jsonl(tmp_path / "qa_controlled.jsonl")
    index_dir = tmp_path / "index_qa"
    build_index(input_jsonl, index_dir)

    answer = answer_question(
        index_dir=index_dir,
        question="What covers regression metrics?",
        top_k=2,
        debug=True,
    )
    assert "answer" in answer
    assert "deck1_s002" in answer["cited_slide_ids"]
    assert len(answer["retrieved_chunks"]) >= 1


def test_citation_matching_ignores_trailing_sentence_punctuation() -> None:
    hits = [
        {
            "slide_id": "s1",
            "chunk_text": "The p95 latency target is below 2 seconds.",
        }
    ]
    assert select_answer_citations("2 seconds", hits) == ["s1"]


def test_hf_qa_backend_dispatches_model_name(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_hf_qa_answer(question, hits, *, model_name):
        observed.update(question=question, hits=hits, model_name=model_name)
        return "74 million"

    monkeypatch.setattr("pptcopilot.qa.generate.hf_qa_answer", fake_hf_qa_answer)
    hits = [{"slide_id": "s1", "chunk_text": "Cash was 74 million."}]
    answer = generate_answer("How much cash?", hits, backend="hf-qa:local/qa-model")

    assert answer == "74 million"
    assert observed == {
        "question": "How much cash?",
        "hits": hits,
        "model_name": "local/qa-model",
    }
