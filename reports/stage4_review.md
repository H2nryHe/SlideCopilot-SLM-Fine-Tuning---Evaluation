# Stage 4 Review

## Scope
Implemented retrieval + RAG-style QA with citations, index/qa CLI commands, and debug chunk logging.

## Commands Run

```bash
python -m pip install -e .
pytest
pptcopilot index data/processed/sample.jsonl --index-dir artifacts/index/sample
pptcopilot qa --index-dir artifacts/index/sample --question "Which slide discusses evaluation harness and scenarios?" -o reports/qa/sample_qa.json
pptcopilot qa --index-dir artifacts/index/sample --question "Which slide discusses evaluation harness and scenarios?" --debug -o reports/qa/sample_qa_debug.json
```

## Outputs

- `pytest`: `12 passed in 0.04s`
- index command output includes:
  - `status=ok`
  - `backend=bruteforce` (FAISS optional and used when available)
  - `n_chunks=6`
- qa command output includes:
  - `status=ok`
  - `n_citations=3`
- debug qa output file includes `retrieved_chunks` for retrieval debugging.
