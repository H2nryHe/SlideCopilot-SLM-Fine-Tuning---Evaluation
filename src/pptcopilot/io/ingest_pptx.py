"""PPTX ingestion into the Stage 2 JSONL schema."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile

REQUIRED_FIELDS = (
    "doc_id",
    "slide_id",
    "slide_text",
    "notes_text",
    "title",
    "n_slides",
    "source_path",
    "lang",
    "hash",
)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_text(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    texts: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            value = _normalize_whitespace(node.text)
            if value:
                texts.append(value)
    return texts


def _slide_number(member_path: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", member_path)
    if not match:
        raise ValueError(f"Invalid slide member path: {member_path}")
    return int(match.group(1))


def _guess_lang(text: str) -> str:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "unknown"
    ascii_letters = [ch for ch in letters if ch.isascii()]
    return "en" if len(ascii_letters) / len(letters) >= 0.8 else "unknown"


def _build_record(
    *,
    doc_id: str,
    slide_num: int,
    n_slides: int,
    source_path: Path,
    slide_text: str,
    notes_text: str,
) -> dict[str, object]:
    payload = f"{slide_text}\n{notes_text}".encode("utf-8")
    slide_hash = hashlib.sha256(payload).hexdigest()
    lang = _guess_lang(f"{slide_text} {notes_text}")
    return {
        "doc_id": doc_id,
        "slide_id": f"{doc_id}_s{slide_num:03d}",
        "slide_text": slide_text,
        "notes_text": notes_text,
        "title": slide_text.split(" | ")[0] if slide_text else "",
        "n_slides": n_slides,
        "source_path": str(source_path.resolve()),
        "lang": lang,
        "hash": slide_hash,
    }


def ingest_pptx(source_path: str | Path) -> list[dict[str, object]]:
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Input PPTX does not exist: {path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError(f"Expected .pptx input, got: {path}")

    raw_bytes = path.read_bytes()
    doc_id = hashlib.sha256(raw_bytes).hexdigest()[:16]

    with ZipFile(path, "r") as zip_file:
        members = set(zip_file.namelist())
        slide_members = sorted(
            (
                name for name in members if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ),
            key=_slide_number,
        )
        n_slides = len(slide_members)
        if n_slides == 0:
            raise ValueError(f"No slides found in PPTX: {path}")

        records: list[dict[str, object]] = []
        for member in slide_members:
            slide_num = _slide_number(member)
            slide_parts = _extract_text(zip_file.read(member))
            slide_text = _normalize_whitespace(" | ".join(slide_parts))

            notes_member = f"ppt/notesSlides/notesSlide{slide_num}.xml"
            notes_text = ""
            if notes_member in members:
                notes_parts = _extract_text(zip_file.read(notes_member))
                notes_text = _normalize_whitespace(" ".join(notes_parts))

            record = _build_record(
                doc_id=doc_id,
                slide_num=slide_num,
                n_slides=n_slides,
                source_path=path,
                slide_text=slide_text,
                notes_text=notes_text,
            )
            records.append(record)

    validate_records(records)
    return records


def validate_record(record: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(record["doc_id"], str) or not record["doc_id"]:
        raise ValueError("Field 'doc_id' must be a non-empty string")
    if not isinstance(record["slide_id"], str) or not record["slide_id"]:
        raise ValueError("Field 'slide_id' must be a non-empty string")
    if not isinstance(record["slide_text"], str):
        raise ValueError("Field 'slide_text' must be a string")
    if not isinstance(record["notes_text"], str):
        raise ValueError("Field 'notes_text' must be a string")
    if not isinstance(record["title"], str):
        raise ValueError("Field 'title' must be a string")
    if not isinstance(record["n_slides"], int) or record["n_slides"] <= 0:
        raise ValueError("Field 'n_slides' must be a positive integer")
    if not isinstance(record["source_path"], str) or not record["source_path"]:
        raise ValueError("Field 'source_path' must be a non-empty string")
    if not isinstance(record["lang"], str) or not record["lang"]:
        raise ValueError("Field 'lang' must be a non-empty string")
    if not isinstance(record["hash"], str) or len(record["hash"]) != 64:
        raise ValueError("Field 'hash' must be a sha256 hex string")


def validate_records(records: Iterable[dict[str, object]]) -> None:
    for idx, record in enumerate(records, start=1):
        try:
            validate_record(record)
        except ValueError as exc:
            raise ValueError(f"Invalid record at index {idx}: {exc}") from exc


def write_jsonl(records: Iterable[dict[str, object]], output_path: str | Path) -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    return out_path


def ingest_pptx_to_jsonl(source_path: str | Path, output_path: str | Path) -> Path:
    records = ingest_pptx(source_path)
    return write_jsonl(records, output_path)
