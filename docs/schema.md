# Data Ingestion Schema (Stage 2)

Each line in the ingestion output JSONL must conform to:

| Field | Type | Description |
|---|---|---|
| `doc_id` | `str` | Stable document identifier from source file hash prefix. |
| `slide_id` | `str` | Stable slide identifier (`<doc_id>_sNNN`). |
| `slide_text` | `str` | Concatenated text extracted from the slide body/shapes. |
| `notes_text` | `str` | Extracted speaker notes text for the slide (empty if none). |
| `title` | `str` | Heuristic slide title (first text segment). |
| `n_slides` | `int` | Total number of slides in the source deck. |
| `source_path` | `str` | Absolute path to the source PPTX file. |
| `lang` | `str` | Light language guess (`en` or `unknown`). |
| `hash` | `str` | SHA-256 hash of slide+notes content. |

Validation is implemented in `src/pptcopilot/io/ingest_pptx.py` via:
- `validate_record(record)`
- `validate_records(records)`
