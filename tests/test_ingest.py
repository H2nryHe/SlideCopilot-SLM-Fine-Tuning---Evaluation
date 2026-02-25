from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pptcopilot.cli import main
from pptcopilot.io.ingest_pptx import ingest_pptx, validate_records


def _make_test_pptx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("_rels/.rels", "<Relationships/>")
        zf.writestr("ppt/presentation.xml", "<presentation/>")
        zf.writestr(
            "ppt/slides/slide1.xml",
            """
            <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                   xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
              <p:cSld><p:spTree><p:sp><p:txBody>
                <a:p><a:r><a:t>Title One</a:t></a:r></a:p>
                <a:p><a:r><a:t>Body text one.</a:t></a:r></a:p>
              </p:txBody></p:sp></p:spTree></p:cSld>
            </p:sld>
            """,
        )
        zf.writestr(
            "ppt/notesSlides/notesSlide1.xml",
            """
            <p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                     xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
              <p:cSld><p:spTree><p:sp><p:txBody>
                <a:p><a:r><a:t>speaker notes</a:t></a:r></a:p>
              </p:txBody></p:sp></p:spTree></p:cSld>
            </p:notes>
            """,
        )
    return path


def test_ingest_pptx_non_empty_slide_text(tmp_path: Path) -> None:
    pptx_path = _make_test_pptx(tmp_path / "tiny.pptx")
    records = ingest_pptx(pptx_path)

    assert len(records) == 1
    assert records[0]["slide_text"]
    validate_records(records)


def test_cli_ingest_writes_valid_jsonl(tmp_path: Path) -> None:
    pptx_path = _make_test_pptx(tmp_path / "tiny_cli.pptx")
    out_path = tmp_path / "sample.jsonl"

    exit_code = main(["ingest", str(pptx_path), "-o", str(out_path)])

    assert exit_code == 0
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["slide_text"] != ""
