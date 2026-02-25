"""PDF ingestion placeholder.

Stage 2 scope prioritizes PPTX ingestion. PDF support can be added in a later
iteration once OCR/text extraction dependencies are selected.
"""

from __future__ import annotations

from pathlib import Path


def ingest_pdf(_: str | Path) -> list[dict[str, object]]:
    raise NotImplementedError("PDF ingestion is not implemented yet. Use PPTX ingestion.")
