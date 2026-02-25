from __future__ import annotations

import json
from pathlib import Path

from pptcopilot.cli import main
from pptcopilot.summarize.baseline import summarize_jsonl


def _write_sample_jsonl(path: Path) -> Path:
    rows = [
        {
            "doc_id": "demo",
            "slide_id": "demo_s001",
            "slide_text": "Project Overview | Build a copilot for slides.",
            "notes_text": "notes",
            "title": "Project Overview",
            "n_slides": 2,
            "source_path": "/tmp/demo.pptx",
            "lang": "en",
            "hash": "a" * 64,
        },
        {
            "doc_id": "demo",
            "slide_id": "demo_s002",
            "slide_text": "Evaluation Plan | Run deterministic smoke scenarios.",
            "notes_text": "",
            "title": "Evaluation Plan",
            "n_slides": 2,
            "source_path": "/tmp/demo.pptx",
            "lang": "en",
            "hash": "b" * 64,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_mock_summarize_is_deterministic(tmp_path: Path) -> None:
    input_jsonl = _write_sample_jsonl(tmp_path / "slides.jsonl")

    result_a = summarize_jsonl(input_jsonl, model="mock")
    result_b = summarize_jsonl(input_jsonl, model="mock")

    assert result_a["document_summary"] == result_b["document_summary"]
    assert result_a["metadata"]["temperature"] == 0.0
    assert result_a["metadata"]["seed"] == 0
    assert float(result_a["metadata"]["runtime_sec"]) >= 0.0
    assert len(result_a["slide_bullets"]) == 2


def test_cli_summarize_writes_output(tmp_path: Path) -> None:
    input_jsonl = _write_sample_jsonl(tmp_path / "slides_cli.jsonl")
    out_json = tmp_path / "summary.json"

    exit_code = main(
        [
            "summarize",
            str(input_jsonl),
            "--model",
            "mock",
            "-o",
            str(out_json),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "document_summary" in payload
    assert "runtime_sec" in payload["metadata"]
