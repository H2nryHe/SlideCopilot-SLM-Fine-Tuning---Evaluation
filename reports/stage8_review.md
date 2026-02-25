# Stage 8 Review

## Scope
Implemented production-ish demo polish: optional FastAPI service, CI workflow, portfolio quickstart, and improved command failure logging.

## Commands Run

```bash
python -m pip install -e .
pytest
python scripts/generate_sample_pptx.py -o data/raw/stage8_demo.pptx
pptcopilot ingest data/raw/stage8_demo.pptx -o data/processed/stage8_demo.jsonl
pptcopilot index data/processed/stage8_demo.jsonl --index-dir artifacts/index/stage8_demo
pptcopilot summarize data/processed/stage8_demo.jsonl --model mock -o reports/summaries/stage8_demo_summary.json
pptcopilot qa --index-dir artifacts/index/stage8_demo --question "Which slide discusses evaluation harness and scenarios?" -o reports/qa/stage8_demo_qa.json
pptcopilot eval run --suite smoke --model mock --outdir reports/eval
pptcopilot bench latency --suite smoke --out reports/bench/latency.json --iterations 3 --warmup 1 --batch 1
pptcopilot bench cost --in reports/bench/latency.json --out reports/bench/cost.json --summary-out reports/bench/summary.md
```

## Outputs

- `pytest`: `22 passed in 0.12s`
- End-to-end demo chain succeeded: ingest -> index -> summarize -> qa -> eval -> bench
- Eval artifacts:
  - `reports/eval/latest_report.json`
  - `reports/eval/latest_report.md`
- Bench artifacts:
  - `reports/bench/latency.json`
  - `reports/bench/cost.json`
  - `reports/bench/summary.md`
- CI workflow added:
  - `.github/workflows/nightly_eval.yml`
- Helpful failure output confirmed (structured JSON + stack trace log) on invalid summarize input.
