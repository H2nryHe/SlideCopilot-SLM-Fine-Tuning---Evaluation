# Stage 2 Review

## Scope
Implemented PPTX ingestion into standardized JSONL with CLI support and schema validation.

## Commands Run

```bash
python -m pip install -e .
pytest
python scripts/generate_sample_pptx.py -o data/raw/sample_deck.pptx
pptcopilot ingest data/raw/sample_deck.pptx -o data/processed/sample.jsonl
python -c "import json;from pathlib import Path;from pptcopilot.io.ingest_pptx import validate_records;path=Path('data/processed/sample.jsonl');records=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()];validate_records(records);print(len(records));print(all(bool(r['slide_text']) for r in records))"
```

## Outputs

- `pytest`: `6 passed in 0.02s`
- synthetic deck created at `data/raw/sample_deck.pptx`
- ingest command output:
  - `{"status": "ok", "input_path": ".../data/raw/sample_deck.pptx", "output_path": ".../data/processed/sample.jsonl", "n_records": 6}`
- schema validation script output:
  - `6`
  - `True`
