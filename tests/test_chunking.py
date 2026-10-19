from pptcopilot.io.chunking import chunk_record


def test_chunking_preserves_numeric_surface_text() -> None:
    record = {
        "doc_id": "d",
        "slide_id": "d_s001",
        "slide_text": "Margins | Operating margin was 18.7% and latency was 1.25s.",
        "notes_text": "",
        "title": "Margins",
    }
    chunks = chunk_record(record, chunk_size_tokens=40, chunk_overlap_tokens=8)
    assert "18.7%" in chunks[0]["chunk_text"]
    assert "1.25s." in chunks[0]["chunk_text"]
