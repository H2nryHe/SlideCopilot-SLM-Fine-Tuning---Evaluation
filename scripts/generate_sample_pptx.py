#!/usr/bin/env python3
"""Generate a tiny synthetic PPTX-like archive for ingestion tests/smoke runs."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


SLIDES = [
    ("SlideCopilot Overview", "Goal: summarize and answer questions from decks."),
    ("Data Pipeline", "Ingest PPTX into JSONL with stable IDs and hashes."),
    ("Baseline Summary", "Create deterministic summary output for regression tests."),
    ("Retrieval Plan", "Add FAISS index and citation-grounded QA."),
    ("Evaluation Harness", "Run scenario-based smoke suites with pass/fail."),
    ("Latency & Cost", "Track p50/p95 latency and estimate serving cost."),
]

NOTES = [
    "Introduce project scope and outcome.",
    "Mention schema fields and validation.",
    "Highlight deterministic defaults for repeatability.",
    "Focus on reducing hallucinations with grounding.",
    "Scenarios should mimic real Copilot tasks.",
    "Benchmarking enables quality-speed-cost trade-offs.",
]


def _slide_xml(title: str, body: str) -> str:
    safe_title = escape(title)
    safe_body = escape(body)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>{safe_title}</a:t></a:r></a:p>
          <a:p><a:r><a:t>{safe_body}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""


def _notes_xml(notes: str) -> str:
    safe_notes = escape(notes)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
         xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>{safe_notes}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:notes>
"""


def generate_synthetic_pptx(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>
""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>
""",
        )
        zf.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"></p:presentation>
""",
        )
        for idx, (slide, notes) in enumerate(zip(SLIDES, NOTES), start=1):
            title, body = slide
            zf.writestr(f"ppt/slides/slide{idx}.xml", _slide_xml(title, body))
            zf.writestr(f"ppt/notesSlides/notesSlide{idx}.xml", _notes_xml(notes))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic PPTX sample.")
    parser.add_argument(
        "-o",
        "--output",
        default="data/raw/sample_deck.pptx",
        help="Output PPTX path",
    )
    args = parser.parse_args()
    output = generate_synthetic_pptx(Path(args.output))
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
