# Stage 7 Review

## Scope
Implemented latency/cost benchmarking with configurable settings, multi-variant comparison, and markdown summary output.

## Commands Run

```bash
python -m pip install -e .
pytest
pptcopilot bench latency --suite smoke --out reports/bench/latency.json --iterations 5 --warmup 1 --batch 1
pptcopilot bench cost --in reports/bench/latency.json --out reports/bench/cost.json --summary-out reports/bench/summary.md
```

## Outputs

- `pytest`: `21 passed in 0.16s`
- `reports/bench/latency.json`:
  - compares 2 variants (`baseline`, `fast`)
  - includes p50/p95 for summarize and QA
- `reports/bench/cost.json`:
  - cost assumptions and USD/1k request estimates
- `reports/bench/summary.md`:
  - human-readable latency/throughput/cost comparison table
